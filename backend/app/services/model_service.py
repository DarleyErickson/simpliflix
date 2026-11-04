"""
Conversão do JSON recebido (ProblemIn) para o modelo interno exato (LPModel).

Regras para as variáveis:
  * ``sign`` explícito ("nonneg" | "nonpos" | "free") define a condição de sinal;
  * sem ``sign``: lower_bound = 0 (padrão) → X ≥ 0; lower_bound = null e upper_bound = 0 → X ≤ 0;
    ambos nulos → livre;
  * limites diferentes de zero (ex.: X1 ≥ 2, X2 ≤ 10) viram restrições explícitas do modelo,
    identificadas como "limite".
"""
from __future__ import annotations

from fractions import Fraction
from typing import List

from app.algorithms.lp_model import LPModel
from app.schemas import ProblemIn
from app.services.validation_service import (
    MAX_CONSTRAINTS, MAX_VARIABLES, VALID_SIGNS, Collector, normalize_op,
)

ZERO = Fraction(0)


def parse_problem(p: ProblemIn) -> LPModel:
    col = Collector()

    # ---------------- função objetivo
    sense = str(p.objective.type or "").strip().lower()
    if sense in ("maximizar", "maximize", "maximização"):
        sense = "max"
    if sense in ("minimizar", "minimize", "minimização"):
        sense = "min"
    if sense not in ("max", "min"):
        col.add("objective.type", "Tipo de problema inválido: escolha maximização (max) ou minimização (min).")
    coeffs = p.objective.coefficients or []
    n = len(coeffs)
    if n == 0:
        col.add("objective.coefficients", "A função objetivo não possui coeficientes. Defina ao menos uma variável.")
    if n > MAX_VARIABLES:
        col.add("objective.coefficients", f"Número de variáveis ({n}) acima do limite de {MAX_VARIABLES}.")
    c = [col.number(v, f"objective.coefficients.{j}", f"Coeficiente de X{j + 1} na função objetivo")
         for j, v in enumerate(coeffs)]
    if n and all(v is not None for v in c) and all(v == 0 for v in c):
        col.add("objective.coefficients", "Todos os coeficientes da função objetivo são zero. Informe ao menos um "
                                          "coeficiente diferente de zero.")

    # ---------------- variáveis
    vars_in = p.variables or []
    if vars_in and len(vars_in) != n:
        col.add("variables", f"Quantidade inconsistente: {len(vars_in)} variáveis definidas, mas a função objetivo "
                             f"possui {n} coeficientes.")
    names, domains, signs = [], [], []
    bound_rows = []
    seen = set()
    for j in range(n):
        v = vars_in[j] if j < len(vars_in) else None
        name = (v.name.strip() if v and v.name and v.name.strip() else f"X{j + 1}")
        if name in seen:
            col.add(f"variables.{j}.name", f"Nome de variável repetido: {name}.")
        seen.add(name)
        names.append(name)
        dom = (v.domain if v else "continuous") or "continuous"
        dom = str(dom).lower()
        if dom in ("inteira", "int"):
            dom = "integer"
        if dom in ("contínua", "continua", "real"):
            dom = "continuous"
        if dom not in ("continuous", "integer"):
            col.add(f"variables.{j}.domain", f"Domínio inválido para {name}: use contínua ou inteira.")
            dom = "continuous"
        domains.append(dom)

        fields = v.model_fields_set if v else set()
        # limite inferior: padrão 0 quando o campo não é enviado; null explícito = sem limite
        if v is None or "lower_bound" not in fields:
            lb = ZERO
        elif v.lower_bound is None:
            lb = None
        else:
            lb = col.number(v.lower_bound, f"variables.{j}.lower_bound", f"Limite inferior de {name}", False)
        ub = (col.number(v.upper_bound, f"variables.{j}.upper_bound", f"Limite superior de {name}", False)
              if v is not None and v.upper_bound is not None else None)
        sign = v.sign if v else None
        if sign is not None:
            sign = str(sign).strip().lower()
            if sign not in VALID_SIGNS:
                col.add(f"variables.{j}.sign", f"Condição de sinal inválida para {name}: use ≥ 0, ≤ 0 ou livre.")
                sign = "nonneg"
            if "lower_bound" not in fields:
                lb = None   # com sinal explícito, o limite inferior só existe se for enviado
        else:
            if lb is not None:
                sign = "nonneg" if lb >= 0 else "free"
            elif ub is not None and ub <= 0:
                sign = "nonpos"
            else:
                sign = "free"
        implied_lb = ZERO if sign == "nonneg" else None
        implied_ub = ZERO if sign == "nonpos" else None
        if lb is not None and ub is not None and lb > ub:
            col.add(f"variables.{j}", f"Limites incoerentes para {name}: limite inferior maior que o superior.")
        signs.append(sign)
        # limites que acrescentam informação além do sinal viram restrições explícitas
        if lb is not None and (implied_lb is None or lb > implied_lb):
            bound_rows.append((j, ">=", lb))
        if ub is not None and (implied_ub is None or ub < implied_ub):
            bound_rows.append((j, "<=", ub))

    # ---------------- restrições
    cons = p.constraints or []
    if len(cons) == 0:
        col.add("constraints", "O modelo não possui restrições. Adicione ao menos uma restrição.")
    if len(cons) + len(bound_rows) > MAX_CONSTRAINTS:
        col.add("constraints", f"Número de restrições acima do limite de {MAX_CONSTRAINTS}.")
    A, ops, b, cnames = [], [], [], []
    for i, cin in enumerate(cons):
        label = f"Restrição {i + 1}"
        if len(cin.coefficients) != n:
            col.add(f"constraints.{i}.coefficients",
                    f"{label}: possui {len(cin.coefficients)} coeficiente(s), mas o modelo tem {n} variável(is).")
            row = [None] * n
        else:
            row = [col.number(v, f"constraints.{i}.coefficients.{j}", f"{label}, coeficiente de {names[j]}")
                   for j, v in enumerate(cin.coefficients)]
        op = normalize_op(cin.operator)
        if op is None:
            col.add(f"constraints.{i}.operator", f"{label}: operador ausente ou inválido. Escolha ≤, ≥ ou =.")
        rhs = col.number(cin.rhs, f"constraints.{i}.rhs", f"{label}, lado direito")
        if all(v is not None for v in row) and row and all(v == 0 for v in row):
            col.add(f"constraints.{i}.coefficients",
                    f"{label}: todos os coeficientes são zero. Informe ao menos um coeficiente ou remova a restrição.")
        A.append(row); ops.append(op); b.append(rhs)
        cnames.append((cin.name or "").strip() or f"R{i + 1}")

    col.raise_if_any()

    origin = ["user"] * len(A)
    for (j, op, val) in bound_rows:
        row = [ZERO] * n
        row[j] = Fraction(1)
        A.append(row); ops.append(op); b.append(val)
        cnames.append(f"Lim. {names[j]}")
        origin.append("bound")

    return LPModel(sense=sense, c=c, A=A, ops=ops, b=b, var_names=names, var_domains=domains,
                   var_signs=signs, con_names=cnames, con_origin=origin, name=(p.name or "Problema").strip()[:80])


def model_summary(model: LPModel) -> dict:
    return {
        "name": model.name,
        "sense": model.sense,
        "sense_label": "Maximização" if model.sense == "max" else "Minimização",
        "n_variables": model.n,
        "n_constraints": model.m,
        "formulation": model.formulation(),
        "variables": [{"name": n, "domain": d, "sign": s}
                      for n, d, s in zip(model.var_names, model.var_domains, model.var_signs)],
        "integer_variables": [n for n, d in zip(model.var_names, model.var_domains) if d == "integer"],
    }


def options_of(p: ProblemIn):
    from app.schemas import OptionsIn
    o = p.options or OptionsIn()
    rule = o.pivot_rule if o.pivot_rule in ("dantzig", "bland") else "dantzig"
    max_iter = max(1, min(int(o.max_iterations or 200), 1000))
    max_nodes = max(1, min(int(o.max_nodes or 500), 5000))
    return o, rule, max_iter, max_nodes


def list_methods(methods: List[str]) -> List[str]:
    valid = ["graphical", "algebraic", "simplex", "two_phase", "big_m", "dual_simplex"]
    out = [m for m in valid if m in (methods or [])]
    return out
