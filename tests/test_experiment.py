import pandas as pd

from experiments.run_experiment import load_eval, run


def test_eval_file_is_well_formed():
    rows = load_eval()
    assert len(rows) >= 100
    assert {r["expected"] for r in rows} == {"resuelto", "aclaracion", "derivado"}
    assert len({r["template"] for r in rows}) == len(rows)


def test_experiment_runs_and_is_reproducible(tmp_path):
    m1 = run(output_dir=tmp_path / "a", repeats=2, make_plots=False)
    m2 = run(output_dir=tmp_path / "b", repeats=2, make_plots=False)
    for key in ("exactitud_intenciones", "macro_f1"):
        assert m1["clasificacion"][key] == m2["clasificacion"][key]
    assert m1["resultados"] == m2["resultados"]
    r = m1["resultados"]
    assert abs(r["pct_resueltas_automaticamente"] + r["pct_aclaracion"] + r["pct_derivadas"] - 100) < 1e-9
    assert 0 <= m1["clasificacion"]["exactitud_intenciones"] <= 1
    assert m1["latencia_ms"]["mediana"] > 0
    d1 = pd.read_csv(tmp_path / "a" / "per_query.csv")
    d2 = pd.read_csv(tmp_path / "b" / "per_query.csv")
    assert list(d1["text"]) == list(d2["text"]) and list(d1["outcome"]) == list(d2["outcome"])
