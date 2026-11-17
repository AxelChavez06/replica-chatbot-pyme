import pytest

from app import create_app


@pytest.fixture()
def client(db_path, clf, tmp_path):
    app = create_app(db_path=db_path, classifier=clf, results_dir=tmp_path)
    app.testing = True
    return app.test_client()


def test_pages_render(client):
    assert client.get("/").status_code == 200
    assert client.get("/dashboard").status_code == 200
    assert client.get("/formulario-devolucion").status_code == 200


def test_chat_endpoint(client):
    r = client.post("/api/chat", json={"session_id": "x", "message": "¿Qué métodos de pago aceptan?"})
    d = r.get_json()
    assert r.status_code == 200 and d["outcome"] == "resuelto" and d["intent_label"] == "Métodos de pago"
    assert d["response_ms"] >= 0


def test_chat_validation(client):
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400
    assert client.post("/api/chat", json={"message": "a" * 501}).status_code == 400
    assert client.post("/api/chat", data="no json").status_code == 400


def test_live_metrics_and_queue(client):
    client.post("/api/chat", json={"session_id": "x", "message": "¿Aceptan PayPal?"})
    client.post("/api/chat", json={"session_id": "x", "message": "Quiero hablar con una persona"})
    m = client.get("/api/metrics/live").get_json()
    assert m["total_consultas"] == 2 and m["derivadas"] == 1
    q = client.get("/api/operator-queue").get_json()
    assert len(q) == 1 and q[0]["reason"] == "solicita_humano"


def test_experiment_endpoint_without_results(client):
    d = client.get("/api/experiment").get_json()
    assert d["experiment"] is None and len(d["comparison"]) == 5
    assert d["paper"]["pct_atendidas_chatbot_prom_feb_abr"] == pytest.approx(74.2, abs=0.01)


def test_results_path_traversal_and_db_blocked(client):
    assert client.get("/results/../app/routes.py").status_code in (308, 404)
    assert client.get("/results/experiment/experiment.db").status_code == 404
