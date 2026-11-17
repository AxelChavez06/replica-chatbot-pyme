import pytest
from scipy import stats

from analysis.replicate import exact_permutation_mwu, run_tests


def test_exact_matches_scipy_without_ties():
    pre, post = [118, 120, 119, 116], [88, 61, 43]
    ex = exact_permutation_mwu(pre, post)
    assert ex["n_arrangements"] == 35
    assert ex["p_exact_two_sided"] == pytest.approx(2 / 35)
    assert ex["p_exact_two_sided"] == pytest.approx(stats.mannwhitneyu(post, pre, method="exact").pvalue)


def test_published_significance_pattern_reproduces_with_exact_two_sided():
    df = run_tests()
    col = "p exacto bilateral (permutación, con empates)"
    p = dict(zip(df["Hipótesis"], df[col]))
    assert p["H1 Tiempo de respuesta"] > 0.05
    assert p["H2 Satisfacción"] < 0.05
    assert p["H3 Consultas mensuales"] > 0.05
    assert df["Reproduce lo publicado (exacto bilateral, α=0.05)"].all()


def test_complete_separation_in_all_indicators():
    df = run_tests()
    assert (df["Rank-biserial (post vs pre)"].abs() == 1).all()
