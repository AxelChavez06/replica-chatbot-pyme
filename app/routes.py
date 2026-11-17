"""Rutas HTTP: interfaz del chatbot, API y panel de indicadores."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_from_directory

from analysis import paper_data as P
from app.db import get_conn
from config import INTENT_LABELS

bp = Blueprint("main", __name__)

SAMPLE_QUERIES = [
    ("Estado de pedido", "¿Dónde está mi pedido PED-1003?"),
    ("Estado de pedido", "¿Puedo cambiar la dirección de entrega de PED-1002?"),
    ("Disponibilidad", "¿Tienen la chaqueta denim en talla M?"),
    ("Disponibilidad", "¿En qué colores viene el abrigo de lana?"),
    ("Devoluciones", "¿Cómo puedo devolver una prenda?"),
    ("Pagos", "¿Qué métodos de pago aceptan?"),
    ("Descuentos", "¿Puedo combinar dos cupones?"),
    ("Derivación", "Quiero hablar con una persona"),
    ("Derivación", "¡Esto es inaceptable, nadie me responde!"),
    ("Aclaración", "¿Mi pedido ya está en camino?"),
]


def _engine():
    return current_app.extensions["engine"]


def _paper_summary() -> dict:
    t = P.TABLE1
    pre = slice(0, P.POST_START_INDEX)
    post = slice(P.POST_START_INDEX, None)
    mean = statistics.fmean
    handled_pct = [h / n * 100 for h, n in zip(t["handled_by_chatbot"][post], t["total_inquiries"][post])]
    esc_pct = [e / n * 100 for e, n in zip(t["escalated"][post], t["total_inquiries"][post])]
    return {
        "fuente": "Datos publicados en Marcineková et al., Information 2025, 16, 1078",
        "tiempo_respuesta_min": {"antes": mean(t["avg_response_min"][pre]), "despues": mean(t["avg_response_min"][post])},
        "satisfaccion": {"antes": mean(t["satisfaction"][pre]), "despues": mean(t["satisfaction"][post])},
        "consultas_mes": {"antes": mean(t["total_inquiries"][pre]), "despues": mean(t["total_inquiries"][post])},
        "pct_atendidas_chatbot_prom_feb_abr": mean(handled_pct),
        "pct_derivadas_prom_feb_abr": mean(esc_pct),
        "pct_derivadas_abril": esc_pct[-1],
        "pct_derivadas_texto_articulo": list(P.PAPER_ESCALATION_RANGE_PCT),
        "meses": P.MONTH_LABELS,
        "mensual": {
            "chatbot": t["handled_by_chatbot"],
            "derivadas": t["escalated"],
            "satisfaccion": t["satisfaction"],
            "tiempo_min": t["avg_response_min"],
        },
    }


def _load_experiment() -> dict | None:
    f = Path(current_app.config["RESULTS_DIR"]) / "experiment" / "metrics.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def _comparison(paper: dict, exp: dict | None) -> list[dict]:
    rows = [
        {
            "indicador": "Consultas atendidas automáticamente",
            "articulo": f"{paper['pct_atendidas_chatbot_prom_feb_abr']:.1f}% (prom. feb–abr, clientes reales)",
            "prototipo": f"{exp['resultados']['pct_resueltas_automaticamente']:.1f}% (consultas sintéticas)" if exp else "—",
            "comparable": "No directamente: la mezcla de consultas sintéticas la definimos nosotros.",
        },
        {
            "indicador": "Consultas derivadas a humano",
            "articulo": (f"{paper['pct_derivadas_prom_feb_abr']:.1f}% (prom. feb–abr); abril {paper['pct_derivadas_abril']:.1f}%; "
                         "el texto menciona 10–15%"),
            "prototipo": f"{exp['resultados']['pct_derivadas']:.1f}% (consultas sintéticas)" if exp else "—",
            "comparable": "No directamente: incluimos adrede casos difíciles (emocionales, fuera de alcance).",
        },
        {
            "indicador": "Tiempo de respuesta",
            "articulo": f"{paper['tiempo_respuesta_min']['antes']:.2f} → {paper['tiempo_respuesta_min']['despues']:.2f} min (humano + bot)",
            "prototipo": f"{exp['latencia_ms']['mediana']:.1f} ms (mediana, procesamiento del servidor)" if exp else "—",
            "comparable": "No: el artículo mide tiempo hasta la respuesta con personas en el circuito; nosotros, latencia de software.",
        },
        {
            "indicador": "Satisfacción del cliente (1–5)",
            "articulo": f"{paper['satisfaccion']['antes']:.2f} → {paper['satisfaccion']['despues']:.2f}",
            "prototipo": "No medida",
            "comparable": "No: no hay clientes reales ni encuestas en este proyecto.",
        },
        {
            "indicador": "Exactitud de clasificación de intenciones",
            "articulo": "No informada en el artículo",
            "prototipo": f"{exp['clasificacion']['exactitud_intenciones'] * 100:.1f}% (consultas sintéticas)" if exp else "—",
            "comparable": "Métrica propia de nuestras pruebas.",
        },
    ]
    return rows


# ------------------------------------------------------------------ páginas
@bp.get("/")
def index():
    return render_template("chat.html", samples=SAMPLE_QUERIES)


@bp.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@bp.get("/formulario-devolucion")
def return_form():
    return render_template("return_form.html")


@bp.get("/results/<path:filename>")
def results_file(filename):
    root = Path(current_app.config["RESULTS_DIR"])
    if not (root / filename).resolve().is_relative_to(root.resolve()):
        abort(404)
    if filename.endswith((".db",)):
        abort(404)
    return send_from_directory(root, filename)


# ------------------------------------------------------------------ API
@bp.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    session_id = str(data.get("session_id") or "anon")[:64]
    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío."}), 400
    if len(message) > 500:
        return jsonify({"error": "El mensaje es demasiado largo (máx. 500 caracteres)."}), 400
    res = _engine().respond(session_id, message)
    res["intent_label"] = INTENT_LABELS.get(res["intent"]) if res["intent"] else None
    return jsonify(res)


@bp.get("/api/metrics/live")
def api_live():
    conn = get_conn(current_app.config["DB_PATH"])
    try:
        rows = conn.execute("SELECT outcome, COUNT(*) n FROM interactions GROUP BY outcome").fetchall()
        outcomes = {r["outcome"]: r["n"] for r in rows}
        counted = sum(v for k, v in outcomes.items() if k != "saludo")
        ms = [r["response_ms"] for r in conn.execute("SELECT response_ms FROM interactions WHERE outcome != 'saludo'")]
        by_intent = {r["intent"]: r["n"] for r in conn.execute(
            "SELECT intent, COUNT(*) n FROM interactions WHERE intent IS NOT NULL AND outcome != 'saludo' GROUP BY intent")}
        reasons = {r["reason"]: r["n"] for r in conn.execute(
            "SELECT reason, COUNT(*) n FROM interactions WHERE outcome='derivado' GROUP BY reason")}
        return jsonify({
            "total_consultas": counted,
            "resueltas": outcomes.get("resuelto", 0),
            "aclaraciones": outcomes.get("aclaracion", 0),
            "derivadas": outcomes.get("derivado", 0),
            "pct_resueltas": 100 * outcomes.get("resuelto", 0) / counted if counted else None,
            "pct_derivadas": 100 * outcomes.get("derivado", 0) / counted if counted else None,
            "latencia_ms_media": statistics.fmean(ms) if ms else None,
            "por_intencion": by_intent,
            "motivos_derivacion": reasons,
            "nota": "Interacciones tecleadas en esta demo; no son una muestra ni clientes reales.",
        })
    finally:
        conn.close()


@bp.get("/api/operator-queue")
def api_queue():
    conn = get_conn(current_app.config["DB_PATH"])
    try:
        rows = conn.execute(
            "SELECT q.id, q.created_at, q.reason, q.status, i.user_message FROM operator_queue q "
            "JOIN interactions i ON i.id = q.interaction_id ORDER BY q.id DESC LIMIT 15").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@bp.get("/api/experiment")
def api_experiment():
    paper = _paper_summary()
    exp = _load_experiment()
    return jsonify({"paper": paper, "experiment": exp, "comparison": _comparison(paper, exp)})
