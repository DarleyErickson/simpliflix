"""Rotas de modelagem: validação, forma padrão e formulação."""
from fastapi import APIRouter

from app.algorithms.simplex import build_standard_form
from app.routes.common import load, ok
from app.schemas import ProblemIn
from app.services.model_service import model_summary

router = APIRouter(prefix="/api/model", tags=["modelo"])


@router.post("/validate")
def validate(problem: ProblemIn):
    """Valida o modelo e devolve a formulação matemática e a forma padrão."""
    model, *_ = load(problem)
    sf = build_standard_form(model, "artificial")
    costs = sf.original_costs(model)
    return ok({
        "valid": True,
        "model": model_summary(model),
        "standard_form": sf.lines(costs, model.sense),
        "needs_artificial": bool(sf.artificial_cols),
        "graphical_available": model.n == 2,
    })
