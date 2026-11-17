"""Base de datos SQLite simulada: productos, pedidos, cupones e interacciones."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from config import DEMO_TODAY

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    color TEXT NOT NULL,
    size TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    order_code TEXT UNIQUE NOT NULL,
    customer TEXT NOT NULL,
    status TEXT NOT NULL,            -- procesando | enviado | en_reparto | entregado | cancelado
    created_at TEXT NOT NULL,
    eta TEXT,                        -- fecha estimada de entrega
    delivered_at TEXT,
    carrier TEXT,
    tracking TEXT,
    payment_method TEXT NOT NULL,
    payment_status TEXT NOT NULL,    -- confirmado | pendiente | reembolsado
    total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS coupons (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    percent REAL,
    min_purchase REAL NOT NULL,
    valid_until TEXT NOT NULL,
    combinable INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    user_message TEXT NOT NULL,
    intent TEXT,
    confidence REAL,
    outcome TEXT NOT NULL,           -- resuelto | aclaracion | derivado | saludo
    reason TEXT,
    response_ms REAL NOT NULL,
    reply TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    created_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendiente'
);
"""

# (modelo, [colores], [tallas], precio)
_CATALOG = [
    ("Chaqueta Denim Urbana", ["azul", "negro"], ["S", "M", "L"], 129.90),
    ("Vestido de Lino Verano", ["beige", "blanco", "verde"], ["S", "M", "L"], 99.90),
    ("Camisa Oxford Clásica", ["blanco", "celeste"], ["S", "M", "L", "XL"], 69.90),
    ("Pantalón Cargo Utility", ["negro", "oliva"], ["M", "L", "XL"], 89.90),
    ("Sudadera Oversize Studio", ["gris", "negro", "burdeos"], ["S", "M", "L"], 79.90),
    ("Zapatillas Canvas Retro", ["blanco", "rojo", "negro"], ["38", "40", "42"], 74.90),
    ("Bolso Tote Artesanal", ["natural", "negro"], ["único"], 59.90),
    ("Abrigo de Lana Nórdico", ["camel", "gris"], ["S", "M", "L"], 189.90),
]

_STATUSES = ["procesando", "enviado", "en_reparto", "entregado", "entregado", "cancelado"]
_PAYMENTS = ["tarjeta", "paypal", "transferencia", "contra_reembolso"]
_CARRIERS = ["Courier Express", "Envíos Rápidos", "Correo Nacional"]
_NAMES = ["Lucía", "Marco", "Valeria", "Diego", "Camila", "Andrés", "Sofía", "Mateo", "Renata", "Javier"]

_COUPONS = [
    ("BIENVENIDA10", "10% en tu primera compra", 10.0, 0.0, "2025-12-31", 0),
    ("VERANO15", "15% en toda la tienda", 15.0, 80.0, "2025-06-30", 0),
    ("ENVIOGRATIS", "Envío gratis", None, 100.0, "2025-12-31", 1),
    ("FIEL20", "20% para clientes frecuentes", 20.0, 150.0, "2025-03-31", 0),
]


def get_conn(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | Path, reset: bool = True) -> None:
    """Crea y rellena la base de datos de forma 100% determinista (sin aleatoriedad)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()
    conn = get_conn(path)
    conn.executescript(SCHEMA)
    today = date.fromisoformat(DEMO_TODAY)

    # Productos (cada fila = variante color/talla). Stock determinista; algunas variantes agotadas.
    products = []
    pid = 1
    for mi, (model, colors, sizes, price) in enumerate(_CATALOG):
        for ci, color in enumerate(colors):
            for si, size in enumerate(sizes):
                stock = (mi * 7 + ci * 5 + si * 3) % 9  # 0..8
                products.append((pid, f"SKU-{pid:03d}", model, color, size, price, stock))
                pid += 1
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?)", products)

    # Pedidos PED-1001 .. PED-1030
    for i in range(30):
        code = f"PED-{1001 + i}"
        status = _STATUSES[i % len(_STATUSES)]
        created = today - timedelta(days=(i * 2) % 25 + 2)
        carrier = _CARRIERS[i % len(_CARRIERS)] if status in ("enviado", "en_reparto", "entregado") else None
        tracking = f"TRK{880000 + i * 37}" if carrier else None
        eta = None
        delivered = None
        if status in ("procesando", "enviado", "en_reparto"):
            eta = (today + timedelta(days={"procesando": 5, "enviado": 3, "en_reparto": 0}[status])).isoformat()
        if status == "entregado":
            delivered = (today - timedelta(days=(i * 3) % 24)).isoformat()
            if delivered < created.isoformat():
                delivered = created.isoformat()
        payment_status = "reembolsado" if status == "cancelado" else ("pendiente" if (i % 11 == 10 and status == "procesando") else "confirmado")
        pm = _PAYMENTS[i % len(_PAYMENTS)]
        n_items = 1 + i % 3
        items = []
        total = 0.0
        for k in range(n_items):
            prod = products[(i * 5 + k * 11) % len(products)]
            items.append((prod[0], 1 + (i + k) % 2))
            total += prod[5] * (1 + (i + k) % 2)
        cur = conn.execute(
            "INSERT INTO orders (order_code, customer, status, created_at, eta, delivered_at, carrier, tracking,"
            " payment_method, payment_status, total) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (code, _NAMES[i % len(_NAMES)], status, created.isoformat(), eta, delivered, carrier, tracking,
             pm, payment_status, round(total, 2)),
        )
        for prod_id, qty in items:
            conn.execute("INSERT INTO order_items (order_id, product_id, qty) VALUES (?,?,?)", (cur.lastrowid, prod_id, qty))

    conn.executemany("INSERT INTO coupons VALUES (?,?,?,?,?,?)", _COUPONS)
    conn.commit()
    conn.close()


def catalog_models() -> list[dict]:
    """Catálogo con modelos y alias (usado por el extractor de entidades)."""
    return [{"model": m, "colors": c, "sizes": s, "price": p} for m, c, s, p in _CATALOG]
