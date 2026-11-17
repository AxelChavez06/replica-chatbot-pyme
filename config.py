"""Configuración central del proyecto."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
REPLICATION_DIR = RESULTS_DIR / "replication"
EXPERIMENT_DIR = RESULTS_DIR / "experiment"

DEMO_DB = DATA_DIR / "demo.db"
TRAIN_FILE = DATA_DIR / "intents_train.txt"
EVAL_FILE = DATA_DIR / "eval_queries.txt"
MODEL_FILE = MODELS_DIR / "intent_clf.joblib"

# Fecha "de hoy" fija para que la demo y los experimentos sean deterministas.
# (Coincide con el final del periodo observado en el artículo: abril 2025.)
DEMO_TODAY = "2025-04-30"

# Las cinco categorías originales del artículo (sección 4.4).
INTENTS = [
    "estado_pedido",
    "disponibilidad",
    "devoluciones",
    "pagos",
    "descuentos",
]
INTENT_LABELS = {
    "estado_pedido": "Estado de pedido",
    "disponibilidad": "Disponibilidad de productos",
    "devoluciones": "Devoluciones",
    "pagos": "Métodos de pago",
    "descuentos": "Descuentos",
}

# Umbral de confianza del clasificador por debajo del cual se deriva a un operador.
# Parámetro de diseño fijado a priori (el artículo no lo informa).
CONFIDENCE_THRESHOLD = 0.50

SEED = 42
