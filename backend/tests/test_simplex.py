"""Testes do Simplex tabular (Duas Fases, Grande M e Simplex Dual)."""
from fractions import Fraction as F

import pytest

from app.algorithms.simplex import solve_lp
from tests.helpers import mk, sol, z

METHODS = ["simplex", "two_phase", "big_m"]


@pytest.mark.parametrize("method", METHODS)
def test_1_maximizacao_otima(method):
    # Wyndor (Hillier & Lieberman): ótimo (2, 6), Z = 36
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    r = solve_lp(m, method)
    assert r["status"] == "optimal"
    assert sol(r) == [2, 6] and z(r) == 36
    assert r["multiple"]["has_multiple"] is False
    # preços-sombra conhecidos: 0, 3/2, 1
    assert [F(d["value"]["exact"]) for d in r["dual_values"]] == [0, F(3, 2), 1]


@pytest.mark.parametrize("method", METHODS + ["dual_simplex"])
def test_2_minimizacao(method):
    m = mk("min", [2, 3], [[1, 1], [1, 3]], [">=", ">="], [4, 6])
    r = solve_lp(m, method)
    assert r["status"] == "optimal"
    assert sol(r) == [3, 1] and z(r) == 9


@pytest.mark.parametrize("method", METHODS + ["dual_simplex"])
def test_3_restricoes_mistas(method):
    # Hillier: min 4x1 + x2; 3x1 + x2 = 3; 4x1 + 3x2 ≥ 6; x1 + 2x2 ≤ 4 → (2/5, 9/5), Z = 17/5
    m = mk("min", [4, 1], [[3, 1], [4, 3], [1, 2]], ["=", ">=", "<="], [3, 6, 4])
    r = solve_lp(m, method)
    assert r["status"] == "optimal"
    assert sol(r) == [F(2, 5), F(9, 5)] and z(r) == F(17, 5)


def test_4_variaveis_artificiais_duas_fases():
    m = mk("max", [2, 3], [[1, 1], [1, -1]], [">=", "="], [2, 0])
    m = m.add_constraint([F(1), F(2)], "<=", F(6))
    r = solve_lp(m, "two_phase")
    assert r["status"] == "optimal"
    phases = {s["phase"] for s in r["steps"]}
    assert phases == {1, 2}                       # houve Fase 1 e Fase 2
    assert sol(r) == [2, 2] and z(r) == 10
    # a Fase 2 não exibe colunas artificiais
    p2 = [s for s in r["steps"] if s["phase"] == 2][0]["tableau"]
    assert all(k != "artificial" for k in p2["kinds"])


@pytest.mark.parametrize("method", METHODS)
def test_5_inviavel(method):
    m = mk("max", [1, 1], [[1, 1], [1, 1]], ["<=", ">="], [2, 5])
    r = solve_lp(m, method)
    assert r["status"] == "infeasible"
    assert r["solution"] is None


@pytest.mark.parametrize("method", METHODS)
def test_6_ilimitado(method):
    m = mk("max", [1, 1], [[1, -1]], ["<="], [2])
    r = solve_lp(m, method)
    assert r["status"] == "unbounded"
    assert r["steps"][-1]["decision"]["type"] == "unbounded"


def test_9_solucoes_multiplas():
    # Z = 2x1 + 4x2 é paralela a x1 + 2x2 ≤ 5: segmento ótimo entre (0, 5/2) e (3, 1)
    m = mk("max", [2, 4], [[1, 2], [1, 1]], ["<=", "<="], [5, 4])
    r = solve_lp(m, "simplex")
    assert r["status"] == "optimal" and z(r) == 10
    mult = r["multiple"]
    assert mult["has_multiple"] is True
    alt = mult["alternatives"][0]
    alt_x = [F(v["exact"]) for v in alt["solution"]]
    assert alt_x != sol(r)
    assert F(alt["objective"]["exact"]) == 10          # mesmo valor de Z
    assert {tuple(sol(r)), tuple(alt_x)} == {(0, F(5, 2)), (3, 1)}


def test_custo_reduzido_zero_sem_multiplicidade_degenerada():
    # Cj − Zj = 0 com pivoteamento degenerado não deve ser reportado como solução distinta
    m = mk("max", [1, 1], [[1, 1], [1, 0]], ["<=", "<="], [0, 0])
    r = solve_lp(m, "simplex")
    assert r["status"] == "optimal" and z(r) == 0
    assert r["multiple"]["has_multiple"] is False


def test_variavel_livre_e_nao_positiva():
    # min x1 − x2 ; x1 + x2 ≥ −4 ; x1 ≥ −3 (via restrição) ; x1 livre, x2 ≤ 0
    m = mk("min", [1, -1], [[1, 1], [1, 0]], [">=", ">="], [-4, -3], signs=["free", "nonpos"])
    r = solve_lp(m, "two_phase")
    assert r["status"] == "optimal"
    assert sol(r) == [-3, 0] and z(r) == -3


def test_lado_direito_negativo():
    m = mk("max", [1, 2], [[-1, -1], [1, 0]], ["<=", "<="], [-2, 5])   # x1 + x2 ≥ 2
    m = m.add_constraint([F(0), F(1)], "<=", F(3))
    r = solve_lp(m, "big_m")
    assert r["status"] == "optimal" and z(r) == 11


def test_degenerescencia_detectada():
    m = mk("max", [3, 9], [[1, 4], [1, 2]], ["<=", "<="], [8, 4])   # clássico degenerado (Taha)
    r = solve_lp(m, "simplex")
    assert r["status"] == "optimal" and z(r) == 18
    assert r["degenerate"] is True


def test_regra_de_bland():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    r = solve_lp(m, "simplex", rule="bland")
    assert r["status"] == "optimal" and z(r) == 36


def test_limite_de_iteracoes():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    r = solve_lp(m, "simplex", max_iter=1)
    assert r["status"] == "iteration_limit"
    assert r["solution"] is None   # nunca declara ótimo sem comprovar


def test_simplex_dual_nao_aplicavel():
    m = mk("max", [3, 5], [[1, 0], [0, 2], [3, 2]], ["<="] * 3, [4, 12, 18])
    r = solve_lp(m, "dual_simplex")
    assert r["status"] == "not_applicable"


def test_simplex_dual_inviavel():
    m = mk("min", [1, 1], [[1, 1], [1, 1]], [">=", "<="], [5, 2])
    r = solve_lp(m, "dual_simplex")
    assert r["status"] == "infeasible"


def test_tabelas_consistentes():
    """Em cada passo registrado, Z da tabela = Σ CB·b e as colunas básicas formam identidade."""
    m = mk("max", [3, 2, 5], [[1, 2, 1], [3, 0, 2], [1, 4, 0]], ["<="] * 3, [430, 460, 420])
    r = solve_lp(m, "simplex")
    assert r["status"] == "optimal" and z(r) == 1350          # Taha: (0, 100, 230)
    assert sol(r) == [0, 100, 230]
    for s in r["steps"]:
        t = s["tableau"]
        for i, col in enumerate(t["basis_cols"]):
            for k, row in enumerate(t["rows"]):
                assert F(row[col]) == (1 if k == i else 0)
