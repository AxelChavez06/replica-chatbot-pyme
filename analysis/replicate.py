"""Réplica analítica: reproduce tablas, gráficos y pruebas del artículo con SUS cifras publicadas.

Uso:  python -m analysis.replicate
Salida: results/replication/  (CSV, PNG, JSON y discrepancias.md)
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis import paper_data as P  # noqa: E402
from config import REPLICATION_DIR  # noqa: E402

PRE = slice(0, P.POST_START_INDEX)
POST = slice(P.POST_START_INDEX, None)


# ----------------------------------------------------------------------------
# Tablas
# ----------------------------------------------------------------------------
def build_table1() -> pd.DataFrame:
    t = P.TABLE1
    df = pd.DataFrame(
        {
            "Mes": P.MONTH_LABELS,
            "Consultas totales": t["total_inquiries"],
            "Tiempo medio de respuesta (min)": t["avg_response_min"],
            "Atendidas por chatbot": t["handled_by_chatbot"],
            "Derivadas a operador": t["escalated"],
            "Satisfacción (1-5)": t["satisfaction"],
        }
    )
    df["% chatbot (calculado)"] = (df["Atendidas por chatbot"] / df["Consultas totales"] * 100).round(2)
    df["% chatbot (publicado)"] = P.TABLE1_PUBLISHED_PCT
    df["Coincide con publicado"] = (df["% chatbot (calculado)"] - df["% chatbot (publicado)"]).abs() < 0.005
    df["Chatbot + operador = total"] = df["Atendidas por chatbot"] + df["Derivadas a operador"] == df["Consultas totales"]
    return df


def pct_change(before: float, after: float) -> float:
    return (after - before) / before * 100


def build_table2() -> pd.DataFrame:
    t = P.TABLE1
    rows = []
    series = {
        "avg_response_min": ("Tiempo medio de respuesta (min)", t["avg_response_min"]),
        "avg_satisfaction": ("Satisfacción media (1-5)", t["satisfaction"]),
        "avg_inquiries": ("Consultas totales por mes", t["total_inquiries"]),
    }
    for key, (label, vals) in series.items():
        pre, post = np.mean(vals[PRE]), np.mean(vals[POST])
        pub = P.TABLE2_PUBLISHED[key]
        rows.append(
            {
                "Indicador": label,
                "Antes (calculado)": round(pre, 2),
                "Antes (publicado)": pub["before"],
                "Después (calculado)": round(post, 2),
                "Después (publicado)": pub["after"],
                "Cambio % (calculado)": round(pct_change(pre, post), 2),
                "Cambio % (publicado)": pub["change_pct"],
            }
        )
    # Cuota atendida por chatbot: el artículo no aclara si es promedio de porcentajes mensuales o agrupado.
    handled = np.array(t["handled_by_chatbot"][POST], float)
    total = np.array(t["total_inquiries"][POST], float)
    mean_of_pct = float(np.mean(handled / total * 100))
    pooled = float(handled.sum() / total.sum() * 100)
    rows.append(
        {
            "Indicador": "% atendido por chatbot (promedio de % mensuales)",
            "Antes (calculado)": 0.0,
            "Antes (publicado)": 0.0,
            "Después (calculado)": round(mean_of_pct, 2),
            "Después (publicado)": P.TABLE2_PUBLISHED["share_handled_by_chatbot"]["after"],
            "Cambio % (calculado)": None,
            "Cambio % (publicado)": None,
        }
    )
    rows.append(
        {
            "Indicador": "% atendido por chatbot (agrupado: sum/sum) [alternativa]",
            "Antes (calculado)": 0.0,
            "Antes (publicado)": None,
            "Después (calculado)": round(pooled, 2),
            "Después (publicado)": None,
            "Cambio % (calculado)": None,
            "Cambio % (publicado)": None,
        }
    )
    return pd.DataFrame(rows)


def build_table3() -> pd.DataFrame:
    df = pd.DataFrame(P.TABLE3, columns=["Tema", "Frecuencia (n)", "Porcentaje publicado"])
    df["Porcentaje calculado"] = (df["Frecuencia (n)"] / df["Frecuencia (n)"].sum() * 100).round(2)
    return df


def build_table4() -> pd.DataFrame:
    df = pd.DataFrame(P.TABLE4, columns=["Sentimiento", "Frecuencia (n)", "Porcentaje publicado"])
    df["Porcentaje calculado"] = (df["Frecuencia (n)"] / df["Frecuencia (n)"].sum() * 100).round(2)
    return df


# ----------------------------------------------------------------------------
# Pruebas estadísticas (Mann-Whitney U)
# ----------------------------------------------------------------------------
def exact_permutation_mwu(pre, post) -> dict:
    """Distribución exacta de U por permutación (maneja empates con rangos medios).

    U se define para la muestra 'post' respecto de 'pre'. Con n1=4 y n2=3 hay C(7,3)=35
    asignaciones posibles, por lo que el p mínimo bilateral posible es 2/35 = 0.0571.
    """
    values = np.array(list(pre) + list(post), float)
    n1, n2 = len(pre), len(post)
    ranks = stats.rankdata(values)  # rangos medios

    def u_post(idx_post):
        r = ranks[list(idx_post)].sum()
        return r - n2 * (n2 + 1) / 2

    obs = u_post(range(n1, n1 + n2))
    all_u = np.array([u_post(c) for c in combinations(range(n1 + n2), n2)])
    mean_u = n1 * n2 / 2
    p_ge = float(np.mean(all_u >= obs - 1e-12))  # post tiende a ser mayor
    p_le = float(np.mean(all_u <= obs + 1e-12))  # post tiende a ser menor
    p_two = float(np.mean(np.abs(all_u - mean_u) >= abs(obs - mean_u) - 1e-12))
    return {"U_post": float(obs), "p_exact_two_sided": p_two, "p_exact_post_greater": p_ge,
            "p_exact_post_less": p_le, "n_arrangements": int(len(all_u))}


def run_tests() -> pd.DataFrame:
    t = P.TABLE1
    indicators = [
        ("H1 Tiempo de respuesta", t["avg_response_min"], "less", "reducción"),
        ("H2 Satisfacción", t["satisfaction"], "greater", "aumento"),
        ("H3 Consultas mensuales", t["total_inquiries"], "two-sided", "cambio (bilateral)"),
    ]
    published = {
        "H1 Tiempo de respuesta": "Tabla 2: p>0.05 (no significativo)",
        "H2 Satisfacción": "Tabla 2: p<0.05 (significativo)",
        "H3 Consultas mensuales": "Tabla 2: p>0.05 (no significativo)",
    }
    rows = []
    for name, vals, direction, hyp in indicators:
        pre, post = vals[PRE], vals[POST]
        ex = exact_permutation_mwu(pre, post)
        if direction == "less":
            p_exact_dir = ex["p_exact_post_less"]
        elif direction == "greater":
            p_exact_dir = ex["p_exact_post_greater"]
        else:
            p_exact_dir = ex["p_exact_two_sided"]
        asym_cc = stats.mannwhitneyu(post, pre, alternative="two-sided", method="asymptotic", use_continuity=True)
        asym_nocc = stats.mannwhitneyu(post, pre, alternative="two-sided", method="asymptotic", use_continuity=False)
        n1, n2 = len(pre), len(post)
        scipy_exact = stats.mannwhitneyu(post, pre, alternative="two-sided", method="exact")
        paper_sig = {"H1 Tiempo de respuesta": False, "H2 Satisfacción": True, "H3 Consultas mensuales": False}[name]
        rank_biserial = 2 * ex["U_post"] / (n1 * n2) - 1
        rows.append(
            {
                "Hipótesis": name,
                "Tipo de hipótesis": hyp,
                "n pre / n post": f"{n1} / {n2}",
                "U (post vs pre)": ex["U_post"],
                "Rank-biserial (post vs pre)": round(rank_biserial, 3),
                "p exacto bilateral (permutación, con empates)": round(ex["p_exact_two_sided"], 4),
                "p exacto bilateral (scipy, ignora empates)": round(float(scipy_exact.pvalue), 4),
                "p exacto en la dirección de la hipótesis": round(p_exact_dir, 4),
                "p asintótico bilateral (con corrección de continuidad)": round(float(asym_cc.pvalue), 4),
                "p asintótico bilateral (sin corrección)": round(float(asym_nocc.pvalue), 4),
                "Publicado": published[name],
                "Reproduce lo publicado (exacto bilateral, α=0.05)": bool((ex["p_exact_two_sided"] < 0.05) == paper_sig),
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------
def fig1_orders(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(P.MONTHS, P.ORDERS, marker="o", color="#2F5BB7", linewidth=2)
    for x, y in zip(P.MONTHS, P.ORDERS):
        ax.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.axvline(P.POST_START_INDEX - 0.5, color="#888", linestyle="--", linewidth=1)
    ax.text(P.POST_START_INDEX - 0.45, min(P.ORDERS) - 3, "Chatbot implementado", fontsize=9, color="#444")
    ax.set_title("Figura 1 (réplica). Pedidos mensuales")
    ax.set_ylabel("Pedidos")
    ax.set_ylim(885, 1005)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig2_impact(path: Path) -> None:
    t = P.TABLE1
    x = np.arange(len(P.MONTHS))
    handled = np.array(t["handled_by_chatbot"])
    escalated = np.array(t["escalated"])
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x, escalated, color="#C9C9C9", label="Derivadas a operador")
    ax.bar(x, handled, bottom=escalated, color="#FFFFFF", edgecolor="#333", label="Atendidas por chatbot")
    ax.set_xticks(x)
    ax.set_xticklabels(P.MONTH_LABELS, rotation=0, fontsize=8)
    ax.set_ylabel("Consultas")
    ax2 = ax.twinx()
    ax2.plot(x, t["satisfaction"], color="black", marker="o", linewidth=2, label="Satisfacción (1-5)")
    for xi, v in zip(x, t["satisfaction"]):
        ax2.annotate(f"{v}", (xi, v), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=9)
    ax2.set_ylim(3.5, 4.6)
    ax2.set_ylabel("Satisfacción (1-5)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False)
    ax.set_title("Figura 2 (réplica). Impacto del chatbot (datos de la Tabla 1)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_response_time(path: Path) -> None:
    """Visualización EXTRA (no es una figura del artículo)."""
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#999"] * P.POST_START_INDEX + ["#2F5BB7"] * (len(P.MONTHS) - P.POST_START_INDEX)
    ax.bar(P.MONTH_LABELS, P.TABLE1["avg_response_min"], color=colors)
    for i, v in enumerate(P.TABLE1["avg_response_min"]):
        ax.text(i, v + 1.5, str(v), ha="center", fontsize=9)
    ax.set_ylabel("Minutos")
    ax.set_title("Extra. Tiempo medio de respuesta (Tabla 1), gris = sin chatbot")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_qualitative(path: Path) -> None:
    """Visualización EXTRA de las Tablas 3 y 4."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].barh([r[0] for r in P.TABLE3][::-1], [r[1] for r in P.TABLE3][::-1], color="#2F5BB7")
    axes[0].set_title("Tabla 3: temas (frecuencia)")
    axes[1].barh([r[0] for r in P.TABLE4][::-1], [r[1] for r in P.TABLE4][::-1], color="#7A8CA8")
    axes[1].set_title("Tabla 4: sentimiento (frecuencia)")
    fig.suptitle("Extra. Datos cualitativos publicados (conteos del artículo)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Informe de discrepancias
# ----------------------------------------------------------------------------
def write_discrepancies(path: Path, t1, t2, tests) -> None:
    L = ["# Discrepancias entre la réplica y el artículo", "",
         "Generado automáticamente por `python -m analysis.replicate`.", ""]
    L += ["## 1. Cifras que SÍ coinciden", ""]
    ok1 = bool(t1["Coincide con publicado"].all())
    ok2 = bool(t1["Chatbot + operador = total"].all())
    L.append(f"- Tabla 1: porcentajes de consultas atendidas por chatbot recalculados = publicados: **{ok1}**.")
    L.append(f"- Tabla 1: atendidas por chatbot + derivadas = total en los 7 meses: **{ok2}**.")
    core = t2.iloc[:3]
    ok_means = bool(((core["Antes (calculado)"] - core["Antes (publicado)"]).abs() < 0.006).all()
                    and ((core["Después (calculado)"] - core["Después (publicado)"]).abs() < 0.006).all())
    ok_chg = bool(((core["Cambio % (calculado)"] - core["Cambio % (publicado)"]).abs() < 0.006).all())
    L.append(f"- Tabla 2: promedios antes/después recalculados = publicados: **{ok_means}**.")
    L.append(f"- Tabla 2: cambios porcentuales recalculados = publicados: **{ok_chg}**.")
    share = t2.iloc[3]["Después (calculado)"]
    L.append(f"- Tabla 2: 74.20% atendido por chatbot se reproduce como promedio de los porcentajes mensuales ({share}%). "
             f"El cálculo agrupado (suma/suma) da {t2.iloc[4]['Después (calculado)']}%, por lo que el artículo usó el promedio de porcentajes.")
    L.append("- Tablas 3 y 4: los porcentajes publicados coinciden con n / suma(n) (ver CSV).")
    L += ["", "## 2. Pruebas de Mann-Whitney U (H1-H3)", ""]
    L.append("Con las cifras mensuales de la Tabla 1 (n=4 pre, n=3 post):")
    L.append("")
    L.append(tests.to_markdown(index=False))
    L += ["",
          "Interpretación:",
          "",
          "- **El patrón publicado SÍ se reproduce** (solo la satisfacción es significativa a α=0.05) usando la prueba exacta "
          "bilateral por permutación que respeta los empates: H1 p=0.0571, H2 p=0.0286, H3 p=0.0571.",
          "- Ese resultado depende de un detalle: con n=4 y n=3 solo hay C(7,3)=35 asignaciones posibles, así que sin empates "
          "el p exacto bilateral mínimo es 2/35=0.0571 (nunca <0.05). En satisfacción hay un empate (3.8 y 3.8 en el periodo pre) "
          "que vuelve asimétrica la distribución nula y deja p=1/35=0.0286. Es decir, la 'significancia' de H2 y la "
          "'no significancia' de H1/H3 provienen de la discretización y los empates, no de una diferencia real entre los tres "
          "indicadores: **los tres** muestran separación completa entre periodos (rank-biserial = ±1).",
          "- La función de SciPy con `method='exact'` ignora los empates y da 0.0571 en los tres (no reproduce el patrón). "
          "La aproximación normal con corrección de continuidad sí lo reproduce, por margen mínimo (p=0.0518, 0.0497 y 0.0518); "
          "sin corrección los tres dan p≈0.03. No sabemos qué variante usó Statistica 12, así que la coincidencia no confirma el procedimiento.",
          "- H1 y H2 están formuladas como direccionales; con la prueba exacta unilateral (p=0.0286) H1 también sería significativa. "
          "Los autores no aclaran si usaron pruebas uni o bilaterales.",
          "- Con solo 3 meses post y sin control de estacionalidad, estas pruebas tienen poca potencia y no permiten atribuir "
          "causalidad al chatbot (el propio artículo lo reconoce parcialmente).",
          ""]
    L += ["## 3. Inconsistencias textuales del artículo", ""]
    L += [f"- {s}" for s in P.TEXTUAL_INCONSISTENCIES]
    L += ["", "## 4. Elementos que NO se pueden reproducir con datos publicados", "",
          "- Datos de logs de conversación, entrevistas y comentarios de clientes (confidenciales; solo hay conteos y citas de ejemplo).",
          "- Porcentajes por categoría de consulta (solo se dice que las cinco categorías suman >90%).",
          "- La plataforma comercial, su modelo NLP y los árboles de diálogo originales (no se nombran).",
          ""]
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> dict:
    out = REPLICATION_DIR
    out.mkdir(parents=True, exist_ok=True)
    t1, t2, t3, t4 = build_table1(), build_table2(), build_table3(), build_table4()
    tests = run_tests()
    t1.to_csv(out / "tabla1_indicadores_mensuales.csv", index=False, encoding="utf-8-sig")
    t2.to_csv(out / "tabla2_resumen_pre_post.csv", index=False, encoding="utf-8-sig")
    t3.to_csv(out / "tabla3_codificacion_tematica.csv", index=False, encoding="utf-8-sig")
    t4.to_csv(out / "tabla4_sentimiento.csv", index=False, encoding="utf-8-sig")
    tests.to_csv(out / "pruebas_mann_whitney.csv", index=False, encoding="utf-8-sig")
    fig1_orders(out / "figura1_pedidos_mensuales.png")
    fig2_impact(out / "figura2_impacto_chatbot.png")
    fig_response_time(out / "extra_tiempo_respuesta.png")
    fig_qualitative(out / "extra_datos_cualitativos.png")
    write_discrepancies(out / "discrepancias.md", t1, t2, tests)
    summary = {
        "table1": t1.to_dict(orient="records"),
        "table2": t2.to_dict(orient="records"),
        "tests": tests.to_dict(orient="records"),
    }
    (out / "replicacion_resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
    print(f"Réplica analítica generada en {REPLICATION_DIR}")
