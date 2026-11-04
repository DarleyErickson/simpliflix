"""
Construção do problema DUAL e verificação da dualidade.

Regras de correspondência (primal → dual):

  Primal MAX                       Dual MIN
  ------------------------------   ------------------------------
  restrição i  (≤)                 y_i ≥ 0
  restrição i  (≥)                 y_i ≤ 0
  restrição i  (=)                 y_i livre
  variável x_j ≥ 0                 restrição dual j  (≥)
  variável x_j ≤ 0                 restrição dual j  (≤)
  variável x_j livre               restrição dual j  (=)

  Primal MIN                       Dual MAX
  restrição i  (≥)                 y_i ≥ 0
  restrição i  (≤)                 y_i ≤ 0
  restrição i  (=)                 y_i livre
  variável x_j ≥ 0                 restrição dual j  (≤)
  variável x_j ≤ 0                 restrição dual j  (≥)
  variável x_j livre               restrição dual j  (=)

Função objetivo dual: W = b·y; restrições duais: (Aᵀ y)_j (op) c_j.
O dual é resolvido pelo MESMO Simplex tabular (Duas Fases), com todas as tabelas.
"""
from __future__ import annotations

from typing import Optional

from app.algorithms.lp_model import SIGN_TEXT, LPModel
from app.algorithms.simplex import public, solve_lp
from app.utils.matrix_utils import transpose
from app.utils.numerical_utils import OP_SYMBOL, ZERO, fmt, num_json

_Y_SIGN = {
    "max": {"<=": "nonneg", ">=": "nonpos", "=": "free"},
    "min": {">=": "nonneg", "<=": "nonpos", "=": "free"},
}
_DUAL_OP = {
    "max": {"nonneg": ">=", "nonpos": "<=", "free": "="},
    "min": {"nonneg": "<=", "nonpos": ">=", "free": "="},
}


def build_dual(model: LPModel) -> LPModel:
    dsense = "min" if model.sense == "max" else "max"
    At = transpose(model.A)
    ynames = [f"Y{i + 1}" for i in range(model.m)]
    ysigns = [_Y_SIGN[model.sense][op] for op in model.ops]
    dops = [_DUAL_OP[model.sense][s] for s in model.var_signs]
    return LPModel(
        sense=dsense, c=list(model.b), A=[list(r) for r in At], ops=dops, b=list(model.c),
        var_names=ynames, var_domains=["continuous"] * model.m, var_signs=ysigns,
        con_names=[f"D{j + 1}" for j in range(model.n)], con_origin=["user"] * model.n,
        name=f"Dual de {model.name}",
    )


def dual_formulation(model: LPModel) -> dict:
    dual = build_dual(model)
    corr_cons = []
    for i in range(model.m):
        corr_cons.append({
            "primal": f"{model.con_names[i]}: {model.constraint_text(i)}",
            "dual_var": dual.var_names[i],
            "sign": SIGN_TEXT[dual.var_signs[i]],
            "rule": f"restrição {OP_SYMBOL[model.ops[i]]} em problema {model.sense.upper()} → "
                    f"{dual.var_names[i]} {SIGN_TEXT[dual.var_signs[i]]}",
        })
    corr_vars = []
    for j in range(model.n):
        corr_vars.append({
            "primal_var": f"{model.var_names[j]} {SIGN_TEXT[model.var_signs[j]]}",
            "dual_con": f"{dual.con_names[j]}: {dual.constraint_text(j)}",
            "rule": f"variável {SIGN_TEXT[model.var_signs[j]]} em problema {model.sense.upper()} → "
                    f"restrição dual {OP_SYMBOL[dual.ops[j]]}",
        })
    return {
        "primal": model.formulation(),
        "dual": dual.formulation(),
        "dual_model": dual.to_dict(),
        "matrix_A": [[fmt(v) for v in row] for row in model.A],
        "matrix_At": [[fmt(v) for v in row] for row in dual.A],
        "primal_vars": model.var_names,
        "dual_vars": dual.var_names,
        "b": [fmt(v) for v in model.b],
        "c": [fmt(v) for v in model.c],
        "correspondence_constraints": corr_cons,
        "correspondence_variables": corr_vars,
        "_dual": dual,
    }


def solve_dual(model: LPModel, primal: Optional[dict] = None, rule: str = "dantzig",
               max_iter: int = 200) -> dict:
    form = dual_formulation(model)
    dual = form.pop("_dual")
    dres = solve_lp(dual, "two_phase", rule=rule, max_iter=max_iter, record=True)
    if primal is None:
        primal = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False)
    out = {**form, "dual_result": public(dres)}
    ps, ds = primal["status"], dres["status"]
    rel = {"primal_status": ps, "dual_status": ds}
    if ps == "optimal" and ds == "optimal":
        zp = model.objective_at(primal["_x"])
        wd = dual.objective_at(dres["_x"])
        rel.update({
            "primal_objective": num_json(zp), "dual_objective": num_json(wd), "equal": zp == wd,
            "text": (f"Dualidade forte verificada: Z* (primal) = {fmt(zp)} = W* (dual) = {fmt(wd)}."
                     if zp == wd else f"ATENÇÃO: Z* = {fmt(zp)} difere de W* = {fmt(wd)}."),
        })
        # valores duais lidos na tabela ótima do primal (preços-sombra) × solução do dual
        y_tab = primal.get("dual_values") or []
        y_dual = dres["_x"]
        rows = []
        for i in range(model.m):
            yt = y_tab[i]["value"] if i < len(y_tab) else None
            rows.append({"constraint": model.con_names[i], "dual_var": dual.var_names[i],
                         "from_primal_tableau": yt, "from_dual_solution": num_json(y_dual[i])})
        rel["shadow_prices"] = rows
        # folgas complementares
        x = primal["_x"]
        comp = []
        for i in range(model.m):
            slack = model.b[i] - model.lhs_at(i, x)
            prod = y_dual[i] * slack
            comp.append({"pair": f"{dual.var_names[i]} · folga({model.con_names[i]})",
                         "text": f"{fmt(y_dual[i])} · {fmt(slack)} = {fmt(prod)}", "ok": prod == 0})
        for j in range(model.n):
            dslack = dual.lhs_at(j, y_dual) - dual.b[j]
            prod = x[j] * dslack
            comp.append({"pair": f"{model.var_names[j]} · folga({dual.con_names[j]})",
                         "text": f"{fmt(x[j])} · {fmt(dslack)} = {fmt(prod)}", "ok": prod == 0})
        rel["complementary_slackness"] = comp
    elif ps == "unbounded":
        rel["text"] = "O primal é ilimitado; pela teoria da dualidade, o dual é inviável."
    elif ps == "infeasible":
        rel["text"] = "O primal é inviável; o dual é ilimitado ou também inviável."
    else:
        rel["text"] = "Relação primal-dual não determinada (resolução incompleta)."
    out["relation"] = rel
    return out
