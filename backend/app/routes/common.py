"""Utilidades compartilhadas pelas rotas: padrão de resposta JSON e conversão do modelo."""
from __future__ import annotations

from app.schemas import ProblemIn
from app.services.model_service import options_of, parse_problem


def ok(data: dict) -> dict:
    """Resposta de sucesso padronizada: {"ok": true, "data": ...}."""
    return {"ok": True, "data": data}


def load(problem: ProblemIn):
    """Valida e converte a requisição; ModelValidationError é tratada no main (HTTP 422)."""
    model = parse_problem(problem)
    opts, rule, max_iter, max_nodes = options_of(problem)
    return model, opts, rule, max_iter, max_nodes
