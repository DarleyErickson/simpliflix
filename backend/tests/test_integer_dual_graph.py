"""Testes de solução inteira, arredondamento, dual, método gráfico e método algébrico."""
from fractions import Fraction as F

from app.algorithms.algebraic_method import solve_algebraic
from app.algorithms.dual_model import build_dual, solve_dual
from app.algorithms.graphical_method import solve_graphical
from app.algorithms.integer_solver import solve_integer
from app.algorithms.simplex import solve_lp
from tests.helpers import mk, sol, z


def test_7_solucao_inteira_otima():
    m = mk("max", [5, 8], [[1, 1], [5, 9]], ["<=", "<="], [6, 45], domains=["integer", "integer"])
    lp = solve_lp(m, "two_phase", record=False)
    assert z(lp) == F(165, 4)
    graph = solve_graphical(m, lp)
    res = solve_integer(m, x_cont=lp["_x"], graph=graph)
    bb = res["branch_and_bound"]
    assert bb["status"] == "optimal" and bb["proven_optimal"]
    assert [F(v["exact"]) for v in bb["solution"]] == [0, 5]
    assert F(bb["objective_value"]["exact"]) == 40
    assert res["enumeration"]["agrees"] is True


def test_8_arredondamento_inviavel():
    m = mk("max", [5, 8], [[1, 1], [5, 9]], ["<=", "<="], [6, 45], domains=["integer", "integer"])
    lp = solve_lp(m, "two_phase", record=False)
    res = solve_integer(m, x_cont=lp["_x"])
    r = res["rounding"]
    assert [F(v["exact"]) for v in r["rounded"]] == [2, 4]   # 2,25 → 2 ; 3,75 → 4
    assert r["feasible"] is False and "R2" in r["violated"]
    assert r["adjusted"]["found"] is True                    # ajuste explícito, não silencioso
    assert F(r["adjusted"]["objective"]["exact"]) == 39      # (3, 3)


def test_inteira_mista_e_mascara_padrao():
    m = mk("max", [1, 1], [[2, 2]], ["<="], [7])               # nenhuma marcada → todas inteiras
    res = solve_integer(m, x_cont=None)
    assert res["assumed_all_integer"] is True
    assert F(res["branch_and_bound"]["objective_value"]["exact"]) == 3


def test_inteira_inviavel():
    # 2x1 = 1 não tem solução inteira
    m = mk("max", [1], [[2]], ["="], [1], domains=["integer"])
    res = solve_integer(m)
    assert res["branch_and_bound"]["status"] == "infeasible"


def test_inteira_limite_de_nos():
    m = mk("max", [5, 8], [[1, 1], [5, 9]], ["<=", "<="], [6, 45], domains=["integer", "integer"])
    res = solve_integer(m, max_nodes=2)
    bb = res["branch_and_bound"]
    assert bb["proven_optimal"] is False


def test_10_dual():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    d = build_dual(m)
    assert d.sense == "min" and d.ops == [">=", ">="] and d.var_signs == ["nonneg"] * 3
    assert d.c == [4, 12, 18] and d.b == [3, 5]
    primal = solve_lp(m, "two_phase", record=False)
    out = solve_dual(m, primal)
    rel = out["relation"]
    assert rel["equal"] is True and F(rel["dual_objective"]["exact"]) == 36
    assert all(c["ok"] for c in rel["complementary_slackness"])
    for row in rel["shadow_prices"]:
        assert row["from_primal_tableau"]["exact"] == row["from_dual_solution"]["exact"]


def test_dual_regras_de_sinal():
    m = mk("min", [1, 2, 3], [[1, 1, 1], [1, -1, 0]], [">=", "="], [4, 1], signs=["nonneg", "nonpos", "free"])
    d = build_dual(m)
    assert d.sense == "max"
    assert d.var_signs == ["nonneg", "free"]          # ≥ em MIN → y ≥ 0 ; = → livre
    assert d.ops == ["<=", ">=", "="]                 # x≥0 → ≤ ; x≤0 → ≥ ; livre → =


def test_dual_de_problema_ilimitado():
    m = mk("max", [1, 1], [[1, -1]], ["<="], [2])
    out = solve_dual(m)
    assert out["relation"]["primal_status"] == "unbounded"
    assert out["dual_result"]["status"] == "infeasible"


def test_grafico_regiao_e_otimo():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    g = solve_graphical(m, solve_lp(m, record=False))
    assert g["status"] == "optimal"
    verts = {(v["x_text"], v["y_text"]) for v in g["vertices"]}
    assert verts == {("0", "0"), ("4", "0"), ("4", "3"), ("2", "6"), ("0", "6")}
    assert g["optimal"]["z_text"] == "36"
    assert g["region_unbounded"] is False
    assert any(lv["optimal"] for lv in g["levels"])


def test_grafico_multiplas_segmento():
    m = mk("max", [2, 4], [[1, 2], [1, 1]], ["<=", "<="], [5, 4])
    g = solve_graphical(m, solve_lp(m, record=False))
    assert g["optimal_set"]["type"] == "segment"


def test_grafico_ilimitado_e_inviavel():
    m = mk("max", [1, 1], [[1, -1]], ["<="], [2])
    g = solve_graphical(m, solve_lp(m, record=False))
    assert g["status"] == "unbounded" and g["region_unbounded"]
    m2 = mk("max", [1, 1], [[1, 1], [1, 1]], ["<=", ">="], [2, 5])
    g2 = solve_graphical(m2, solve_lp(m2, record=False))
    assert g2["status"] == "infeasible"


def test_grafico_regiao_ilimitada_com_otimo():
    m = mk("min", [2, 3], [[1, 1], [1, 3]], [">=", ">="], [4, 6])
    g = solve_graphical(m, solve_lp(m, record=False))
    assert g["status"] == "optimal" and g["region_unbounded"] is True
    assert g["optimal"]["z_text"] == "9"


def test_grafico_indisponivel_3_variaveis():
    m = mk("max", [1, 1, 1], [[1, 1, 1]], ["<="], [3])
    assert solve_graphical(m)["available"] is False


def test_metodo_algebrico():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    a = solve_algebraic(m)
    assert a["total_combinations"] == 10
    assert a["feasible_count"] == 5
    assert a["best_objective"]["exact"] == "36"
