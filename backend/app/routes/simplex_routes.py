"""Rotas do Simplex tabular (Duas Fases, Grande M, Simplex Dual), método algébrico e resolução completa."""
from fastapi import APIRouter

from app.algorithms.algebraic_method import solve_algebraic
from app.algorithms.simplex import METHODS, public, solve_lp
from app.routes.common import load, ok
from app.schemas import ProblemIn
from app.services.model_service import list_methods, model_summary
from app.services.solver_service import solve_all

router = APIRouter(prefix="/api/solve", tags=["simplex"])


@router.post("/simplex")
def simplex(problem: ProblemIn):
    """Resolve pelo Simplex tabular. options.methods pode conter two_phase, big_m ou dual_simplex."""
    model, opts, rule, max_iter, _ = load(problem)
    method = next((m for m in opts.methods if m in METHODS), "simplex")
    res = solve_lp(model, method, rule=rule, max_iter=max_iter, record=True)
    return ok({"model": model_summary(model), "result": public(res)})


@router.post("/algebraic")
def algebraic(problem: ProblemIn):
    model, *_ = load(problem)
    return ok({"model": model_summary(model), "result": solve_algebraic(model)})


@router.post("/all")
def solve_everything(problem: ProblemIn):
    """Executa todos os métodos selecionados e devolve uma resposta consolidada para a tela de resultados."""
    model, opts, rule, max_iter, max_nodes = load(problem)
    methods = list_methods(opts.methods)
    data = solve_all(model, methods, rule, max_iter, max_nodes, opts.include_integer, opts.include_dual)
    return ok(data)
