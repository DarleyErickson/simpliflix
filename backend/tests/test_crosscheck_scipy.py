"""
Validação cruzada com SciPy (USO EXCLUSIVO NOS TESTES).

Gera centenas de PPLs aleatórios (MAX/MIN, ≤/≥/=, variáveis livres) e compara status e
valor ótimo do Simplex próprio (Duas Fases e Grande M) com scipy.optimize.linprog (HiGHS).
"""
import random
from fractions import Fraction as F

import pytest

scipy_opt = pytest.importorskip("scipy.optimize")

from app.algorithms.integer_solver import solve_integer  # noqa: E402
from app.algorithms.simplex import solve_lp  # noqa: E402
from tests.helpers import mk  # noqa: E402

STATUS = {0: "optimal", 2: "infeasible", 3: "unbounded"}


def scipy_solve(m, integrality=None):
    c = [float(v) * (-1 if m.sense == "max" else 1) for v in m.c]
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for row, op, b in zip(m.A, m.ops, m.b):
        r = [float(v) for v in row]
        if op == "<=":
            A_ub.append(r); b_ub.append(float(b))
        elif op == ">=":
            A_ub.append([-v for v in r]); b_ub.append(-float(b))
        else:
            A_eq.append(r); b_eq.append(float(b))
    bounds = [(0, None) if s == "nonneg" else (None, 0) if s == "nonpos" else (None, None) for s in m.var_signs]
    res = scipy_opt.linprog(c, A_ub=A_ub or None, b_ub=b_ub or None, A_eq=A_eq or None, b_eq=b_eq or None,
                            bounds=bounds, method="highs", integrality=integrality)
    zval = None if res.status != 0 else (-res.fun if m.sense == "max" else res.fun)
    return STATUS.get(res.status, "other"), zval


def random_model(rng):
    n = rng.randint(2, 4)
    mcount = rng.randint(1, 4)
    c = [rng.randint(-5, 9) for _ in range(n)]
    if all(v == 0 for v in c):
        c[0] = 1
    A, ops, b = [], [], []
    for _ in range(mcount):
        row = [rng.randint(-3, 8) for _ in range(n)]
        if all(v == 0 for v in row):
            row[0] = 1
        A.append(row)
        ops.append(rng.choice(["<=", "<=", "<=", ">=", "="]))
        b.append(rng.randint(-5, 20))
    signs = [rng.choice(["nonneg"] * 6 + ["nonpos", "free"]) for _ in range(n)]
    return mk(rng.choice(["max", "min"]), c, A, ops, b, signs=signs)


@pytest.mark.parametrize("seed", range(300))
def test_simplex_vs_scipy(seed):
    rng = random.Random(seed)
    m = random_model(rng)
    st, zref = scipy_solve(m)
    if st == "other":
        pytest.skip("status SciPy não comparável")
    for method in ("two_phase", "big_m"):
        r = solve_lp(m, method, record=False)
        assert r["status"] == st, f"{method}: {r['status']} vs scipy {st}"
        if st == "optimal":
            assert abs(float(F(r["objective_value"]["exact"])) - zref) < 1e-6
            assert m.is_feasible(r["_x"])
    if st == "optimal":
        rd = solve_lp(m, "dual_simplex", record=False)
        if rd["status"] != "not_applicable":
            assert abs(float(F(rd["objective_value"]["exact"])) - zref) < 1e-6


@pytest.mark.parametrize("seed", range(80))
def test_branch_and_bound_vs_scipy_milp(seed):
    rng = random.Random(1000 + seed)
    n = rng.randint(2, 3)
    c = [rng.randint(1, 9) for _ in range(n)]
    A = [[rng.randint(1, 9) for _ in range(n)] for _ in range(rng.randint(1, 3))]
    b = [rng.randint(5, 40) for _ in A]
    m = mk("max", c, A, ["<="] * len(A), b, domains=["integer"] * n)
    st, zref = scipy_solve(m, integrality=[1] * n)
    res = solve_integer(m, max_nodes=2000)
    bb = res["branch_and_bound"]
    assert bb["status"] == "optimal"
    assert abs(float(F(bb["objective_value"]["exact"])) - zref) < 1e-6
