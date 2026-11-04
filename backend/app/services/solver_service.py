"""
Orquestração: executa os métodos solicitados e monta a resposta completa, incluindo as
verificações de consistência entre resultados algébricos, tabulares e gráficos.
"""
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional

from app.algorithms.algebraic_method import solve_algebraic
from app.algorithms.dual_model import solve_dual
from app.algorithms.graphical_method import solve_graphical
from app.algorithms.integer_solver import solve_integer
from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import METHODS, public, solve_lp
from app.services.model_service import model_summary
from app.services.visualization_service import overlay_solutions
from app.utils.numerical_utils import fmt, to_frac

TABULAR = ["simplex", "two_phase", "big_m", "dual_simplex"]


def _frac(numjson) -> Optional[Fraction]:
    return None if numjson is None else to_frac(numjson["exact"])


def solve_all(model: LPModel, methods: List[str], rule: str, max_iter: int, max_nodes: int,
              include_integer: bool = True, include_dual: bool = True) -> dict:
    methods = list(methods)
    if not any(m in TABULAR for m in methods):
        methods.append("simplex")   # o Simplex tabular é obrigatório
    tabular = {}
    for m in TABULAR:
        if m in methods:
            tabular[m] = solve_lp(model, m, rule=rule, max_iter=max_iter, record=True)

    # método principal: o primeiro tabular aplicável (Simplex Dual pode não se aplicar)
    primary_key = next((m for m in TABULAR if m in tabular and tabular[m]["status"] != "not_applicable"), None)
    if primary_key is None:
        tabular["two_phase"] = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=True)
        primary_key = "two_phase"
    primary = tabular[primary_key]

    graph = None
    if "graphical" in methods or model.n == 2:
        graph = solve_graphical(model, primary)
    algebraic = solve_algebraic(model) if "algebraic" in methods else None

    integer = None
    if include_integer:
        integer = solve_integer(model, max_nodes=max_nodes, rule=rule, x_cont=primary.get("_x"), graph=graph)
    dual = solve_dual(model, primary, rule=rule, max_iter=max_iter) if include_dual else None

    if graph is not None:
        graph = overlay_solutions(graph, primary, integer)

    analysis = consistency(model, primary, tabular, graph, algebraic, integer, dual)

    out = {
        "model": model_summary(model),
        "model_json": model.to_dict(),
        "methods_requested": methods,
        "primary_method": primary_key,
        "primary_label": METHODS[primary_key],
        "summary": {
            "status": primary["status"],
            "status_label": primary["status_label"],
            "message": primary["message"],
            "solution": primary["solution"],
            "objective_value": primary["objective_value"],
            "iterations": primary["iterations"],
            "multiple": primary.get("multiple"),
            "degenerate": primary.get("degenerate"),
            "constraints": primary.get("constraints"),
            "unbounded_variable": primary.get("unbounded_variable"),
        },
        "tabular": {k: public(v) for k, v in tabular.items()},
        "graphical": ({k: v for k, v in graph.items() if not k.startswith("_")} if graph else
                      {"available": False, "message": "Método gráfico não solicitado."}),
        "algebraic": algebraic,
        "integer": ({k: v for k, v in integer.items() if not k.startswith("_")} if integer else None),
        "dual": dual,
        "analysis": analysis,
    }
    return out


def consistency(model, primary, tabular, graph, algebraic, integer, dual) -> dict:
    checks = []

    def add(label, ok, detail):
        checks.append({"label": label, "ok": bool(ok), "detail": detail})

    st = primary["status"]
    # ---- concordância entre os métodos tabulares
    for k, r in tabular.items():
        if r is primary or r["status"] == "not_applicable":
            continue
        if r["status"] == st == "optimal":
            a, b = _frac(r["objective_value"]), _frac(primary["objective_value"])
            add(f"{METHODS[k]} × {METHODS[next(x for x in tabular if tabular[x] is primary)]}", a == b,
                f"Z = {fmt(a)} e Z = {fmt(b)}")
        else:
            add(f"Status do {METHODS[k]}", r["status"] == st, f"{r['status_label']} / {primary['status_label']}")

    if st == "optimal":
        x = primary["_x"]
        z = model.objective_at(x)
        tz = primary.get("tableau_objective")
        tz_val = to_frac(tz) if isinstance(tz, str) else None
        add("Z da tabela final = c·x avaliado", tz_val == z,
            f"Tabela: Z = {tz if isinstance(tz, str) else tz}; avaliação direta: Z = {fmt(z)}")
        add("Solução satisfaz todas as restrições", model.is_feasible(x),
            "Substituição dos valores ótimos em cada restrição e nas condições de sinal.")
        if graph and graph.get("available"):
            g = graph.get("optimal")
            if g:
                gz = to_frac(g["z_text"])
                on_set = any(abs(p["x"] - float(x[0])) < 1e-9 and abs(p["y"] - float(x[1])) < 1e-9
                             for p in g["points"])
                same = gz == z
                det = f"Gráfico: Z = {g['z_text']}; Simplex: Z = {fmt(z)}"
                if not on_set:
                    det += " (o ponto do Simplex está no conjunto ótimo, entre os vértices destacados)" if same else ""
                add("Método gráfico × Simplex", same, det)
            else:
                add("Método gráfico × Simplex", False, graph.get("message", ""))
        if algebraic and algebraic.get("best_objective"):
            az = _frac(algebraic["best_objective"])
            add("Método algébrico × Simplex", az == z, f"Melhor solução básica viável: Z = {fmt(az)}")
        if dual and dual.get("relation", {}).get("dual_objective"):
            rel = dual["relation"]
            add("Dualidade forte (Z* = W*)", rel["equal"], rel["text"])
        if integer:
            bb = integer["_bb"]
            if bb.get("_z") is not None:
                better_or_equal = not model.better(bb["_z"], z)
                add("Ótimo inteiro não supera o contínuo", better_or_equal,
                    f"Z inteiro = {fmt(bb['_z'])}; Z contínuo = {fmt(z)}")
            en = integer.get("enumeration")
            if en and en.get("performed"):
                add("Branch and Bound × enumeração de pontos inteiros", en.get("agrees"), en.get("message", ""))
    elif st == "infeasible":
        if graph and graph.get("available"):
            add("Método gráfico confirma inviabilidade", graph["status"] == "infeasible", graph.get("message", ""))
        if algebraic and algebraic.get("status") in ("no_feasible", "ok"):
            add("Método algébrico: nenhuma solução básica viável", algebraic["status"] == "no_feasible",
                algebraic.get("message", ""))
    elif st == "unbounded":
        if graph and graph.get("available"):
            add("Método gráfico confirma ilimitação", graph["status"] == "unbounded", graph.get("message", ""))
        if dual and dual.get("dual_result"):
            add("Dual inviável (primal ilimitado)", dual["dual_result"]["status"] == "infeasible",
                dual["dual_result"]["status_label"])
    all_ok = all(c["ok"] for c in checks)
    return {"checks": checks, "all_ok": all_ok,
            "message": ("Todos os resultados são consistentes entre si." if all_ok else
                        "Há divergências entre os métodos; verifique os detalhes.")}
