"""Rota do método gráfico."""
from fastapi import APIRouter

from app.algorithms.graphical_method import solve_graphical
from app.algorithms.simplex import solve_lp
from app.routes.common import load, ok
from app.schemas import ProblemIn

router = APIRouter(prefix="/api/solve", tags=["gráfico"])


@router.post("/graph")
def graph(problem: ProblemIn):
    model, opts, rule, max_iter, _ = load(problem)
    lp = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False) if model.n == 2 else None
    return ok(solve_graphical(model, lp))
