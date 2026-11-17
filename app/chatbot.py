"""Motor del chatbot híbrido: reglas (árboles de escenario) + clasificación de intenciones + derivación.

Arquitectura (según el artículo, sec. 3.1): el sistema se basa sobre todo en escenarios predefinidos para
las preguntas frecuentes; el NLP clasifica la entrada y la enruta al módulo de respuesta; no hay LLM generativo.
Los casos ambiguos o emocionalmente cargados se derivan a un operador humano (sec. 4.4).

Flujo de decisión en `respond()`:
  1. Saludo/agradecimiento  -> respuesta fija (no cuenta como consulta).
  2. Relleno de dato pendiente (p. ej. el cliente envía solo el código de pedido).
  3. Reglas de derivación: pide humano, lenguaje emocional, acciones que requiere un operador.
  4. Confianza del clasificador < umbral -> derivación.
  5. Módulo de respuesta de la intención (consulta SQLite).
"""
from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime

from app.db import get_conn
from app.nlu import IntentClassifier, get_classifier, normalize
from config import CONFIDENCE_THRESHOLD, DEMO_DB, DEMO_TODAY

# --------------------------------------------------------------------------
# Constantes de reglas
# --------------------------------------------------------------------------
RESOLVED, CLARIFY, ESCALATED, GREETING = "resuelto", "aclaracion", "derivado", "saludo"

GREETING_WORDS = {
    "hola", "buenas", "buenos", "dias", "tardes", "noches", "gracias", "muchas", "adios", "chau", "hey",
    "ok", "vale", "listo", "perfecto", "genial", "buen", "dia", "saludos", "hasta", "luego", "muy", "amable",
}
HUMAN_NOUN = r"(persona|humano|humana|operador|operadora|asesor|asesora|agente|representante|ejecutivo|ejecutiva|alguien del equipo|gerente)"
HUMAN_VERB = r"(hablar|pasa|pasar|pasame|comunic\w*|atencion|necesito|quiero|contactar|derivar|derivame|transferir)"
EMOTION_RE = re.compile(
    r"\b(inaceptable|harto|harta|pesim[oa]|estafa|verguenza|horrible|furios[oa]|molest[oa]|denunci\w*|exijo|"
    r"indignante|fatal|nadie da la cara|nadie me responde|nadie responde|jamas vuelvo|lamentable|inutiles?|ladrones)\b"
)
INVOICE_RE = re.compile(r"\b(factura|boleta|comprobante|ruc)\b")
INVOICE_ACTION_RE = re.compile(
    r"(reenv\w*|reemit\w*|corrig\w*|duplicado|otra factura|nueva factura|cambiar|modific\w*|equivocad\w*|"
    r"no me llego|no recibi|a nombre de)"
)
CANCEL_RE = re.compile(r"\b(cancel\w*|anul\w*)\b")
CANCEL_OBJ_RE = re.compile(r"\b(pedido|compra|orden|ped-?\s?\d{4})\b")

ORDER_RE_1 = re.compile(r"\bped[-\s]?(\d{4})\b")
ORDER_RE_2 = re.compile(r"\b(?:pedido|orden|compra|numero|nro|n°|#)\s*(?:de\s*)?(\d{4})\b")
SIZE_RE = re.compile(r"\b(?:talla|numero|del|en)\s*(xxl|xl|xs|s|m|l|\d{2})\b|\b(xxl|xl)\b")

# Palabras clave por modelo del catálogo demo (para reconocer el producto en el texto).
MODEL_KEYWORDS = {
    "Chaqueta Denim Urbana": ["chaqueta", "denim", "vaquera"],
    "Vestido de Lino Verano": ["vestido", "lino"],
    "Camisa Oxford Clásica": ["camisa", "oxford"],
    "Pantalón Cargo Utility": ["pantalon", "cargo"],
    "Sudadera Oversize Studio": ["sudadera", "oversize", "hoodie"],
    "Zapatillas Canvas Retro": ["zapatillas", "canvas", "tenis"],
    "Bolso Tote Artesanal": ["bolso", "tote"],
    "Abrigo de Lana Nórdico": ["abrigo", "lana"],
}

RETURN_WINDOW_DAYS = 14  # política FICTICIA de la tienda demo
CURRENCY = "S/"

MENU = (
    "Puedo ayudarte con: estado de pedidos, disponibilidad de productos, devoluciones, métodos de pago y descuentos."
)


def _today() -> date:
    return date.fromisoformat(DEMO_TODAY)


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y")


# --------------------------------------------------------------------------
# Extracción de entidades (basada en reglas)
# --------------------------------------------------------------------------
def extract_order_code(norm: str) -> str | None:
    m = ORDER_RE_1.search(norm) or ORDER_RE_2.search(norm)
    return f"PED-{m.group(1)}" if m else None


def extract_size(norm: str) -> str | None:
    m = SIZE_RE.search(norm)
    if not m:
        return None
    s = m.group(1) or m.group(2)
    return s.upper() if not s.isdigit() else s


def extract_color(norm: str, colors: set[str]) -> str | None:
    for c in sorted(colors):
        if re.search(rf"\b{re.escape(normalize(c))}\b", norm):
            return c
    return None


def match_model(norm: str, models: list[str]) -> tuple[list[str], int]:
    """Devuelve (modelos empatados con mayor puntaje, puntaje). Tolera errores ortográficos leves."""
    import difflib

    tokens = re.findall(r"[a-z0-9]+", norm)
    best, best_score = [], 0
    for model in models:
        kws = MODEL_KEYWORDS.get(model, [normalize(model)])
        score = 0
        for kw in kws:
            if kw in tokens or (len(kw) >= 5 and difflib.get_close_matches(kw, tokens, n=1, cutoff=0.82)):
                score += 1
        if score > best_score:
            best, best_score = [model], score
        elif score == best_score and score > 0:
            best.append(model)
    return best, best_score


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------
class ChatbotEngine:
    def __init__(self, db_path=DEMO_DB, classifier: IntentClassifier | None = None,
                 threshold: float = CONFIDENCE_THRESHOLD):
        self.db_path = db_path
        self.classifier = classifier or get_classifier()
        self.threshold = threshold
        self._pending: dict[str, str] = {}
        self._lock = threading.Lock()

    # -- API pública ------------------------------------------------------
    def respond(self, session_id: str, text: str, log: bool = True) -> dict:
        t0 = time.perf_counter()
        original = text
        norm = normalize(text)
        intent, conf, probs = self.classifier.predict(text)
        conn = get_conn(self.db_path)
        try:
            outcome, reason, reply, used_intent = self._decide(conn, session_id, original, norm, intent, conf)
            response_ms = (time.perf_counter() - t0) * 1000.0  # excluye el registro en BD
            ticket_id = None
            if log:
                ticket_id = self._log(conn, session_id, original, used_intent, conf, outcome, reason, response_ms, reply)
                if outcome == ESCALATED and ticket_id:
                    reply = f"{reply} (Ticket #{ticket_id})"
        finally:
            conn.close()
        return {
            "reply": reply,
            "intent": used_intent,
            "classifier_intent": intent,
            "confidence": round(conf, 4),
            "outcome": outcome,
            "reason": reason,
            "response_ms": round(response_ms, 3),
            "ticket_id": ticket_id,
        }

    # -- Lógica de decisión -----------------------------------------------
    def _decide(self, conn, session_id, original, norm, intent, conf):
        words = re.findall(r"[a-z0-9]+", norm)

        # 1. Saludo / agradecimiento
        if words and len(words) <= 5 and all(w in GREETING_WORDS for w in words):
            reply = ("¡Hola! Soy el asistente virtual de la tienda demo. " + MENU
                     if any(w in ("hola", "buenas", "buenos", "hey", "saludos") for w in words)
                     else "¡Con gusto! Si necesitas algo más, escríbeme.")
            return GREETING, "saludo", reply, None

        # 2. Relleno de dato pendiente
        with self._lock:
            pending = self._pending.get(session_id)
        if pending and len(words) <= 6 and (extract_order_code(norm) or self._has_product_entity(conn, norm)):
            intent, conf = pending, 1.0
            reason_fill = "relleno_dato_pendiente"
        else:
            reason_fill = None

        # 3. Reglas de derivación
        if reason_fill is None:
            if self._wants_human(norm, words):
                return self._escalate(session_id, "solicita_humano", intent,
                                      "Claro, te derivo con una persona del equipo para que te atienda.")
            if EMOTION_RE.search(norm) or self._is_shouting(original):
                return self._escalate(session_id, "lenguaje_emocional", intent,
                                      "Lamento la molestia. Para atender tu caso con el cuidado que merece, "
                                      "te derivo con una persona del equipo.")
            if INVOICE_RE.search(norm) and INVOICE_ACTION_RE.search(norm):
                return self._escalate(session_id, "accion_requiere_operador", intent,
                                      "Los cambios o reenvíos de comprobantes los gestiona una persona del equipo. "
                                      "Te derivo con un operador.")
            if CANCEL_RE.search(norm) and CANCEL_OBJ_RE.search(norm) and not re.search(r"cancel\w* con\b", norm):
                return self._escalate(session_id, "accion_requiere_operador", intent,
                                      "Las cancelaciones de pedidos las gestiona una persona del equipo. "
                                      "Te derivo con un operador.")

            # 4. Confianza insuficiente
            if conf < self.threshold:
                return self._escalate(session_id, "baja_confianza", intent,
                                      "No estoy seguro de haber entendido tu consulta, así que prefiero derivarte "
                                      "con una persona del equipo.")

        # 5. Módulos de respuesta
        handler = {
            "estado_pedido": self._h_order_status,
            "disponibilidad": self._h_availability,
            "devoluciones": self._h_returns,
            "pagos": self._h_payments,
            "descuentos": self._h_discounts,
        }[intent]
        outcome, reply, needs_slot = handler(conn, norm, original)
        with self._lock:
            if outcome == CLARIFY and needs_slot:
                self._pending[session_id] = intent
            else:
                self._pending.pop(session_id, None)
        return outcome, reason_fill or ("falta_dato" if outcome == CLARIFY else "modulo_respuesta"), reply, intent

    def _escalate(self, session_id, reason, intent, message):
        with self._lock:
            self._pending.pop(session_id, None)
        return ESCALATED, reason, message, intent

    @staticmethod
    def _wants_human(norm, words) -> bool:
        if re.search(HUMAN_NOUN, norm) and re.search(HUMAN_VERB, norm):
            return True
        return len(words) <= 3 and bool(re.search(HUMAN_NOUN, norm))

    @staticmethod
    def _is_shouting(original) -> bool:
        letters = [c for c in original if c.isalpha()]
        return len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7

    def _has_product_entity(self, conn, norm) -> bool:
        models = [r["model"] for r in conn.execute("SELECT DISTINCT model FROM products")]
        return match_model(norm, models)[1] > 0

    # -- Módulos de respuesta --------------------------------------------
    def _h_order_status(self, conn, norm, original):
        code = extract_order_code(norm)
        if not code:
            return CLARIFY, "Con gusto reviso tu pedido. ¿Me indicas el código (formato PED-1234)?", True
        o = conn.execute("SELECT * FROM orders WHERE order_code = ?", (code,)).fetchone()
        if not o:
            return CLARIFY, f"No encuentro el pedido {code}. Verifica el código (formato PED-1234) e inténtalo de nuevo.", True
        st = o["status"]
        if re.search(r"\b(direccion|domicilio)\b", norm) and re.search(r"(cambi|modific|corregir|actualiz)", norm):
            if st == "procesando":
                msg = (f"{code} aún está en preparación, por lo que la dirección todavía puede modificarse. "
                       "Escribe «hablar con un operador» para que lo gestionen.")
            elif st in ("enviado", "en_reparto"):
                msg = (f"{code} ya fue despachado con {o['carrier']}; no podemos cambiar la dirección desde aquí. "
                       f"Puedes coordinar con el courier usando el tracking {o['tracking']}.")
            else:
                msg = f"{code} está {st.replace('_', ' ')}; ya no admite cambio de dirección."
            return RESOLVED, msg, False
        if re.search(r"(seguimiento|rastre\w*|tracking|courier|transportista|recorrido)", norm):
            if o["tracking"]:
                return RESOLVED, f"{code} viaja con {o['carrier']}. Código de seguimiento: {o['tracking']}.", False
            return RESOLVED, f"{code} aún no tiene código de seguimiento porque todavía no fue despachado.", False
        if st == "procesando":
            msg = f"{code} está en preparación. Fecha estimada de entrega: {_fmt_date(o['eta'])}."
        elif st == "enviado":
            msg = (f"{code} fue despachado con {o['carrier']} (tracking {o['tracking']}). "
                   f"Llegada estimada: {_fmt_date(o['eta'])}.")
        elif st == "en_reparto":
            msg = f"{code} está en reparto hoy con {o['carrier']} (tracking {o['tracking']})."
        elif st == "entregado":
            msg = f"{code} figura como entregado el {_fmt_date(o['delivered_at'])}."
        else:
            msg = f"{code} fue cancelado. Estado del pago: {o['payment_status']}."
        return RESOLVED, msg, False

    def _h_availability(self, conn, norm, original):
        models = [r["model"] for r in conn.execute("SELECT DISTINCT model FROM products")]
        found, score = match_model(norm, models)
        if score == 0:
            names = ", ".join(sorted(models))
            return CLARIFY, f"¿De qué producto quieres saber? Tenemos: {names}.", True
        if len(found) > 1:
            return CLARIFY, "¿A cuál te refieres: " + " o ".join(found) + "?", True
        model = found[0]
        rows = conn.execute("SELECT * FROM products WHERE model = ?", (model,)).fetchall()
        colors = {r["color"] for r in rows}
        color = extract_color(norm, colors | {"azul", "negro", "blanco", "gris", "rojo", "verde", "beige", "camel",
                                               "celeste", "oliva", "burdeos", "natural"})
        size = extract_size(norm)
        sel = [r for r in rows if (color is None or r["color"] == color) and (size is None or r["size"].upper() == size.upper())]
        if color and color not in colors:
            return RESOLVED, f"{model} no se ofrece en {color}. Colores disponibles: {', '.join(sorted(colors))}.", False
        if size and not any(r["size"].upper() == size.upper() for r in rows):
            return RESOLVED, f"{model} no se ofrece en talla {size}. Tallas: {', '.join(dict.fromkeys(r['size'] for r in rows))}.", False
        in_stock = [r for r in sel if r["stock"] > 0]
        if color and size:
            r = sel[0]
            msg = (f"{model} en {color}, talla {size}: {r['stock']} unidades disponibles." if r["stock"] > 0
                   else f"{model} en {color}, talla {size}: agotado por ahora.")
            return RESOLVED, msg, False
        if not in_stock:
            return RESOLVED, f"{model}: por ahora no hay stock con esos filtros.", False
        by_color: dict[str, list[str]] = {}
        for r in in_stock:
            by_color.setdefault(r["color"], []).append(f"{r['size']} ({r['stock']})")
        detail = "; ".join(f"{c}: {', '.join(s)}" for c, s in by_color.items())
        price = rows[0]["price"]
        return RESOLVED, f"{model} ({CURRENCY}{price:.2f}). Disponible en → {detail}.", False

    def _h_returns(self, conn, norm, original):
        base = (f"Puedes devolver o cambiar un artículo dentro de {RETURN_WINDOW_DAYS} días desde la entrega, "
                "sin uso y con etiquetas. Completa el formulario de devolución (/formulario-devolucion), "
                "envíanos el paquete y te reembolsaremos en 7 días hábiles tras recibirlo.")
        code = extract_order_code(norm)
        if code:
            o = conn.execute("SELECT * FROM orders WHERE order_code = ?", (code,)).fetchone()
            if not o:
                return CLARIFY, f"No encuentro el pedido {code}. Verifica el código (formato PED-1234).", True
            if o["status"] != "entregado":
                return RESOLVED, f"{code} está {o['status'].replace('_', ' ')}; podrás devolverlo una vez que lo recibas. {base}", False
            days = (_today() - date.fromisoformat(o["delivered_at"])).days
            if days <= RETURN_WINDOW_DAYS:
                return RESOLVED, f"{code} se entregó hace {days} días, así que está dentro del plazo. {base}", False
            return RESOLVED, (f"{code} se entregó hace {days} días y superó el plazo de {RETURN_WINDOW_DAYS}. "
                              "Si el artículo llegó con defecto, escribe «hablar con un operador».")  , False
        return RESOLVED, base, False

    def _h_payments(self, conn, norm, original):
        code = extract_order_code(norm)
        if code:
            o = conn.execute("SELECT * FROM orders WHERE order_code = ?", (code,)).fetchone()
            if not o:
                return CLARIFY, f"No encuentro el pedido {code}. Verifica el código (formato PED-1234).", True
            return RESOLVED, f"El pago de {code} ({o['payment_method'].replace('_', ' ')}) figura como {o['payment_status']}.", False
        if re.search(r"(acredit\w*|\bpague\b|pagado|se refleja|reflej\w*|recibieron)", norm):
            return CLARIFY, "Para verificar tu pago necesito el código del pedido (formato PED-1234).", True
        return RESOLVED, ("Aceptamos tarjeta de crédito/débito (Visa y Mastercard), PayPal, transferencia bancaria y "
                          "pago contra reembolso. Los datos para transferir se muestran al finalizar la compra, y "
                          "recibirás un correo de confirmación y tu comprobante electrónico cuando se acredite el pago."), False

    def _h_discounts(self, conn, norm, original):
        today = _today().isoformat()
        coupons = conn.execute("SELECT * FROM coupons").fetchall()
        mentioned = [c for c in coupons if normalize(c["code"]) in norm]
        parts: list[str] = []
        for c in mentioned:
            vigente = c["valid_until"] >= today
            est = f"vigente hasta {_fmt_date(c['valid_until'])}" if vigente else f"venció el {_fmt_date(c['valid_until'])}"
            pct = f"{c['percent']:.0f}% de descuento" if c["percent"] else "envío gratis"
            parts.append(f"{c['code']}: {pct}, compra mínima {CURRENCY}{c['min_purchase']:.0f}, {est}.")
        if re.search(r"(combin\w*|acumul\w*|junt\w*|suma\w*|a la vez|mismo tiempo|otro (codigo|cupon))", norm):
            parts.append("Los cupones de porcentaje no son acumulables entre sí; ENVIOGRATIS sí se puede combinar con uno de ellos.")
        elif not mentioned:
            if re.search(r"(minim\w*|monto)", norm):
                parts.append("Compra mínima: VERANO15 " + f"{CURRENCY}80, ENVIOGRATIS {CURRENCY}100, FIEL20 {CURRENCY}150; BIENVENIDA10 sin mínimo.")
            elif re.search(r"\b(como|donde)\b.*(aplic\w*|us\w*|coloc\w*|ingres\w*|canje\w*)", norm):
                parts.append("Ingresa el código en el campo «Cupón» del carrito y pulsa «Aplicar» antes de pagar.")
            else:
                vig = [c for c in coupons if c["valid_until"] >= today]
                lst = "; ".join(f"{c['code']} ({c['description'].lower()}, mínimo {CURRENCY}{c['min_purchase']:.0f})" for c in vig)
                parts.append(f"Promociones vigentes: {lst}. Ingrésalos en el carrito antes de pagar.")
        return RESOLVED, " ".join(parts), False

    # -- Registro ---------------------------------------------------------
    def _log(self, conn, session_id, text, intent, conf, outcome, reason, response_ms, reply):
        cur = conn.execute(
            "INSERT INTO interactions (session_id, ts, user_message, intent, confidence, outcome, reason, response_ms, reply)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, datetime.now().isoformat(timespec="seconds"), text, intent, conf, outcome, reason, response_ms, reply),
        )
        iid = cur.lastrowid
        ticket = None
        if outcome == ESCALATED:
            c2 = conn.execute(
                "INSERT INTO operator_queue (interaction_id, created_at, reason) VALUES (?,?,?)",
                (iid, datetime.now().isoformat(timespec="seconds"), reason),
            )
            ticket = c2.lastrowid
        conn.commit()
        return ticket
