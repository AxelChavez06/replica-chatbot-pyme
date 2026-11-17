"""Experimento con consultas SINTÉTICAS para evaluar el prototipo.

Métricas propias del prototipo (NO son métricas del artículo ni de clientes reales):
  - exactitud de clasificación de intenciones (solo consultas con intención real conocida)
  - % de consultas resueltas automáticamente / con solicitud de aclaración / derivadas a humano
  - exactitud de enrutamiento (resultado del bot == resultado esperado definido por nosotros)
  - latencia de procesamiento del prototipo (ms)

Uso:  python -m experiments.run_experiment
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.chatbot import ChatbotEngine  # noqa: E402
from app.db import get_conn, init_db  # noqa: E402
from app.nlu import IntentClassifier, build_pipeline, load_labeled  # noqa: E402
from config import (CONFIDENCE_THRESHOLD, EVAL_FILE, EXPERIMENT_DIR, INTENT_LABELS, INTENTS, SEED,  # noqa: E402
                    TRAIN_FILE)

PRODUCT_PHRASES = ["la chaqueta denim", "el vestido de lino", "la camisa oxford", "el pantalón cargo",
                   "la sudadera oversize", "las zapatillas canvas", "el bolso tote", "el abrigo de lana"]
TIMING_REPEATS = 5


def load_eval(path: Path = EVAL_FILE) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tag, true_intent, expected, text = line.split("|", 3)
        rows.append({"tag": tag, "true_intent": true_intent, "expected": expected, "template": text})
    return rows


def fill_placeholders(rows: list[dict], order_codes: list[str], seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for r in rows:
        text = r["template"]
        if "{order}" in text:
            text = text.replace("{order}", rng.choice(order_codes))
        if "{product}" in text:
            text = text.replace("{product}", rng.choice(PRODUCT_PHRASES))
        out.append({**r, "text": text})
    return out


def run(output_dir: Path = EXPERIMENT_DIR, repeats: int = TIMING_REPEATS, threshold: float = CONFIDENCE_THRESHOLD,
        make_plots: bool = True) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "experiment.db"
    init_db(db_path, reset=True)  # BD limpia: no contamina la BD de demostración
    conn = get_conn(db_path)
    order_codes = [r["order_code"] for r in conn.execute("SELECT order_code FROM orders ORDER BY id")]
    conn.close()

    clf = IntentClassifier.train(TRAIN_FILE)
    items = fill_placeholders(load_eval(), order_codes)
    engine = ChatbotEngine(db_path=db_path, classifier=clf, threshold=threshold)

    # --- Clasificación (modelo solo, sin reglas de derivación) -------------------
    preds = clf.predict_many([it["text"] for it in items])
    for it, (p, c) in zip(items, preds):
        it["pred_intent"], it["pred_conf"] = p, c
    scoped = [it for it in items if it["true_intent"] in INTENTS]
    y_true = [it["true_intent"] for it in scoped]
    y_pred = [it["pred_intent"] for it in scoped]
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", labels=INTENTS)
    report = classification_report(y_true, y_pred, labels=INTENTS, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=INTENTS)

    # --- Pipeline completo ---------------------------------------------------------
    warm = engine.respond("warmup", "hola", log=False)  # calentamiento (no se cuenta)
    del warm
    for it in items:
        res = engine.respond(f"exp-{items.index(it)}", it["text"], log=True)
        it.update({"outcome": res["outcome"], "reason": res["reason"], "bot_intent": res["intent"],
                   "confidence": res["confidence"], "response_ms_first": res["response_ms"], "reply": res["reply"]})
    # Repeticiones solo para tiempos (sin escribir en BD)
    timings = [[it["response_ms_first"]] for it in items]
    for _ in range(repeats - 1):
        for k, it in enumerate(items):
            timings[k].append(engine.respond(f"t-{k}", it["text"], log=False)["response_ms"])
    all_ms = np.array([v for row in timings for v in row])
    for k, it in enumerate(items):
        it["response_ms_mean"] = float(np.mean(timings[k]))

    n = len(items)
    counts = pd.Series([it["outcome"] for it in items]).value_counts().to_dict()
    resolved, clar, esc = counts.get("resuelto", 0), counts.get("aclaracion", 0), counts.get("derivado", 0)
    routing_acc = float(np.mean([it["outcome"] == it["expected"] for it in items]))

    df = pd.DataFrame(items)
    by_tag = (df.assign(ok=df["outcome"] == df["expected"])
              .groupby("tag")
              .agg(n=("text", "size"), routing_accuracy=("ok", "mean"),
                   resuelto=("outcome", lambda s: (s == "resuelto").sum()),
                   aclaracion=("outcome", lambda s: (s == "aclaracion").sum()),
                   derivado=("outcome", lambda s: (s == "derivado").sum()),
                   latency_ms_mean=("response_ms_mean", "mean"))
              .reset_index())
    sc = df[df["true_intent"].isin(INTENTS)]
    acc_by_tag = (sc.assign(ok=sc["pred_intent"] == sc["true_intent"]).groupby("tag")["ok"]
                  .agg(["mean", "size"]).rename(columns={"mean": "intent_accuracy", "size": "n_scoped"}).reset_index())
    by_tag = by_tag.merge(acc_by_tag, on="tag", how="left")

    # Validación cruzada sobre el entrenamiento (referencia; solo datos de entrenamiento)
    train_rows = load_labeled(TRAIN_FILE)
    X = [t for _, t in train_rows]
    y = [i for i, _ in train_rows]
    cv_pred = cross_val_predict(build_pipeline(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    cv_acc = float(accuracy_score(y, cv_pred))

    # Sensibilidad al umbral (exploratoria; el umbral principal se fijó a priori en config.py)
    sens = []
    for th in [0.30, 0.40, 0.50, 0.60, 0.70]:
        eng = ChatbotEngine(db_path=db_path, classifier=clf, threshold=th)
        outs = [eng.respond("s", it["text"], log=False)["outcome"] for it in items]
        sens.append({"threshold": th,
                     "automatizadas_pct": 100 * np.mean([o == "resuelto" for o in outs]),
                     "derivadas_pct": 100 * np.mean([o == "derivado" for o in outs]),
                     "routing_accuracy_pct": 100 * np.mean([o == it["expected"] for o, it in zip(outs, items)])})

    metrics = {
        "origen": "PRUEBAS SINTÉTICAS DEL PROTOTIPO (no son datos del artículo ni de clientes reales)",
        "n_consultas": n,
        "n_con_intencion_real": len(scoped),
        "umbral_confianza": threshold,
        "clasificacion": {
            "exactitud_intenciones": acc,
            "macro_f1": macro_f1,
            "exactitud_validacion_cruzada_entrenamiento_5fold": cv_acc,
            "por_clase": {k: report[k] for k in INTENTS},
            "matriz_confusion": {"labels": INTENTS, "matrix": cm.tolist()},
        },
        "resultados": {
            "resueltas_automaticamente": resolved,
            "aclaracion_solicitada": clar,
            "derivadas_a_humano": esc,
            "pct_resueltas_automaticamente": 100 * resolved / n,
            "pct_aclaracion": 100 * clar / n,
            "pct_derivadas": 100 * esc / n,
            "pct_atendidas_sin_humano": 100 * (resolved + clar) / n,
            "exactitud_enrutamiento_pct": 100 * routing_acc,
        },
        "latencia_ms": {
            "media": float(all_ms.mean()), "mediana": float(np.median(all_ms)),
            "p95": float(np.percentile(all_ms, 95)), "max": float(all_ms.max()),
            "n_mediciones": int(all_ms.size),
            "nota": "Tiempo de procesamiento del servidor (clasificación + reglas + consultas SQLite). "
                    "No es comparable con el tiempo medio de respuesta en minutos del artículo.",
        },
        "por_etiqueta": by_tag.astype(object).where(by_tag.notna(), None).to_dict(orient="records"),
        "sensibilidad_umbral": sens,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    df.drop(columns=["template"]).to_csv(output_dir / "per_query.csv", index=False, encoding="utf-8-sig")
    by_tag.to_csv(output_dir / "por_etiqueta.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(sens).to_csv(output_dir / "sensibilidad_umbral.csv", index=False, encoding="utf-8-sig")

    if make_plots:
        _plots(output_dir, cm, by_tag, all_ms, metrics)
    return metrics


def _plots(out: Path, cm, by_tag: pd.DataFrame, all_ms, m: dict) -> None:
    labels = [INTENT_LABELS[i] for i in INTENTS]
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(5)); ax.set_yticks(range(5))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8); ax.set_yticklabels(labels, fontsize=8)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicha"); ax.set_ylabel("Real")
    ax.set_title(f"Matriz de confusión (consultas sintéticas)\nexactitud = {m['clasificacion']['exactitud_intenciones']:.1%}")
    fig.colorbar(im, fraction=0.046); fig.tight_layout()
    fig.savefig(out / "matriz_confusion.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    t = by_tag.set_index("tag")
    bottom = np.zeros(len(t))
    for col, color in [("resuelto", "#2F5BB7"), ("aclaracion", "#E0A52B"), ("derivado", "#C0504D")]:
        ax.barh(t.index, t[col], left=bottom, color=color, label=col)
        bottom += t[col].values
    ax.set_xlabel("Número de consultas"); ax.legend(frameon=False)
    ax.set_title("Resultado del chatbot por tipo de consulta sintética")
    fig.tight_layout(); fig.savefig(out / "resultados_por_etiqueta.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(all_ms, bins=30, color="#2F5BB7")
    ax.axvline(np.median(all_ms), color="black", linestyle="--", label=f"mediana {np.median(all_ms):.1f} ms")
    ax.set_xlabel("Latencia de procesamiento (ms)"); ax.set_ylabel("Frecuencia"); ax.legend(frameon=False)
    ax.set_title("Latencia del prototipo (no comparable con minutos del artículo)")
    fig.tight_layout(); fig.savefig(out / "latencia.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    m = run()
    r, c = m["resultados"], m["clasificacion"]
    print("=== PRUEBAS SINTÉTICAS (prototipo) ===")
    print(f"Consultas: {m['n_consultas']}  (con intención real: {m['n_con_intencion_real']})")
    print(f"Exactitud de intenciones: {c['exactitud_intenciones']:.1%}   macro-F1: {c['macro_f1']:.3f}")
    print(f"Resueltas automáticamente: {r['pct_resueltas_automaticamente']:.1f}%  | aclaración: {r['pct_aclaracion']:.1f}%"
          f"  | derivadas: {r['pct_derivadas']:.1f}%")
    print(f"Exactitud de enrutamiento: {r['exactitud_enrutamiento_pct']:.1f}%")
    l = m["latencia_ms"]
    print(f"Latencia (ms): media {l['media']:.2f}, mediana {l['mediana']:.2f}, p95 {l['p95']:.2f}")
    print(f"Resultados guardados en {EXPERIMENT_DIR}")
