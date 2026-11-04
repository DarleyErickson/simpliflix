"""
Método do Grande M.

Cada variável artificial recebe custo −M (MAX) ou +M (MIN), com M arbitrariamente grande.
Aqui M é SIMBÓLICO: cada custo é um par (c, m) que representa c + m·M, e as comparações
são lexicográficas (a parte em M domina). Isso evita escolher um valor numérico de M que
poderia ser "pequeno demais" ou causar erros de arredondamento.

Encerramento:
  • ótimo com alguma artificial básica positiva → problema inviável;
  • coluna de entrada sem coeficientes positivos → ilimitado, desde que nenhuma
    artificial permaneça positiva (caso contrário, inviável).
"""
from __future__ import annotations

from app.algorithms.lp_model import LPModel
from app.algorithms.simplex import (
    DEFAULT_MAX_ITER, assemble_result, build_standard_form, run_iterations,
)
from app.algorithms.two_phase import initial_tableau
from app.utils.numerical_utils import ONE, ZERO, MValue, fmt


def solve_big_m(model: LPModel, rule: str = "dantzig", max_iter: int = DEFAULT_MAX_ITER,
                record: bool = True) -> dict:
    sf = build_standard_form(model, "artificial")
    costs = sf.original_costs(model)
    penalty = MValue(ZERO, -ONE) if model.sense == "max" else MValue(ZERO, ONE)
    for j in sf.artificial_cols:
        costs[j] = penalty
    steps = []
    std = {"bigm": sf.lines(costs, model.sense) if record else None, "uses_artificial": bool(sf.artificial_cols)}
    if sf.artificial_cols:
        sign = "−M" if model.sense == "max" else "+M"
        intro = (f"Tabela inicial do Grande M: cada variável artificial recebe custo {sign} na função objetivo, "
                 f"penalizando-a de modo que o Simplex a expulse da base. As linhas Zj e Cj − Zj são expressas "
                 f"na forma a + b·M.")
    else:
        intro = ("O modelo não exige variáveis artificiais; o Grande M coincide com o Simplex a partir da base "
                 "de folgas.")
    tab = initial_tableau(sf, costs, model.sense)
    status, k = run_iterations(tab, steps, phase=0, rule=rule, max_iter=max_iter, record=record, intro=intro)
    art = set(sf.artificial_cols)
    positive_art = [tab.names[b] for i, b in enumerate(tab.basis) if b in art and tab.rhs[i] > 0]
    extra = {"standard_form": std}
    if status in ("optimal", "unbounded") and positive_art:
        steps[-1]["decision"] = {
            "type": "infeasible",
            "explanation": f"O critério de parada foi atingido com variável(is) artificial(is) positiva(s) na base "
                           f"({', '.join(positive_art)}). Logo, nenhuma solução satisfaz todas as restrições: "
                           f"o problema é inviável.",
        }
        return assemble_result(model, sf, tab, "infeasible", steps, "big_m", "Método do Grande M",
                               "Problema inviável: variável artificial positiva na solução final.", record, extra)
    if status == "optimal":
        msg = "Solução ótima encontrada: nenhuma artificial positiva e critério de otimalidade satisfeito."
    elif status == "unbounded":
        msg = f"O problema é ilimitado: a variável {tab.names[k]} pode aumentar indefinidamente."
        extra["unbounded_variable"] = tab.names[k]
    else:
        msg = "Limite de iterações atingido: a otimalidade não foi comprovada."
    return assemble_result(model, sf, tab, status, steps, "big_m", "Método do Grande M", msg, record, extra)
