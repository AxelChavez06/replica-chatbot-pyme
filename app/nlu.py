"""Clasificador de intenciones (TF-IDF + regresión logística) para las cinco categorías.

El artículo indica que el NLP se usó para clasificar la entrada del usuario y enrutarla a módulos de respuesta,
sin modelos generativos. Este módulo cumple ese papel con scikit-learn. El algoritmo concreto del artículo
no se informa; esta es una aproximación.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from config import MODEL_FILE, SEED, TRAIN_FILE


def normalize(text: str) -> str:
    """Minúsculas, sin acentos y espacios colapsados."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


_ORDER_CODE_RE = re.compile(r"\bped[-\s]?\d{4}\b")


def clf_preprocess(text: str) -> str:
    """Normaliza y enmascara el código de pedido (entidad) para que no diluya las características del texto."""
    return _ORDER_CODE_RE.sub(" codigopedido ", normalize(text))


def load_labeled(path: Path = TRAIN_FILE) -> list[tuple[str, str]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        intent, text = line.split("|", 1)
        rows.append((intent.strip(), text.strip()))
    return rows


def build_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(preprocessor=clf_preprocess, analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(preprocessor=clf_preprocess, analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)),
        ]
    )
    clf = LogisticRegression(C=10.0, max_iter=2000, random_state=SEED)
    return Pipeline([("features", features), ("clf", clf)])


class IntentClassifier:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.classes_ = list(pipeline.named_steps["clf"].classes_)

    @classmethod
    def train(cls, path: Path = TRAIN_FILE) -> "IntentClassifier":
        rows = load_labeled(path)
        pipe = build_pipeline()
        pipe.fit([t for _, t in rows], [i for i, _ in rows])
        return cls(pipe)

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        proba = self.pipeline.predict_proba([text])[0]
        k = int(np.argmax(proba))
        return self.classes_[k], float(proba[k]), {c: float(p) for c, p in zip(self.classes_, proba)}

    def predict_many(self, texts: list[str]) -> list[tuple[str, float]]:
        proba = self.pipeline.predict_proba(texts)
        idx = proba.argmax(axis=1)
        return [(self.classes_[i], float(proba[n, i])) for n, i in enumerate(idx)]


def _file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_classifier(train_path: Path = TRAIN_FILE, model_path: Path = MODEL_FILE, force: bool = False) -> IntentClassifier:
    """Carga el modelo guardado o lo reentrena si no existe / cambió el archivo de entrenamiento."""
    h = _file_hash(train_path)
    if model_path.exists() and not force:
        try:
            blob = joblib.load(model_path)
            if blob.get("train_hash") == h:
                return IntentClassifier(blob["pipeline"])
        except Exception:
            pass
    clf = IntentClassifier.train(train_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": clf.pipeline, "train_hash": h}, model_path)
    return clf
