"""Verifica que las cifras transcritas del artículo son internamente consistentes."""
import pytest

from analysis import paper_data as P
from analysis.replicate import build_table1, build_table2, build_table3, build_table4


def test_table1_handled_plus_escalated_equals_total():
    t = P.TABLE1
    for h, e, n in zip(t["handled_by_chatbot"], t["escalated"], t["total_inquiries"]):
        assert h + e == n


def test_table1_percentages_match_published():
    df = build_table1()
    assert df["Coincide con publicado"].all()


def test_table2_means_and_changes_match_published():
    t2 = build_table2().iloc[:3]
    for _, r in t2.iterrows():
        assert r["Antes (calculado)"] == pytest.approx(r["Antes (publicado)"], abs=0.006)
        assert r["Después (calculado)"] == pytest.approx(r["Después (publicado)"], abs=0.006)
        assert r["Cambio % (calculado)"] == pytest.approx(r["Cambio % (publicado)"], abs=0.006)


def test_table2_share_is_mean_of_monthly_percentages():
    t2 = build_table2()
    assert t2.iloc[3]["Después (calculado)"] == pytest.approx(74.20, abs=0.005)
    assert t2.iloc[4]["Después (calculado)"] != pytest.approx(74.20, abs=0.005)  # el agrupado difiere


def test_tables_3_and_4_percentages():
    for df in (build_table3(), build_table4()):
        assert (df["Porcentaje calculado"] - df["Porcentaje publicado"]).abs().max() < 0.006
