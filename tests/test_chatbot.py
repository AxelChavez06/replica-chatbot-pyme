import pytest

from app.chatbot import extract_order_code, extract_size, match_model
from app.db import get_conn
from app.nlu import normalize


def status_of(conn, code):
    return conn.execute("SELECT status FROM orders WHERE order_code=?", (code,)).fetchone()[0]


def test_entity_extraction():
    assert extract_order_code(normalize("estado de PED-1010 gracias")) == "PED-1010"
    assert extract_order_code(normalize("mi pedido 1022 no llega")) == "PED-1022"
    assert extract_order_code(normalize("hola")) is None
    assert extract_size(normalize("en talla M por favor")) == "M"
    assert extract_size(normalize("numero 40")) == "40"
    models = ["Chaqueta Denim Urbana", "Camisa Oxford Clásica"]
    found, score = match_model(normalize("tienen la chaqueta denim?"), models)
    assert found == ["Chaqueta Denim Urbana"] and score == 2
    found, _ = match_model(normalize("tienen la chaketa denim"), models)
    assert found == ["Chaqueta Denim Urbana"]


def test_order_status_uses_database(engine, conn):
    r = engine.respond("s1", "¿Cuál es el estado actual de PED-1004?")
    assert r["outcome"] == "resuelto" and r["intent"] == "estado_pedido"
    st = status_of(conn, "PED-1004")
    expected = {"procesando": "preparación", "enviado": "despachado", "en_reparto": "reparto",
                "entregado": "entregado", "cancelado": "cancelado"}[st]
    assert expected in r["reply"]


def test_unknown_order_asks_again(engine):
    r = engine.respond("s1", "¿Dónde está mi pedido PED-9999?")
    assert r["outcome"] == "aclaracion" and "PED-9999" in r["reply"]


def test_missing_order_code_then_slot_filling(engine):
    r1 = engine.respond("s2", "¿Mi encomienda ya está en camino?")
    assert r1["outcome"] == "aclaracion"
    r2 = engine.respond("s2", "PED-1003")
    assert r2["outcome"] == "resuelto" and r2["reason"] == "relleno_dato_pendiente" and "PED-1003" in r2["reply"]


def test_availability(engine):
    r = engine.respond("s3", "¿Tienen la chaqueta denim en talla M?")
    assert r["outcome"] == "resuelto" and r["intent"] == "disponibilidad" and "Chaqueta Denim" in r["reply"]
    r = engine.respond("s3", "¿Tienen talla M disponible?")
    assert r["outcome"] == "aclaracion"


def test_returns_payments_discounts(engine):
    r = engine.respond("s4", "¿Cómo puedo devolver una prenda?")
    assert r["intent"] == "devoluciones" and "formulario" in r["reply"].lower()
    r = engine.respond("s4", "¿Qué métodos de pago aceptan?")
    assert r["intent"] == "pagos" and "PayPal" in r["reply"]
    r = engine.respond("s4", "¿Sigue valiendo el cupón VERANO15?")
    assert r["intent"] == "descuentos" and "VERANO15" in r["reply"]
    r = engine.respond("s4", "¿Se pueden usar dos cupones a la vez?")
    assert "no son acumulables" in r["reply"]


@pytest.mark.parametrize("text,reason", [
    ("Quiero hablar con una persona, no con un bot", "solicita_humano"),
    ("Esto es inaceptable, nadie me responde", "lenguaje_emocional"),
    ("Necesito que me reenvíen la factura de mi compra PED-1002", "accion_requiere_operador"),
    ("Quiero cancelar mi pedido PED-1002", "accion_requiere_operador"),
])
def test_escalation_rules_create_ticket(engine, db_path, text, reason):
    r = engine.respond("s5", text)
    assert r["outcome"] == "derivado" and r["reason"] == reason and r["ticket_id"]
    assert "Ticket #" in r["reply"]
    c = get_conn(db_path)
    row = c.execute("SELECT reason, status FROM operator_queue WHERE id=?", (r["ticket_id"],)).fetchone()
    c.close()
    assert row["reason"] == reason and row["status"] == "pendiente"


def test_low_confidence_escalates(engine):
    r = engine.respond("s6", "¿Cuál es la capital de Francia?")
    assert r["outcome"] == "derivado"


def test_greeting_is_not_a_query(engine):
    r = engine.respond("s7", "hola")
    assert r["outcome"] == "saludo" and r["intent"] is None


def test_interactions_are_logged(engine, db_path):
    engine.respond("s8", "¿Aceptan PayPal?")
    engine.respond("s8", "¿Aceptan PayPal?", log=False)
    c = get_conn(db_path)
    assert c.execute("SELECT COUNT(*) FROM interactions WHERE session_id='s8'").fetchone()[0] == 1
    c.close()
