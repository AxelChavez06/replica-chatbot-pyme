from app.nlu import clf_preprocess, load_labeled, normalize
from config import EVAL_FILE, INTENTS, TRAIN_FILE


def test_normalize_strips_accents():
    assert normalize("  ¿Dónde   está MI Pedido? ") == "¿donde esta mi pedido?"


def test_order_code_is_masked():
    assert "codigopedido" in clf_preprocess("Estado de PED-1004 por favor")


def test_training_covers_five_intents_with_enough_examples():
    rows = load_labeled(TRAIN_FILE)
    for i in INTENTS:
        assert sum(1 for k, _ in rows if k == i) >= 25


def test_no_exact_overlap_between_train_and_eval_templates():
    train = {normalize(t) for _, t in load_labeled(TRAIN_FILE)}
    ev = set()
    for line in EVAL_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            ev.add(normalize(line.split("|", 3)[3]))
    assert not (train & ev)


def test_classifier_basic_predictions(clf):
    assert clf.predict("¿Aceptan PayPal?")[0] == "pagos"
    assert clf.predict("Quiero devolver mi compra")[0] == "devoluciones"
    assert clf.predict("¿Cuándo llega mi paquete?")[0] == "estado_pedido"
