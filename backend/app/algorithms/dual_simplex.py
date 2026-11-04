"""
Método Simplex Dual (Lemke).

Aplicável quando a tabela inicial é DUAL-VIÁVEL (critério de otimalidade já satisfeito:
Cj − Zj ≤ 0 em MAX / ≥ 0 em MIN) mas PRIMAL-INVIÁVEL (algum b_i < 0). Caso típico:
minimização com custos não negativos e restrições ≥.

Preparação: todas as restrições são escritas na forma ≤ (≥ é multiplicada por −1 e = é
desdobrada em duas desigualdades) e as folgas formam a base inicial.

Iteração:
  1. Linha pivô (variável que SAI): a de b_i mais negativo (empates → menor índice).
     Se todos os b_i ≥ 0 → solução ótima.
  2. Se a linha não tem coeficiente negativo → o primal é inviável.
  3. Coluna pivô (variável que ENTRA): menor razão |(Cj − Zj) / a_rj| entre a_rj < 0
     (preserva a viabilidade dual); empates → menor índice.
  4. Pivoteamento e repetição.
"""
from __future__ import annotations

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import (
    DEFAULT_MAX_ITER, assemble_result, build_standard_form, make_step,
)
from app.algorithms.simplex_tableau import Tableau
from app.utils.numerical_utils import fmt


def _abs_m(v):
    """|v| para MValue sem parte M (o Simplex Dual não usa M)."""
    return abs(v.c)


def solve_dual_simplex(model: LPModel, max_iter: int = DEFAULT_MAX_ITER, record: bool = True) -> dict:
    sf = build_standard_form(model, "dual_simplex")
    costs = sf.original_costs(model)
    basis = list(sf.identity_col)
    tab = Tableau(list(sf.names), list(sf.kinds), [list(r) for r in sf.rows], list(sf.rhs), basis,
                  costs, model.sense)
    steps = []
    std = {"dual_simplex": sf.lines(costs, model.sense) if record else None}
    label = "Método Simplex Dual"

    red = tab.reduced()
    bad = [tab.names[j] for j in range(tab.N) if j not in tab.basis and tab.improving(red[j])]
    if bad:
        step = make_step(tab, 0, record)
        crit = "Cj − Zj ≤ 0" if model.sense == "max" else "Cj − Zj ≥ 0"
        step["decision"] = {
            "type": "not_applicable",
            "explanation": f"A tabela inicial não é dual-viável: as variáveis {', '.join(bad)} violam o critério "
                           f"{crit}. O Simplex Dual exige que a tabela inicial já satisfaça a condição de otimalidade. "
                           f"Utilize o Simplex Tabular (Duas Fases) ou o Grande M para este modelo.",
        }
        steps.append(step)
        return assemble_result(model, sf, tab, "not_applicable", steps, "dual_simplex", label,
                               "O Simplex Dual não se aplica: a tabela inicial não é dual-viável "
                               f"({', '.join(bad)} com custo reduzido favorável).", record,
                               {"standard_form": std})

    iterations = 0
    first = True
    while True:
        step = make_step(tab, 0, record)
        if first:
            step["intro"] = ("Tabela inicial do Simplex Dual: base de folgas, com todas as restrições na forma ≤. "
                             "A tabela já satisfaz o critério de otimalidade (dual-viável); o objetivo agora é "
                             "eliminar os valores negativos da coluna b.")
            first = False
        neg = [i for i in range(tab.m) if tab.rhs[i] < 0]
        if not neg:
            step["decision"] = {
                "type": "optimal",
                "explanation": "Todos os valores de b são não negativos (viabilidade primal) e a tabela continua "
                               "dual-viável: a solução é ótima.",
            }
            steps.append(step)
            status = "optimal"
            break
        if iterations >= max_iter:
            step["decision"] = {"type": "iteration_limit",
                                "explanation": f"Limite de {max_iter} iterações atingido."}
            steps.append(step)
            status = "iteration_limit"
            break
        r = min(neg, key=lambda i: (tab.rhs[i], i))
        leaving = tab.names[tab.basis[r]]
        red = tab.reduced()
        ratios = []
        best_k, best = None, None
        for j in tab.visible():
            a = tab.rows[r][j]
            if j in tab.basis:
                continue
            if a < 0:
                q = _abs_m(red[j]) / (-a)
                ratios.append({"col": tab.col_pos(j), "name": tab.names[j], "reduced": red[j].to_json(),
                               "coef": fmt(a), "ratio": fmt(q), "valid": True})
                if best is None or q < best:
                    best, best_k = q, j
            else:
                ratios.append({"col": tab.col_pos(j), "name": tab.names[j], "reduced": red[j].to_json(),
                               "coef": fmt(a), "ratio": None, "valid": False})
        if best_k is None:
            step["decision"] = {
                "type": "infeasible", "leaving": leaving, "leaving_row": r, "col_ratios": ratios,
                "explanation": f"A linha L{r + 1} ({leaving} = {fmt(tab.rhs[r])} < 0) não possui coeficiente negativo: "
                               f"não há como torná-la viável. O problema primal é inviável.",
            }
            steps.append(step)
            status = "infeasible"
            break
        k = best_k
        piv = tab.rows[r][k]
        z_before = tab.z()
        ops = tab.pivot(r, k)
        iterations += 1
        step["decision"] = {
            "type": "dual_pivot",
            "entering": tab.names[k], "entering_col": tab.col_pos(k),
            "leaving": leaving, "leaving_row": r,
            "pivot": fmt(piv), "col_ratios": ratios, "operations": ops, "ratios": [],
            "z_before": z_before.to_json(), "z_after": tab.z().to_json(),
            "degenerate": best == 0,
            "explanation": (
                f"Sai {leaving}: é a variável básica mais negativa (linha L{r + 1}). Entra {tab.names[k]}: menor "
                f"razão |Cj − Zj| ÷ |a_rj| entre os coeficientes negativos da linha ({fmt(best)}), o que preserva "
                f"a viabilidade dual. Elemento pivô = {fmt(piv)}."
            ),
        }
        steps.append(step)

    if status == "optimal":
        msg = "Solução ótima encontrada pelo Simplex Dual."
    elif status == "infeasible":
        msg = "O problema é inviável (detectado pelo Simplex Dual)."
    else:
        msg = "Limite de iterações atingido: a otimalidade não foi comprovada."
    return assemble_result(model, sf, tab, status, steps, "dual_simplex", label, msg, record,
                           {"standard_form": std})
