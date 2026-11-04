"""Rotas do problema dual (formulação e resolução tabular)."""
from fastapi import APIRouter

from app.algorithms.dual_model import dual_formulation, solve_dual
from app.algorithms.simplex import solve_lp
from app.routes.common import load, ok
from app.schemas import ProblemIn

router = APIRouter(prefix="/api", tags=["dual"])


@router.post("/model/dual")
def formulate(problem: ProblemIn):
    """Apenas converte o primal em dual (botão "Converter em Dual")."""
    model, *_ = load(problem)
    form = dual_formulation(model)
    form.pop("_dual", None)
    return ok(form)


@router.post("/solve/dual")
def dual(problem: ProblemIn):
    model, opts, rule, max_iter, _ = load(problem)
    primal = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False)
    return ok(solve_dual(model, primal, rule=rule, max_iter=max_iter))
