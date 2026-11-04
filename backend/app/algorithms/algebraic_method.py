"""
Método Algébrico (enumeração de soluções básicas).

Com o modelo na forma padrão  A·x = b  (m equações, N variáveis, incluindo folgas e
excessos), cada escolha de m variáveis básicas define um sistema B·x_B = b:
  • B singular             → a combinação não forma base;
  • x_B com algum valor < 0 → solução básica INVIÁVEL;
  • x_B ≥ 0                → solução básica VIÁVEL (vértice da região viável).
A melhor solução básica viável é a ótima, desde que o problema seja limitado
(o que é confirmado pelo Simplex). O número de combinações é C(N, m).
"""
from __future__ import annotations

from itertools import combinations
from math import comb

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import build_standard_form, original_solution  # noqa: F401
from app.utils.matrix_utils import rank_exact, solve_exact
from app.utils.numerical_utils import ZERO, fmt, num_json

MAX_COMBINATIONS = 3000


def solve_algebraic(model: LPModel) -> dict:
    sf = build_standard_form(model, "algebraic")
    m, N = sf.m, sf.N
    total = comb(N, m)
    base = {
        "method": "algebraic",
        "method_label": "Método Algébrico",
        "variables": sf.names,
        "equations": [
            " + ".join(f"{fmt(v)}{n}" for v, n in zip(row, sf.names) if v != 0) + f" = {fmt(b)}"
            for row, b in zip(sf.rows, sf.rhs)
        ],
        "notes": sf.var_notes,
        "m": m, "N": N, "total_combinations": total,
    }
    if total > MAX_COMBINATIONS:
        base.update({
            "status": "too_large",
            "message": f"O modelo gera C({N}, {m}) = {total} combinações de bases, acima do limite de "
                       f"{MAX_COMBINATIONS} para enumeração. Utilize o Simplex Tabular.",
            "solutions": [],
        })
        return base
    if rank_exact(sf.rows) < m:
        base["rank_note"] = ("As equações são linearmente dependentes (há restrição redundante); bases com m "
                             "colunas serão singulares.")
    sols = []
    best = None
    for combo in combinations(range(N), m):
        B = [[sf.rows[i][j] for j in combo] for i in range(m)]
        xb = solve_exact(B, sf.rhs)
        entry = {"basic": [sf.names[j] for j in combo],
                 "nonbasic": [sf.names[j] for j in range(N) if j not in combo]}
        if xb is None:
            entry.update({"status": "singular", "values": None, "objective": None})
            sols.append(entry)
            continue
        vals = [ZERO] * N
        for j, v in zip(combo, xb):
            vals[j] = v
        x = [ZERO] * model.n
        for col, (j, coef) in sf.var_map.items():
            x[j] += coef * vals[col]
        feasible = all(v >= 0 for v in xb)
        z = model.objective_at(x)
        entry.update({
            "status": "feasible" if feasible else "infeasible",
            "values": {sf.names[j]: fmt(v) for j, v in zip(combo, xb)},
            "x": [fmt(v) for v in x],
            "x_float": [float(v) for v in x],
            "objective": num_json(z),
            "_z": z,
            "degenerate": feasible and any(v == 0 for v in xb),
        })
        sols.append(entry)
        if feasible and (best is None or model.better(z, best)):
            best = z
    optimal_idx = []
    if best is not None:
        for idx, s in enumerate(sols):
            if s["status"] == "feasible" and s["_z"] == best:
                s["optimal"] = True
                optimal_idx.append(idx)
    # pontos distintos ótimos (bases degeneradas podem repetir o mesmo ponto)
    distinct = {tuple(sols[i]["x"]) for i in optimal_idx}
    for s in sols:
        s.pop("_z", None)
    feas = sum(1 for s in sols if s["status"] == "feasible")
    base.update({
        "status": "ok" if best is not None else "no_feasible",
        "solutions": sols,
        "feasible_count": feas,
        "infeasible_count": sum(1 for s in sols if s["status"] == "infeasible"),
        "singular_count": sum(1 for s in sols if s["status"] == "singular"),
        "best_objective": num_json(best) if best is not None else None,
        "optimal_indices": optimal_idx,
        "distinct_optimal_points": [list(p) for p in distinct],
        "message": (f"{feas} solução(ões) básica(s) viável(is) entre {total} combinações. A melhor tem "
                    f"Z = {fmt(best)}." if best is not None else
                    "Nenhuma solução básica viável: o problema é inviável."),
    })
    return base
