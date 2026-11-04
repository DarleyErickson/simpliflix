"""
Branch and Bound para Programação Linear Inteira (pura ou mista).

Cada nó é uma relaxação linear resolvida pelo PRÓPRIO Simplex tabular do projeto
(Duas Fases), acrescida das restrições de ramificação acumuladas no caminho até a raiz.

Algoritmo (busca pelo melhor limitante, "best-bound"):
  1. Resolve-se a relaxação linear da raiz.
  2. Um nó é PODADO quando:
       • a relaxação é inviável (poda por inviabilidade);
       • a solução da relaxação já é inteira (poda por integralidade → candidata a incumbente);
       • seu valor Z não é melhor que a melhor solução inteira conhecida (poda por limitante).
  3. Caso contrário, escolhe-se a variável inteira mais fracionária x_j = v e criam-se
     dois subproblemas:  x_j ≤ ⌊v⌋   e   x_j ≥ ⌈v⌉.
  4. A busca termina quando não há nós abertos (otimalidade COMPROVADA) ou quando o
     limite de nós é atingido (melhor solução encontrada, sem prova de otimalidade).
"""
from __future__ import annotations

import heapq
import math
from fractions import Fraction
from typing import List, Optional

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import solve_lp
from app.utils.numerical_utils import ZERO, fmt, num_json

DEFAULT_MAX_NODES = 500


def _frac_part(v: Fraction) -> Fraction:
    return v - math.floor(v)


def branch_and_bound(model: LPModel, int_mask: List[bool], max_nodes: int = DEFAULT_MAX_NODES,
                     rule: str = "dantzig") -> dict:
    names = model.var_names
    sgn = 1 if model.sense == "max" else -1
    nodes: List[dict] = []
    heap = []
    incumbent_x: Optional[List[Fraction]] = None
    incumbent_z: Optional[Fraction] = None
    incumbent_node: Optional[int] = None
    stop_reason = None
    counter = 0

    def solve_node(branches, parent, depth, label):
        nonlocal counter
        sub = model.copy()
        for (j, op, val) in branches:
            coeffs = [ZERO] * model.n
            coeffs[j] = Fraction(1)
            sub = sub.add_constraint(coeffs, op, Fraction(val), name=f"{names[j]} {'≤' if op == '<=' else '≥'} {val}",
                                     origin="branch")
        res = solve_lp(sub, "two_phase", rule=rule, record=False)
        node = {
            "id": counter, "parent": parent, "depth": depth, "branch": label,
            "constraints": [f"{names[j]} {'≤' if op == '<=' else '≥'} {val}" for (j, op, val) in branches],
            "branches_raw": [[j, op, int(val)] for (j, op, val) in branches],
            "lp_status": res["status"], "iterations": res["iterations"], "children": [],
            "solution": None, "objective": None, "status": None, "reason": "",
        }
        counter += 1
        if parent is not None:
            nodes[parent]["children"].append(node["id"])
        x = res.get("_x")
        if res["status"] == "optimal":
            z = model.objective_at(x)
            node["solution"] = [{"name": names[j], **num_json(x[j])} for j in range(model.n)]
            node["objective"] = num_json(z)
            node["_x"], node["_z"] = x, z
        nodes.append(node)
        return node

    def classify(node):
        """Classifica um nó recém-resolvido; retorna True se deve ir para a fila."""
        nonlocal incumbent_x, incumbent_z, incumbent_node
        st = node["lp_status"]
        if st == "infeasible":
            node["status"] = "infeasible"
            node["reason"] = "Relaxação inviável: o nó é podado (poda por inviabilidade)."
            return False
        if st == "unbounded":
            node["status"] = "unbounded"
            node["reason"] = "Relaxação ilimitada: o Branch and Bound não pode limitar este ramo."
            return False
        if st != "optimal":
            node["status"] = "error"
            node["reason"] = "A relaxação não foi resolvida até a otimalidade (limite de iterações)."
            return False
        x, z = node["_x"], node["_z"]
        frac = [j for j in range(model.n) if int_mask[j] and x[j].denominator != 1]
        if not frac:
            if incumbent_z is None or model.better(z, incumbent_z):
                old = incumbent_z
                incumbent_x, incumbent_z, incumbent_node = x, z, node["id"]
                node["status"] = "incumbent"
                node["reason"] = ("Solução inteira (poda por integralidade). Torna-se a nova incumbente"
                                  + (f", melhorando Z de {fmt(old)} para {fmt(z)}." if old is not None else
                                     f" com Z = {fmt(z)}."))
            else:
                node["status"] = "integer"
                node["reason"] = (f"Solução inteira com Z = {fmt(z)}, mas não supera a incumbente "
                                  f"(Z = {fmt(incumbent_z)}).")
            return False
        if incumbent_z is not None and not model.better(z, incumbent_z):
            node["status"] = "pruned_bound"
            node["reason"] = (f"Poda por limitante: Z da relaxação ({fmt(z)}) não é melhor que a incumbente "
                              f"({fmt(incumbent_z)}).")
            return False
        node["status"] = "open"
        return True

    def push(node):
        heapq.heappush(heap, (-sgn * node["_z"], node["id"]))

    root = solve_node([], None, 0, "Raiz (relaxação linear)")
    root_status = root["lp_status"]
    if classify(root):
        push(root)

    while heap:
        if counter >= max_nodes:
            stop_reason = "node_limit"
            break
        _, nid = heapq.heappop(heap)
        node = nodes[nid]
        z = node["_z"]
        if incumbent_z is not None and not model.better(z, incumbent_z):
            node["status"] = "pruned_bound"
            node["reason"] = (f"Poda por limitante: Z da relaxação ({fmt(z)}) não é melhor que a incumbente "
                              f"({fmt(incumbent_z)}), encontrada depois da criação deste nó.")
            continue
        x = node["_x"]
        frac = [j for j in range(model.n) if int_mask[j] and x[j].denominator != 1]
        # variável mais fracionária (parte fracionária mais próxima de 1/2); empate → menor índice
        j = min(frac, key=lambda k: (abs(_frac_part(x[k]) - Fraction(1, 2)), k))
        v = x[j]
        lo, hi = math.floor(v), math.ceil(v)
        node["status"] = "branched"
        node["branch_var"] = names[j]
        node["reason"] = (f"{names[j]} = {fmt(v)} não é inteira. Ramifica-se em {names[j]} ≤ {lo} e "
                          f"{names[j]} ≥ {hi}.")
        base = [tuple(b) for b in node["_branches"]] if "_branches" in node else []
        for op, val in (("<=", lo), (">=", hi)):
            if counter >= max_nodes:
                stop_reason = "node_limit"
                break
            br = base + [(j, op, val)]
            child = solve_node(br, nid, node["depth"] + 1, f"{names[j]} {'≤' if op == '<=' else '≥'} {val}")
            child["_branches"] = br
            if classify(child):
                push(child)
        if stop_reason:
            break
        if any(n["status"] == "unbounded" for n in nodes):
            stop_reason = "unbounded"
            break

    # nós que ficaram na fila sem exploração
    for _, nid in heap:
        if nodes[nid]["status"] == "open":
            nodes[nid]["status"] = "pending"
            nodes[nid]["reason"] = "Nó não explorado (busca interrompida)."

    # ---------------- conclusão
    if root_status == "infeasible":
        status, msg = "infeasible", "A relaxação linear é inviável, logo o problema inteiro também é inviável."
    elif root_status == "unbounded" or stop_reason == "unbounded":
        status = "unbounded"
        msg = ("A relaxação linear é ilimitada: o Branch and Bound não consegue comprovar um ótimo inteiro "
               "(o problema inteiro pode ser ilimitado ou inviável).")
    elif stop_reason == "node_limit":
        if incumbent_x is not None:
            status = "feasible"
            msg = (f"Limite de {max_nodes} nós atingido. A melhor solução inteira viável encontrada tem "
                   f"Z = {fmt(incumbent_z)}, mas sua otimalidade NÃO foi comprovada.")
        else:
            status = "limit_no_solution"
            msg = f"Limite de {max_nodes} nós atingido sem encontrar solução inteira viável."
    elif incumbent_x is not None:
        status = "optimal"
        msg = ("Solução inteira comprovadamente ótima: todos os nós foram podados (por inviabilidade, "
               "integralidade ou limitante), não restando ramo capaz de melhorar a incumbente.")
    elif root_status != "optimal":
        status, msg = "error", "Não foi possível resolver a relaxação linear da raiz."
    else:
        status, msg = "infeasible", "Todos os ramos são inviáveis: não existe solução inteira viável."

    # incumbentes que foram superadas por uma solução inteira melhor encontrada depois
    for n in nodes:
        if n["status"] == "incumbent" and n["id"] != incumbent_node:
            n["status"] = "superseded"
            n["reason"] += f" Posteriormente superada pela solução do nó N{incumbent_node} (Z = {fmt(incumbent_z)})."

    counts = {}
    for n in nodes:
        counts[n["status"]] = counts.get(n["status"], 0) + 1
    for n in nodes:
        n.pop("_x", None); n.pop("_z", None); n.pop("_branches", None)
    added = sorted({c for n in nodes for c in n["constraints"]})
    return {
        "status": status,
        "message": msg,
        "proven_optimal": status == "optimal",
        "solution": ([{"name": names[j], "domain": model.var_domains[j], "integer": int_mask[j],
                       **num_json(incumbent_x[j])} for j in range(model.n)] if incumbent_x is not None else None),
        "objective_value": num_json(incumbent_z) if incumbent_z is not None else None,
        "incumbent_node": incumbent_node,
        "nodes": nodes,
        "node_count": len(nodes),
        "status_counts": counts,
        "added_constraints": added,
        "max_nodes": max_nodes,
        "integer_variables": [names[j] for j in range(model.n) if int_mask[j]],
        "_x": incumbent_x,
        "_z": incumbent_z,
    }
