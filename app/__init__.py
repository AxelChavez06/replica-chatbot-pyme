"""Aplicación Flask: chatbot híbrido + panel de indicadores."""
from __future__ import annotations

from pathlib import Path

from flask import Flask

from app.chatbot import ChatbotEngine
from app.db import init_db
from app.nlu import get_classifier
from config import DEMO_DB


def create_app(db_path: str | Path | None = None, classifier=None, results_dir: str | Path | None = None) -> Flask:
    from config import RESULTS_DIR

    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path or DEMO_DB)
    app.config["RESULTS_DIR"] = str(results_dir or RESULTS_DIR)
    app.json.ensure_ascii = False

    if not Path(app.config["DB_PATH"]).exists():
        init_db(app.config["DB_PATH"], reset=True)
    app.extensions["engine"] = ChatbotEngine(db_path=app.config["DB_PATH"], classifier=classifier or get_classifier())

    from app.routes import bp

    app.register_blueprint(bp)
    return app
