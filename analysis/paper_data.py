"""Datos numéricos PUBLICADOS en el artículo (Marcineková, Sujová, Ďurica, Information 2025, 16, 1078).

Solo se transcriben cifras que aparecen en el PDF. Nada aquí está inventado.
Cada bloque indica la tabla / figura / sección de origen.
"""

MONTHS = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03", "2025-04"]
MONTH_LABELS = ["Oct 2024", "Nov 2024", "Dic 2024", "Ene 2025", "Feb 2025", "Mar 2025", "Abr 2025"]
POST_START_INDEX = 4  # el artículo compara oct-ene (pre) vs feb-abr (post)

# --- Tabla 1 -----------------------------------------------------------------
TABLE1 = {
    "total_inquiries": [645, 698, 715, 683, 574, 598, 581],
    "avg_response_min": [118, 120, 119, 116, 88, 61, 43],
    "handled_by_chatbot": [0, 0, 0, 0, 349, 457, 496],
    "escalated": [645, 698, 715, 683, 225, 141, 85],
    "satisfaction": [3.7, 3.6, 3.8, 3.8, 4.1, 4.3, 4.4],
}
# Porcentajes impresos en la Tabla 1 (columna "Handled by Chatbot")
TABLE1_PUBLISHED_PCT = [0.00, 0.00, 0.00, 0.00, 60.80, 76.42, 85.37]

# --- Figura 1 (pedidos mensuales) ---------------------------------------------
ORDERS = [945, 993, 978, 962, 895, 964, 940]

# --- Tabla 2 (valores publicados) ----------------------------------------------
TABLE2_PUBLISHED = {
    "avg_response_min": {"before": 118.25, "after": 64.00, "change_pct": -45.88, "p": ">0.05", "significant": False},
    "avg_satisfaction": {"before": 3.73, "after": 4.27, "change_pct": 14.54, "p": "<0.05", "significant": True},
    "avg_inquiries": {"before": 685.25, "after": 584.33, "change_pct": -14.73, "p": ">0.05", "significant": False},
    "share_handled_by_chatbot": {"before": 0.00, "after": 74.20, "change_pct": None, "p": None, "significant": None},
}

# --- Tabla 3 (codificación temática, entrevistas a empleados) ---------------------
TABLE3 = [
    ("Beneficios percibidos", 16, 48.48),
    ("Desafíos", 7, 21.21),
    ("Mejoras/Adaptación", 7, 21.21),
    ("Actitudes iniciales", 3, 9.09),
]

# --- Tabla 4 (sentimiento en reflexiones de empleados) ----------------------------
TABLE4 = [
    ("Positivo", 7, 36.84),
    ("Neutral/Adaptativo", 5, 26.32),
    ("Negativo", 7, 36.84),
]

# --- Sección 4.4 / Tabla 5 (texto cualitativo, solo ejemplos citados) ---------------
FIVE_CATEGORIES = [
    "Estado del pedido y seguimiento de entrega",
    "Disponibilidad de producto y variantes",
    "Devoluciones y reclamaciones",
    "Pagos y facturación",
    "Descuentos y códigos promocionales",
]
# "approximately 10–15% of these conversations required human intervention" (sec. 4.4)
PAPER_ESCALATION_RANGE_PCT = (10.0, 15.0)

# Otros datos de contexto publicados
CONTEXT = {
    "employees": 8,
    "observation_period": "oct 2024 - abr 2025",
    "chatbot_architecture": "híbrida: árboles de diálogo (reglas) + NLP para clasificar intenciones; sin LLM generativo",
    "tests": "Mann-Whitney U, pre (oct-ene, n=4) vs post (feb-abr, n=3)",
    "software": "Microsoft Excel y Statistica 12",
}

# Inconsistencias internas del artículo detectadas al leerlo (texto, no cálculo).
TEXTUAL_INCONSISTENCIES = [
    "Sec. 3.1 dice que el chatbot se lanzó en enero de 2025; la Tabla 1 y la comparación pre/post usan febrero de 2025 como primer mes con chatbot.",
    "Sec. 4.2 dice que la proporción de consultas del chatbot pasó 'de 61% a 85%'; la Tabla 1 da 60.80%, 76.42% y 85.37%.",
    "Sec. 3.2 indica entrevistas a tres empleados (2 operadores + 1 coordinador); la Sec. 4.3 habla de 'dos' entrevistas semiestructuradas.",
    "Sec. 3.1 describe 'bienes de consumo'; la Sec. 4 describe 'artículos de moda de nicho'.",
    "Sec. 4.2 afirma 'strong correlation' entre automatización y satisfacción sin reportar ningún coeficiente de correlación.",
]
