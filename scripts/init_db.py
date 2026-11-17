"""Crea la base de datos de demostración (determinista) y entrena el clasificador.

Uso:  python -m scripts.init_db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import init_db  # noqa: E402
from app.nlu import get_classifier  # noqa: E402
from config import DEMO_DB  # noqa: E402

if __name__ == "__main__":
    init_db(DEMO_DB, reset=True)
    get_classifier(force=True)
    print(f"Base de datos demo creada en {DEMO_DB} y clasificador entrenado.")
