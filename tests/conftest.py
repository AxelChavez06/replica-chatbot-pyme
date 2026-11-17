import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chatbot import ChatbotEngine  # noqa: E402
from app.db import get_conn, init_db  # noqa: E402
from app.nlu import IntentClassifier  # noqa: E402


@pytest.fixture(scope="session")
def clf():
    return IntentClassifier.train()


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "test.db"
    init_db(p, reset=True)
    return p


@pytest.fixture()
def engine(db_path, clf):
    return ChatbotEngine(db_path=db_path, classifier=clf)


@pytest.fixture()
def conn(db_path):
    c = get_conn(db_path)
    yield c
    c.close()
