"""Rotas do método gráfico: dados para o gráfico interativo e figura estática (Matplotlib)."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from app.algorithms.graphical_method import solve_graphical
from app.algorithms.integer_solver import solve_integer
from app.algorithms.simplex import solve_lp
from app.routes.common import load, ok
from app.schemas import ProblemIn
from app.services.figure_service import FORMATS, FigureUnavailable, render_figure
from app.services.validation_service import ModelValidationError
from app.services.visualization_service import overlay_solutions

router = APIRouter(prefix="/api/solve", tags=["gráfico"])


@router.post("/graph")
def graph(problem: ProblemIn):
    model, opts, rule, max_iter, _ = load(problem)
    lp = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False) if model.n == 2 else None
    return ok(solve_graphical(model, lp))


@router.post("/graph/figure")
def graph_figure(problem: ProblemIn, fmt: str = Query("png", pattern="^(png|svg|pdf)$")):
    """Figura do método gráfico para relatório e slides: PNG (300 dpi), SVG ou PDF."""
    model, opts, rule, max_iter, max_nodes = load(problem)
    if model.n != 2:
        raise ModelValidationError([{"field": "objective.coefficients",
                                     "message": "A figura do método gráfico exige exatamente 2 variáveis de decisão."}])
    lp = solve_lp(model, "two_phase", rule=rule, max_iter=max_iter, record=False)
    g = solve_graphical(model, lp)
    integer = (solve_integer(model, max_nodes=max_nodes, rule=rule, x_cont=lp.get("_x"), graph=g)
               if opts.include_integer else None)
    g = overlay_solutions(g, lp, integer)
    try:
        data = render_figure(g, fmt, title=model.name or "")
    except FigureUnavailable:
        return JSONResponse(status_code=503, content={"ok": False, "error": {
            "code": "figure_unavailable", "details": [],
            "message": "A exportação de figuras precisa do Matplotlib, que não está instalado. "
                       "Rode o iniciar.bat com internet (ou pip install -r requirements.txt) e tente de novo."}})
    return Response(content=data, media_type=FORMATS[fmt],
                    headers={"Content-Disposition": f'attachment; filename="simpliflix-grafico.{fmt}"'})
