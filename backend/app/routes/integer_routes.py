"""Rotas de solução inteira (Branch and Bound) e arredondamento."""
from fastapi import APIRouter

from app.algorithms.graphical_method import solve_graphical
from app.algorithms.integer_solver import integer_mask, solve_integer, solve_rounding
from app.algorithms.simplex import solve_lp
from app.routes.common import load, ok
from app.schemas import ProblemIn

router = APIRouter(prefix="/api/solve", tags=["inteira"])


@router.post("/integer")
def integer(problem: ProblemIn):
    model, opts, rule, max_iter, max_nodes = load(problem)
    lp = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False)
    graph = solve_graphical(model, lp) if model.n == 2 else None
    res = solve_integer(model, max_nodes=max_nodes, rule=rule, x_cont=lp.get("_x"), graph=graph)
    return ok({k: v for k, v in res.items() if not k.startswith("_")})


@router.post("/rounding")
def rounding(problem: ProblemIn):
    model, opts, rule, max_iter, _ = load(problem)
    lp = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False)
    mask, assumed = integer_mask(model)
    res = solve_rounding(model, lp.get("_x"), mask)
    res["assumed_all_integer"] = assumed
    return ok(res)
