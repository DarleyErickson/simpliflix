"""
Núcleo do Método Simplex Tabular (implementação própria do SimpliFlix).

Este módulo contém:
  * ``build_standard_form``: conversão do modelo para a forma padrão (folgas, excessos,
    artificiais, troca de sinal de variáveis ≤ 0, divisão de variáveis livres);
  * ``run_iterations``: o laço iterativo do Simplex primal (entrada → razão mínima →
    saída → pivô → atualização → teste de otimalidade), registrando cada tabela;
  * extração da solução, análise de restrições, valores duais (preços-sombra) e
    detecção de soluções ótimas múltiplas;
  * ``solve_lp``: fachada que despacha para Duas Fases, Grande M ou Simplex Dual.

Regras de escolha (política de desempate / anticiclagem):
  * "dantzig" (padrão): entra a variável com o custo reduzido mais favorável
    (maior Cj − Zj em MAX, menor em MIN); empates → menor índice de coluna.
  * "bland": entra a variável favorável de menor índice.
  * Saída: menor razão b_i / a_ik (a_ik > 0); empates → variável básica de menor índice.
  * Se uma base se repetir (ciclagem), o algoritmo passa automaticamente à regra de Bland,
    que garante término.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex_tableau import Tableau
from app.utils.numerical_utils import (
    FLIP_OP, ONE, OP_SYMBOL, ZERO, MValue, fmt, linear_text, num_json,
)

DEFAULT_MAX_ITER = 200

STATUS_LABEL = {
    "optimal": "Solução ótima encontrada",
    "infeasible": "Problema inviável",
    "unbounded": "Problema ilimitado",
    "iteration_limit": "Limite de iterações atingido",
    "not_applicable": "Método não aplicável a este modelo",
}

KIND_LABEL = {
    "decision": "decisão",
    "slack": "folga",
    "surplus": "excesso",
    "artificial": "artificial",
}


# =============================================================================
# Forma padrão
# =============================================================================
@dataclass
class StandardForm:
    names: List[str]
    kinds: List[str]
    rows: List[List[Fraction]]
    rhs: List[Fraction]
    row_ops: List[str]                       # operador original (após eventual inversão)
    row_orig: List[int]                      # restrição original correspondente
    row_sign: List[int]                      # +1 ou −1 (linha multiplicada por −1)
    identity_col: List[Optional[int]]        # coluna identidade (folga/artificial) de cada linha
    var_map: Dict[int, Tuple[int, int]]      # coluna → (variável original, coeficiente ±1)
    artificial_cols: List[int]
    notes: List[str] = field(default_factory=list)
    var_notes: List[str] = field(default_factory=list)

    @property
    def m(self):
        return len(self.rows)

    @property
    def N(self):
        return len(self.names)

    def original_costs(self, model: LPModel) -> List[MValue]:
        costs = [MValue() for _ in range(self.N)]
        for col, (j, coef) in self.var_map.items():
            costs[col] = MValue(model.c[j] * coef)
        return costs

    def lines(self, costs: List[MValue], sense: str, obj_name: str = "Z") -> dict:
        names = self.names
        obj = f"{sense.upper()} {obj_name} = {linear_text(costs, names, zero_terms=True)}"
        cons = [f"{linear_text(self.rows[i], names)} = {fmt(self.rhs[i])}" for i in range(self.m)]
        return {
            "objective": obj,
            "constraints": cons,
            "nonnegativity": f"{', '.join(names)} ≥ 0",
            "notes": self.notes + self.var_notes,
            "variables": [
                {"name": n, "kind": k, "kind_label": KIND_LABEL[k]} for n, k in zip(self.names, self.kinds)
            ],
        }


def _decision_columns(model: LPModel):
    names, kinds, cols, var_map, notes = [], [], [], {}, []
    for j in range(model.n):
        nm = model.var_names[j]
        s = model.var_signs[j]
        colvals = [model.A[i][j] for i in range(model.m)]
        if s == "nonneg":
            var_map[len(names)] = (j, 1)
            names.append(nm); kinds.append("decision"); cols.append(colvals)
        elif s == "nonpos":
            var_map[len(names)] = (j, -1)
            names.append(f"{nm}'"); kinds.append("decision"); cols.append([-v for v in colvals])
            notes.append(f"{nm} ≤ 0: substituída por {nm} = −{nm}', com {nm}' ≥ 0.")
        else:
            var_map[len(names)] = (j, 1)
            names.append(f"{nm}⁺"); kinds.append("decision"); cols.append(colvals)
            var_map[len(names)] = (j, -1)
            names.append(f"{nm}⁻"); kinds.append("decision"); cols.append([-v for v in colvals])
            notes.append(f"{nm} livre: substituída por {nm} = {nm}⁺ − {nm}⁻, com {nm}⁺, {nm}⁻ ≥ 0.")
    return names, kinds, cols, var_map, notes


def build_standard_form(model: LPModel, mode: str = "artificial") -> StandardForm:
    """Converte o modelo para a forma padrão.

    mode = "artificial"    → ≤: +folga; ≥: −excesso +artificial; =: +artificial (b ≥ 0)
    mode = "dual_simplex"  → todas as linhas na forma ≤ com folga (≥ multiplicada por −1,
                              = desdobrada em duas desigualdades); b pode ser negativo
    mode = "algebraic"     → ≤: +folga; ≥: −excesso; =: nada (sem artificiais)
    """
    dnames, dkinds, dcols, var_map, var_notes = _decision_columns(model)
    nd = len(dnames)

    # ---- linhas (coeficientes das variáveis de decisão)
    base_rows, rhs, ops, row_orig, row_sign, notes, labels = [], [], [], [], [], [], []
    for i in range(model.m):
        coeffs = [dcols[c][i] for c in range(nd)]
        op, b = model.ops[i], model.b[i]
        cname = model.con_names[i]
        if mode == "dual_simplex":
            if op == "<=":
                parts = [(coeffs, b, 1, "")]
            elif op == ">=":
                parts = [([-v for v in coeffs], -b, -1, "")]
                notes.append(f"{cname} (≥) multiplicada por −1 para a forma ≤.")
            else:
                parts = [(coeffs, b, 1, "a"), ([-v for v in coeffs], -b, -1, "b")]
                notes.append(f"{cname} (=) desdobrada em duas desigualdades: ≤ e (≥ ×(−1)).")
            for co, bb, sg, suffix in parts:
                base_rows.append(co); rhs.append(bb); ops.append("<=")
                row_orig.append(i); row_sign.append(sg); labels.append(f"{i + 1}{suffix}")
        else:
            sg = 1
            if b < 0 and mode == "artificial":
                coeffs = [-v for v in coeffs]
                b = -b
                op = FLIP_OP[op]
                sg = -1
                notes.append(f"{cname} multiplicada por −1 para tornar o lado direito não negativo "
                             f"(operador passa a {OP_SYMBOL[op]}).")
            base_rows.append(coeffs); rhs.append(b); ops.append(op)
            row_orig.append(i); row_sign.append(sg); labels.append(f"{i + 1}")

    m = len(base_rows)
    # ---- colunas auxiliares
    aux_names, aux_kinds, aux_entries = [], [], []    # entries: (row, value)
    art_names, art_entries = [], []
    identity_local: List[Optional[Tuple[str, int]]] = [None] * m
    for r in range(m):
        op = ops[r]
        lab = labels[r]
        if op == "<=":
            identity_local[r] = ("aux", len(aux_names))
            aux_names.append(f"S{lab}"); aux_kinds.append("slack"); aux_entries.append((r, ONE))
        elif op == ">=":
            aux_names.append(f"E{lab}"); aux_kinds.append("surplus"); aux_entries.append((r, -ONE))
            if mode == "artificial":
                identity_local[r] = ("art", len(art_names))
                art_names.append(f"A{lab}"); art_entries.append((r, ONE))
        else:
            if mode == "artificial":
                identity_local[r] = ("art", len(art_names))
                art_names.append(f"A{lab}"); art_entries.append((r, ONE))

    names = dnames + aux_names + art_names
    kinds = dkinds + aux_kinds + ["artificial"] * len(art_names)
    N = len(names)
    rows = [list(base_rows[r]) + [ZERO] * (N - nd) for r in range(m)]
    for k, (r, v) in enumerate(aux_entries):
        rows[r][nd + k] = v
    for k, (r, v) in enumerate(art_entries):
        rows[r][nd + len(aux_names) + k] = v
    identity_col: List[Optional[int]] = []
    for r in range(m):
        loc = identity_local[r]
        if loc is None:
            identity_col.append(None)
        elif loc[0] == "aux":
            identity_col.append(nd + loc[1])
        else:
            identity_col.append(nd + len(aux_names) + loc[1])
    artificial_cols = list(range(nd + len(aux_names), N))
    return StandardForm(names, kinds, rows, rhs, ops, row_orig, row_sign, identity_col,
                        var_map, artificial_cols, notes, var_notes)


# =============================================================================
# Laço iterativo do Simplex primal
# =============================================================================
def _choose_entering(tab: Tableau, red: List[MValue], cands: List[int], rule: str) -> int:
    # No Grande M, a parte em M domina: se algum candidato melhora a parte M, só eles concorrem.
    with_m = [j for j in cands if red[j].m != 0]
    if with_m:
        cands = with_m
    if rule == "bland":
        return min(cands)
    if tab.sense == "max":
        return max(cands, key=lambda j: (red[j].key(), -j))
    return min(cands, key=lambda j: (red[j].key(), j))


def _ratio_test(tab: Tableau, k: int):
    ratios = []
    best_r, best_theta = None, None
    for i in range(tab.m):
        a = tab.rows[i][k]
        if a > 0:
            theta = tab.rhs[i] / a
            ratios.append({"row": i, "rhs": fmt(tab.rhs[i]), "coef": fmt(a), "ratio": fmt(theta), "valid": True})
            if (best_theta is None or theta < best_theta
                    or (theta == best_theta and tab.basis[i] < tab.basis[best_r])):
                best_r, best_theta = i, theta
        else:
            ratios.append({"row": i, "rhs": fmt(tab.rhs[i]), "coef": fmt(a), "ratio": None, "valid": False,
                           "reason": "coeficiente ≤ 0 (não limita a entrada)"})
    return best_r, best_theta, ratios


def _rc_text(v: MValue) -> str:
    return v.text()


def make_step(tab: Tableau, phase: int, record: bool) -> dict:
    step = {"phase": phase, "degenerate": tab.is_degenerate()}
    if record:
        step["tableau"] = tab.snapshot()
    return step


def run_iterations(
    tab: Tableau,
    steps: List[dict],
    phase: int = 0,
    rule: str = "dantzig",
    max_iter: int = DEFAULT_MAX_ITER,
    record: bool = True,
    intro: Optional[str] = None,
    allowed: Optional[set] = None,
) -> Tuple[str, Optional[int]]:
    """Executa o Simplex primal a partir de uma tabela primal-viável.

    Retorna (status, coluna) onde status ∈ {"optimal", "unbounded", "iteration_limit"} e
    coluna é a variável de entrada sem limite (caso ilimitado).
    """
    visited = {tuple(sorted(tab.basis))}
    iterations = 0
    current_rule = rule
    first = True
    while True:
        red = tab.reduced()
        cands = [
            j for j in tab.visible()
            if j not in tab.basis and (allowed is None or j in allowed) and tab.improving(red[j])
        ]
        step = make_step(tab, phase, record)
        if first and intro:
            step["intro"] = intro
        first = False
        crit = "todos os Cj − Zj ≤ 0" if tab.sense == "max" else "todos os Cj − Zj ≥ 0"
        if not cands:
            step["decision"] = {
                "type": "optimal",
                "explanation": f"Critério de otimalidade satisfeito ({crit}): nenhuma variável não básica "
                               f"melhora a função objetivo.",
            }
            steps.append(step)
            return "optimal", None
        if iterations >= max_iter:
            step["decision"] = {
                "type": "iteration_limit",
                "explanation": f"Limite de {max_iter} iterações atingido antes de comprovar a otimalidade.",
            }
            steps.append(step)
            return "iteration_limit", None

        k = _choose_entering(tab, red, cands, current_rule)
        r, theta, ratios = _ratio_test(tab, k)
        kname = tab.names[k]
        if r is None:
            step["decision"] = {
                "type": "unbounded",
                "entering": kname,
                "entering_col": tab.col_pos(k),
                "ratios": ratios,
                "explanation": f"{kname} melhora a função objetivo (Cj − Zj = {_rc_text(red[k])}), mas nenhum "
                               f"coeficiente da sua coluna é positivo: {kname} pode crescer indefinidamente sem "
                               f"violar restrições. O problema é ilimitado.",
            }
            steps.append(step)
            return "unbounded", k

        leaving = tab.names[tab.basis[r]]
        pivot_val = tab.rows[r][k]
        degenerate = theta == 0
        direction = "maior" if tab.sense == "max" else "menor"
        sign_word = "positivo" if tab.sense == "max" else "negativo"
        if current_rule == "bland":
            why_in = (f"Regra de Bland: {kname} é a variável de menor índice com Cj − Zj {sign_word} "
                      f"({_rc_text(red[k])}).")
        else:
            why_in = (f"Entra {kname}: possui o {direction} Cj − Zj ({_rc_text(red[k])}), ou seja, a maior "
                      f"melhoria de Z por unidade introduzida.")
        why_out = (f"Sai {leaving}: menor razão b/a entre as linhas com coeficiente positivo "
                   f"(θ = {fmt(tab.rhs[r])} ÷ {fmt(pivot_val)} = {fmt(theta)}).")
        z_before = tab.z()
        ops = tab.pivot(r, k)
        iterations += 1
        dec = {
            "type": "pivot",
            "rule": current_rule,
            "entering": kname,
            "entering_col": tab.col_pos(k),
            "entering_reduced": red[k].to_json(),
            "leaving": leaving,
            "leaving_row": r,
            "pivot": fmt(pivot_val),
            "theta": fmt(theta),
            "ratios": ratios,
            "operations": ops,
            "degenerate": degenerate,
            "z_before": z_before.to_json(),
            "z_after": tab.z().to_json(),
            "explanation": why_in + " " + why_out + f" Elemento pivô = {fmt(pivot_val)}.",
        }
        if degenerate:
            dec["explanation"] += " Pivoteamento degenerado (θ = 0): a solução e o valor de Z não mudam."
        key = tuple(sorted(tab.basis))
        if key in visited and current_rule != "bland":
            current_rule = "bland"
            dec["explanation"] += (" Uma base já visitada reapareceu (risco de ciclagem): o algoritmo passa a "
                                   "usar a regra de Bland, que garante término.")
        visited.add(key)
        step["decision"] = dec
        steps.append(step)


# =============================================================================
# Extração de resultados
# =============================================================================
def original_solution(tab: Tableau, sf: StandardForm, n: int) -> List[Fraction]:
    vals = tab.values()
    x = [ZERO] * n
    for col, (j, coef) in sf.var_map.items():
        x[j] += coef * vals[col]
    return x


def constraint_analysis(model: LPModel, x: List[Fraction]) -> List[dict]:
    out = []
    for i in range(model.m):
        lhs = model.lhs_at(i, x)
        b = model.b[i]
        op = model.ops[i]
        if op == "<=":
            gap, gap_type = b - lhs, "folga"
        elif op == ">=":
            gap, gap_type = lhs - b, "excesso"
        else:
            gap, gap_type = lhs - b, "—"
        out.append({
            "name": model.con_names[i],
            "origin": model.con_origin[i],
            "expression": model.constraint_text(i),
            "lhs_expression": linear_text(model.A[i], model.var_names),
            "operator": op,
            "value": num_json(lhs),
            "rhs": num_json(b),
            "gap": num_json(gap),
            "gap_type": gap_type,
            "active": lhs == b,
            "satisfied": model.constraint_ok(i, x),
        })
    return out


def variables_json(model: LPModel, x: List[Fraction]) -> List[dict]:
    return [
        {"name": model.var_names[j], "domain": model.var_domains[j], **num_json(x[j])}
        for j in range(model.n)
    ]


def dual_values(tab: Tableau, sf: StandardForm, model: LPModel) -> List[Optional[Fraction]]:
    """Preços-sombra y = c_B·B⁻¹, lidos nas colunas identidade (folgas/artificiais) da tabela final."""
    cb = [tab.costs[b].c for b in tab.basis]   # apenas a parte constante (custos originais)
    y_std: Dict[int, Optional[Fraction]] = {}
    present = set(tab.row_origin)
    for s in range(sf.m):
        col = sf.identity_col[s]
        if col is None or s not in present:
            y_std[s] = None
            continue
        y_std[s] = sum((cb[i] * tab.rows[i][col] for i in range(tab.m)), ZERO)
    y: List[Optional[Fraction]] = [ZERO] * model.m
    for s in range(sf.m):
        i = sf.row_orig[s]
        if y_std[s] is None:
            y[i] = None
        elif y[i] is not None:
            y[i] += sf.row_sign[s] * y_std[s]
    return y


def reduced_costs_original(tab: Tableau, sf: StandardForm, model: LPModel) -> List[dict]:
    red = tab.reduced()
    out = []
    for col, (j, coef) in sf.var_map.items():
        out.append({"variable": tab.names[col], "original": model.var_names[j], "reduced": red[col].to_json(),
                    "basic": col in tab.basis})
    return out


def detect_alternatives(tab: Tableau, sf: StandardForm, model: LPModel, record: bool = True) -> dict:
    """Verifica soluções ótimas múltiplas a partir da tabela ótima.

    Um custo reduzido nulo para uma variável não básica é apenas um INDÍCIO. A multiplicidade
    só é confirmada quando o pivoteamento nessa coluna é admissível e não degenerado (θ > 0),
    produzindo outra solução básica viável distinta com o mesmo Z, ou quando a coluna não tem
    coeficientes positivos (aresta ilimitada de soluções ótimas).
    """
    red = tab.reduced()
    x0 = original_solution(tab, sf, model.n)
    z0 = model.objective_at(x0)
    zero_cols = [
        j for j in tab.visible()
        if j not in tab.basis and sf.kinds[j] != "artificial" and red[j].is_zero()
    ]
    result = {
        "has_multiple": False,
        "zero_reduced": [tab.names[j] for j in zero_cols],
        "alternatives": [],
        "checks": [],
        "explanation": "",
    }
    if not zero_cols:
        result["explanation"] = ("Todas as variáveis não básicas possuem custo reduzido diferente de zero: "
                                 "a solução ótima é única.")
        return result
    for k in zero_cols:
        name = tab.names[k]
        r, theta, ratios = _ratio_test(tab, k)
        if r is None:
            # direção ilimitada que mantém Z constante
            d = [ZERO] * sf.N
            d[k] = ONE
            for i, bcol in enumerate(tab.basis):
                d[bcol] = -tab.rows[i][k]
            dx = [ZERO] * model.n
            for col, (j, coef) in sf.var_map.items():
                dx[j] += coef * d[col]
            x1 = [a + b for a, b in zip(x0, dx)]
            if dx == [ZERO] * model.n:
                result["checks"].append({"variable": name, "result": "same_point",
                                         "text": f"{name}: Cj − Zj = 0, mas a direção não altera as variáveis de decisão."})
                continue
            result["has_multiple"] = True
            result["alternatives"].append({
                "type": "ray", "variable": name,
                "solution": variables_json(model, x1), "objective": num_json(model.objective_at(x1)),
                "direction": [num_json(v) for v in dx],
            })
            result["checks"].append({"variable": name, "result": "ray",
                                     "text": f"{name}: Cj − Zj = 0 e nenhum coeficiente positivo na coluna, então existe uma "
                                             f"semirreta de soluções ótimas (x + t·d, t ≥ 0)."})
            continue
        if theta == 0:
            result["checks"].append({"variable": name, "result": "degenerate",
                                     "text": f"{name}: Cj − Zj = 0, porém θ = 0 (pivoteamento degenerado): a nova base "
                                             f"representa o mesmo ponto."})
            continue
        alt = tab.copy()
        leaving = alt.names[alt.basis[r]]
        ops = alt.pivot(r, k)
        x1 = original_solution(alt, sf, model.n)
        if x1 == x0:
            result["checks"].append({"variable": name, "result": "same_point",
                                     "text": f"{name}: o pivoteamento muda apenas variáveis auxiliares; mesmo ponto."})
            continue
        result["has_multiple"] = True
        entry = {
            "type": "vertex", "variable": name, "leaving": leaving, "theta": fmt(theta),
            "solution": variables_json(model, x1), "objective": num_json(model.objective_at(x1)),
            "operations": ops,
        }
        if record:
            entry["tableau"] = alt.snapshot()
            entry["pivot_row"] = r
            entry["pivot_col"] = tab.col_pos(k)
        result["alternatives"].append(entry)
        result["checks"].append({"variable": name, "result": "vertex",
                                 "text": f"{name}: Cj − Zj = 0 e pivoteamento admissível (θ = {fmt(theta)} > 0, sai "
                                         f"{leaving}) gera outra solução básica ótima distinta."})
    if result["has_multiple"]:
        result["explanation"] = (
            "O problema possui soluções ótimas múltiplas: na tabela ótima há variável não básica com custo "
            "reduzido nulo (Cj − Zj = 0) cuja introdução na base é admissível. Ela altera a solução sem alterar Z, "
            f"pois cada unidade introduzida varia Z em exatamente 0. Todas as combinações convexas das soluções "
            f"ótimas encontradas também são ótimas, com Z = {fmt(z0)}."
        )
    else:
        result["explanation"] = (
            "Há variáveis não básicas com Cj − Zj = 0, mas nenhum pivoteamento admissível produziu solução distinta "
            "(casos degenerados). Não se confirma multiplicidade por este teste."
        )
    return result


def algebraic_proof(tab: Tableau, sf: StandardForm, model: LPModel, x: List[Fraction]) -> dict:
    """Identificação algébrica da solução ótima a partir da tabela final."""
    red = tab.reduced()
    basic = [{"name": tab.names[b], "value": fmt(tab.rhs[i]), "row": i + 1} for i, b in enumerate(tab.basis)]
    nonbasic = [tab.names[j] for j in tab.visible() if j not in tab.basis]
    cond = "≤ 0" if model.sense == "max" else "≥ 0"
    checks = []
    for j in tab.visible():
        if j in tab.basis:
            continue
        ok = not tab.improving(red[j])
        checks.append({"name": tab.names[j], "reduced": red[j].to_json(), "ok": ok})
    terms = [f"{fmt(model.c[j])}·({fmt(x[j])})" for j in range(model.n)]
    z = model.objective_at(x)
    subst = []
    for i in range(model.m):
        parts = [f"{fmt(model.A[i][j])}·({fmt(x[j])})" for j in range(model.n) if model.A[i][j] != 0]
        lhs = model.lhs_at(i, x)
        subst.append({
            "name": model.con_names[i],
            "text": f"{' + '.join(parts) if parts else '0'} = {fmt(lhs)} {OP_SYMBOL[model.ops[i]]} {fmt(model.b[i])}",
            "ok": model.constraint_ok(i, x),
        })
    return {
        "basic": basic,
        "nonbasic": nonbasic,
        "condition": f"Cj − Zj {cond} para todas as variáveis não básicas",
        "reduced_checks": checks,
        "feasibility": "Todos os valores da coluna b são ≥ 0 (solução básica viável).",
        "rhs_nonnegative": all(v >= 0 for v in tab.rhs),
        "z_expansion": f"Z = {' + '.join(terms)} = {fmt(z)}",
        "substitution": subst,
    }


def assemble_result(
    model: LPModel, sf: Optional[StandardForm], tab: Optional[Tableau], status: str, steps: List[dict],
    method: str, method_label: str, message: str, record: bool = True, extra: Optional[dict] = None,
) -> dict:
    iterations = sum(1 for s in steps if s.get("decision", {}).get("type") in ("pivot", "dual_pivot", "drive_out"))
    res = {
        "method": method,
        "method_label": method_label,
        "status": status,
        "status_label": STATUS_LABEL.get(status, status),
        "message": message,
        "iterations": iterations,
        "steps": steps if record else [],
        "solution": None,
        "objective_value": None,
        "constraints": [],
        "multiple": None,
        "degenerate": any(s.get("degenerate") for s in steps),
        "degenerate_steps": [i for i, s in enumerate(steps) if s.get("degenerate")],
    }
    if status == "optimal" and tab is not None and sf is not None:
        x = original_solution(tab, sf, model.n)
        z = model.objective_at(x)
        tz = tab.z()
        res["solution"] = variables_json(model, x)
        res["objective_value"] = num_json(z)
        res["tableau_objective"] = tz.to_json()
        res["constraints"] = constraint_analysis(model, x)
        res["multiple"] = detect_alternatives(tab, sf, model, record=record)
        y = dual_values(tab, sf, model)
        res["dual_values"] = [
            {"constraint": model.con_names[i], "value": None if v is None else num_json(v)} for i, v in enumerate(y)
        ]
        res["reduced_costs"] = reduced_costs_original(tab, sf, model)
        res["proof"] = algebraic_proof(tab, sf, model, x)
        res["_x"] = x  # uso interno (removido antes da serialização)
    if extra:
        res.update(extra)
    return res


def public(result: dict) -> dict:
    """Remove campos internos (Fractions) antes de enviar ao cliente."""
    return {k: v for k, v in result.items() if not k.startswith("_")}


# =============================================================================
# Fachada
# =============================================================================
METHODS = {
    "simplex": "Simplex Tabular",
    "two_phase": "Método das Duas Fases",
    "big_m": "Método do Grande M",
    "dual_simplex": "Método Simplex Dual",
}


def solve_lp(model: LPModel, method: str = "simplex", rule: str = "dantzig",
             max_iter: int = DEFAULT_MAX_ITER, record: bool = True) -> dict:
    if method in ("simplex", "two_phase"):
        from app.algorithms.two_phase import solve_two_phase
        return solve_two_phase(model, rule=rule, max_iter=max_iter, record=record, label=method)
    if method == "big_m":
        from app.algorithms.big_m import solve_big_m
        return solve_big_m(model, rule=rule, max_iter=max_iter, record=record)
    if method == "dual_simplex":
        from app.algorithms.dual_simplex import solve_dual_simplex
        return solve_dual_simplex(model, max_iter=max_iter, record=record)
    raise ValueError(f"Método desconhecido: {method}")
