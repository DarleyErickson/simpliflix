"""
Método das Duas Fases.

Fase 1: minimizar W = Σ artificiais, partindo da base formada por folgas e artificiais.
        • W* > 0  → não existe solução viável (problema inviável);
        • W* = 0  → as artificiais ainda básicas (em nível zero) são retiradas da base por
                    pivoteamentos degenerados; se a linha não tiver coeficiente não nulo fora
                    das artificiais, ela é redundante e é removida.
Fase 2: as colunas artificiais são descartadas da exibição, Cj recebe os coeficientes
        originais e o Simplex continua a partir da base viável obtida.

Quando o modelo não exige artificiais (todas as restrições ≤ com b ≥ 0), executa-se
diretamente o Simplex em uma única fase, a partir da base de folgas.
"""
from __future__ import annotations

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import (
    DEFAULT_MAX_ITER, METHODS, StandardForm, assemble_result, build_standard_form, make_step, run_iterations,
)
from app.algorithms.simplex_tableau import Tableau
from app.utils.numerical_utils import ONE, MValue, fmt


def initial_tableau(sf: StandardForm, costs, sense: str) -> Tableau:
    basis = []
    for r in range(sf.m):
        col = sf.identity_col[r]
        if col is None:
            raise ValueError("Linha sem coluna identidade")
        basis.append(col)
    return Tableau(list(sf.names), list(sf.kinds), [list(r) for r in sf.rows], list(sf.rhs), basis,
                   list(costs), sense)


def solve_two_phase(model: LPModel, rule: str = "dantzig", max_iter: int = DEFAULT_MAX_ITER,
                    record: bool = True, label: str = "two_phase") -> dict:
    sf = build_standard_form(model, "artificial")
    orig_costs = sf.original_costs(model)
    steps = []
    has_art = bool(sf.artificial_cols)
    method_label = METHODS[label]
    std = {
        "phase1": None,
        "phase2": sf.lines(orig_costs, model.sense) if record else None,
        "uses_phase1": has_art,
    }

    if has_art:
        p1_costs = [MValue(ONE) if k == "artificial" else MValue() for k in sf.kinds]
        if record:
            std["phase1"] = sf.lines(p1_costs, "min", "W")
        tab = initial_tableau(sf, p1_costs, "min")
        intro = ("Fase 1: as restrições ≥ e = exigem variáveis artificiais. Minimiza-se W = soma das artificiais; "
                 "se W chegar a 0, obtém-se uma solução básica viável para o problema original.")
        status, _ = run_iterations(tab, steps, phase=1, rule=rule, max_iter=max_iter, record=record, intro=intro)
        if status == "iteration_limit":
            return assemble_result(model, sf, tab, status, steps, label, method_label,
                                   "A Fase 1 atingiu o limite de iterações; não foi possível concluir.",
                                   record, {"standard_form": std})
        w = tab.z().c
        if w > 0:
            steps[-1]["decision"] = {
                "type": "infeasible",
                "explanation": f"Fim da Fase 1 com W* = {fmt(w)} > 0: ao menos uma variável artificial permanece "
                               f"positiva. Não existe solução que satisfaça todas as restrições — o problema é inviável.",
            }
            return assemble_result(model, sf, tab, "infeasible", steps, label, method_label,
                                   f"O problema é inviável: a Fase 1 terminou com W* = {fmt(w)} > 0.",
                                   record, {"standard_form": std})
        steps[-1]["decision"]["explanation"] += (" W* = 0: todas as artificiais estão em nível zero, logo existe "
                                                 "solução viável.")
        # ---- retirar artificiais remanescentes da base
        art = set(sf.artificial_cols)
        r = 0
        while r < tab.m:
            bcol = tab.basis[r]
            if bcol in art:
                step = make_step(tab, 1, record)
                cand = [j for j in range(tab.N) if j not in art and tab.rows[r][j] != 0]
                if cand:
                    k = cand[0]
                    piv = tab.rows[r][k]
                    leaving = tab.names[bcol]
                    ops = tab.pivot(r, k)
                    step["decision"] = {
                        "type": "drive_out", "entering": tab.names[k], "entering_col": tab.col_pos(k),
                        "leaving": leaving, "leaving_row": r, "pivot": fmt(piv), "operations": ops, "ratios": [],
                        "degenerate": True,
                        "explanation": f"{leaving} é artificial e continua básica com valor 0. Pivoteia-se em "
                                       f"{tab.names[k]} (coeficiente {fmt(piv)} ≠ 0) para retirá-la da base sem "
                                       f"alterar a solução.",
                    }
                    steps.append(step)
                    r += 1
                else:
                    name = tab.names[bcol]
                    step["decision"] = {
                        "type": "remove_row", "leaving": name, "leaving_row": r,
                        "explanation": f"A linha L{r + 1} (básica {name} = 0) tem coeficientes nulos em todas as "
                                       f"variáveis não artificiais: a restrição correspondente é redundante e é "
                                       f"removida.",
                    }
                    steps.append(step)
                    tab.delete_row(r)
            else:
                r += 1
        # ---- preparar Fase 2
        tab.hidden = set(art)
        tab.costs = list(orig_costs)
        tab.sense = model.sense
        intro2 = ("Fase 2: colunas artificiais removidas, Cj substituído pelos coeficientes originais da função "
                  "objetivo e linhas Zj e Cj − Zj recalculadas a partir da base viável obtida na Fase 1.")
        phase = 2
    else:
        tab = initial_tableau(sf, orig_costs, model.sense)
        intro2 = ("Tabela inicial: todas as restrições são do tipo ≤ com lado direito não negativo, portanto as "
                  "variáveis de folga formam uma base viável inicial (origem).")
        phase = 0

    status, k = run_iterations(tab, steps, phase=phase, rule=rule, max_iter=max_iter, record=record,
                               intro=intro2, allowed=set(tab.visible()))
    if status == "optimal":
        msg = "Solução ótima encontrada e comprovada pelo critério de otimalidade."
    elif status == "unbounded":
        msg = (f"O problema é ilimitado: a variável {tab.names[k]} pode aumentar indefinidamente, melhorando Z "
               f"sem limite.")
    else:
        msg = "Limite de iterações atingido: a otimalidade não foi comprovada."
    extra = {"standard_form": std}
    if status == "unbounded":
        extra["unbounded_variable"] = tab.names[k]
    return assemble_result(model, sf, tab, status, steps, label, method_label, msg, record, extra)
