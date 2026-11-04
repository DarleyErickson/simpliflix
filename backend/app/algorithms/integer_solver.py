"""
Soluções inteiras: Branch and Bound, arredondamento e enumeração de conferência.

* ``integer_mask``  — quais variáveis devem ser inteiras. Se o usuário não marcou nenhuma,
  todas as variáveis de decisão são tratadas como inteiras (requisito da disciplina),
  e isso é informado.
* ``solve_rounding`` — arredonda a solução contínua ótima (meio para cima), verifica cada
  restrição e, se a proposta for inviável, procura combinações ⌊x⌋/⌈x⌉ próximas,
  apontando explicitamente que houve ajuste. Nunca declara o arredondamento ótimo.
* ``enumerate_integer_2d`` — para 2 variáveis e região limitada, enumera todos os pontos
  inteiros viáveis e confere o resultado do Branch and Bound.
"""
from __future__ import annotations

import math
from fractions import Fraction
from itertools import product
from typing import List, Optional

from app.algorithms.branch_and_bound import DEFAULT_MAX_NODES, branch_and_bound
from app.algorithms.lp_model import LPModel
from app.utils.numerical_utils import fmt, num_json

MAX_NEIGHBORS_VARS = 12
MAX_ENUM_POINTS = 250_000


def integer_mask(model: LPModel):
    mask = [d == "integer" for d in model.var_domains]
    if not any(mask):
        return [True] * model.n, True
    return mask, False


def _round_half_up(v: Fraction) -> int:
    return math.floor(v + Fraction(1, 2))


def _check(model: LPModel, x: List[Fraction]) -> List[dict]:
    out = []
    for i in range(model.m):
        lhs = model.lhs_at(i, x)
        out.append({"name": model.con_names[i], "expression": model.constraint_text(i),
                    "value": num_json(lhs), "rhs": num_json(model.b[i]), "operator": model.ops[i],
                    "satisfied": model.constraint_ok(i, x)})
    for j in range(model.n):
        if model.var_signs[j] != "free":
            ok = model.sign_ok(j, x[j])
            out.append({"name": f"{model.var_names[j]} {'≥' if model.var_signs[j] == 'nonneg' else '≤'} 0",
                        "expression": f"{model.var_names[j]} = {fmt(x[j])}", "value": num_json(x[j]),
                        "rhs": num_json(Fraction(0)), "operator": ">=" if model.var_signs[j] == "nonneg" else "<=",
                        "satisfied": ok, "sign": True})
    return out


def solve_rounding(model: LPModel, x_cont: Optional[List[Fraction]], mask: List[bool]) -> dict:
    if x_cont is None:
        return {"available": False,
                "message": "Não há solução contínua ótima para arredondar (o problema é inviável ou ilimitado)."}
    rounded = [Fraction(_round_half_up(v)) if mask[j] else v for j, v in enumerate(x_cont)]
    checks = _check(model, rounded)
    feasible = all(c["satisfied"] for c in checks)
    z = model.objective_at(rounded)
    res = {
        "available": True,
        "continuous": [{"name": model.var_names[j], **num_json(v)} for j, v in enumerate(x_cont)],
        "continuous_objective": num_json(model.objective_at(x_cont)),
        "rounded": [{"name": model.var_names[j], **num_json(v), "rounded": mask[j]} for j, v in enumerate(rounded)],
        "objective": num_json(z),
        "checks": checks,
        "feasible": feasible,
        "violated": [c["name"] for c in checks if not c["satisfied"]],
        "adjusted": None,
        "rule": "Arredondamento ao inteiro mais próximo (0,5 arredonda para cima) das variáveis inteiras.",
    }
    if feasible:
        res["message"] = ("A solução arredondada satisfaz todas as restrições (é viável), mas o arredondamento NÃO "
                          "garante otimalidade — compare com a solução inteira ótima.")
        return res
    res["message"] = ("A solução arredondada é INVIÁVEL: viola " + ", ".join(res["violated"]) +
                      ". O arredondamento convencional não produziu uma solução aceitável.")
    # ---- busca na vizinhança ⌊x⌋ / ⌈x⌉
    frac_idx = [j for j in range(model.n) if mask[j] and x_cont[j].denominator != 1]
    if len(frac_idx) > MAX_NEIGHBORS_VARS:
        res["adjusted"] = {"found": False, "tested": 0,
                           "message": f"Muitas variáveis fracionárias ({len(frac_idx)}) para testar todas as "
                                      f"combinações de piso/teto."}
        return res
    best, best_z, tested, feasible_count = None, None, 0, 0
    for choice in product((0, 1), repeat=len(frac_idx)):
        cand = list(rounded)
        for bit, j in zip(choice, frac_idx):
            cand[j] = Fraction(math.floor(x_cont[j]) + bit)
        tested += 1
        if model.is_feasible(cand):
            feasible_count += 1
            zc = model.objective_at(cand)
            if best is None or model.better(zc, best_z):
                best, best_z = cand, zc
    if best is None:
        res["adjusted"] = {"found": False, "tested": tested,
                           "message": f"Nenhuma das {tested} combinações de piso/teto é viável."}
    else:
        res["adjusted"] = {
            "found": True, "tested": tested, "feasible_count": feasible_count,
            "solution": [{"name": model.var_names[j], **num_json(v)} for j, v in enumerate(best)],
            "objective": num_json(best_z),
            "checks": _check(model, best),
            "message": (f"AJUSTE DO ARREDONDAMENTO: entre {tested} combinações de ⌊x⌋/⌈x⌉, {feasible_count} são "
                        f"viáveis; a melhor tem Z = {fmt(best_z)}. Esta é uma heurística, não uma prova de "
                        f"otimalidade."),
        }
    return res


def enumerate_integer_2d(model: LPModel, graph: Optional[dict]) -> Optional[dict]:
    """Conferência por enumeração completa (2 variáveis, ambas inteiras, região limitada)."""
    if model.n != 2 or graph is None or not graph.get("available") or not graph.get("feasible"):
        return None
    if graph.get("region_unbounded"):
        return {"performed": False, "message": "Região ilimitada: enumeração completa não aplicável."}
    vx = [v["x"] for v in graph["vertices"]]
    vy = [v["y"] for v in graph["vertices"]]
    if not vx:
        return None
    x0, x1 = math.ceil(min(vx) - 1e-9), math.floor(max(vx) + 1e-9)
    y0, y1 = math.ceil(min(vy) - 1e-9), math.floor(max(vy) + 1e-9)
    total = max(0, x1 - x0 + 1) * max(0, y1 - y0 + 1)
    if total > MAX_ENUM_POINTS:
        return {"performed": False, "message": f"Muitos pontos ({total}) para enumeração completa."}
    best, best_z, count = None, None, 0
    for xi in range(x0, x1 + 1):
        for yi in range(y0, y1 + 1):
            p = [Fraction(xi), Fraction(yi)]
            if model.is_feasible(p):
                count += 1
                z = model.objective_at(p)
                if best is None or model.better(z, best_z):
                    best, best_z = p, z
    return {
        "performed": True, "points_tested": total, "feasible_points": count,
        "best": [{"name": model.var_names[j], **num_json(best[j])} for j in range(2)] if best else None,
        "objective": num_json(best_z) if best else None,
        "_z": best_z,
        "message": (f"Enumeração de {total} pontos inteiros da caixa envolvente: {count} viáveis; "
                    + (f"melhor Z = {fmt(best_z)}." if best else "nenhum viável.")),
    }


def solve_integer(model: LPModel, max_nodes: int = DEFAULT_MAX_NODES, rule: str = "dantzig",
                  x_cont: Optional[List[Fraction]] = None, graph: Optional[dict] = None) -> dict:
    mask, assumed = integer_mask(model)
    bb = branch_and_bound(model, mask, max_nodes=max_nodes, rule=rule)
    rounding = solve_rounding(model, x_cont, mask)
    enum = None
    if model.n == 2 and all(mask):
        enum = enumerate_integer_2d(model, graph)
        if enum and enum.get("performed"):
            agrees = (bb.get("_z") == enum.get("_z"))
            enum["agrees"] = agrees
            enum["comparison"] = ("A enumeração confirma o valor ótimo inteiro obtido pelo Branch and Bound."
                                  if agrees else "ATENÇÃO: enumeração e Branch and Bound divergem.")
        if enum:
            enum.pop("_z", None)
    return {
        "assumed_all_integer": assumed,
        "integer_variables": [model.var_names[j] for j in range(model.n) if mask[j]],
        "note": ("Nenhuma variável foi marcada como inteira; para o cálculo da solução inteira, todas as variáveis "
                 "de decisão foram consideradas inteiras." if assumed else ""),
        "branch_and_bound": {k: v for k, v in bb.items() if not k.startswith("_")},
        "rounding": rounding,
        "enumeration": enum,
        "_bb": bb,
    }
