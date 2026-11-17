from app.db import get_conn, init_db


def test_seed_counts(conn):
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 30
    assert conn.execute("SELECT COUNT(*) FROM coupons").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(DISTINCT model) FROM products").fetchone()[0] == 8
    statuses = {r[0] for r in conn.execute("SELECT DISTINCT status FROM orders")}
    assert {"procesando", "enviado", "en_reparto", "entregado", "cancelado"} <= statuses


def test_seed_is_deterministic(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    init_db(a)
    init_db(b)
    q = "SELECT order_code,status,eta,delivered_at,total FROM orders ORDER BY id"
    ca, cb = get_conn(a), get_conn(b)
    assert [tuple(r) for r in ca.execute(q)] == [tuple(r) for r in cb.execute(q)]
    ca.close()
    cb.close()
