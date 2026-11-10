"""
SimpliFlix — API REST (FastAPI).

Executar (a partir da pasta backend):
    uvicorn app.main:app --reload --port 8000

A API também serve o front-end estático em http://localhost:8000/ por conveniência; o
front-end continua independente e pode ser servido por qualquer servidor HTTP.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routes import dual_routes, graph_routes, integer_routes, model_routes, simplex_routes
from app.services.validation_service import ModelValidationError

log = logging.getLogger("simpliflix")
VERSION = "1.0.0"

app = FastAPI(
    title="SimpliFlix API",
    description="Resolução e visualização de Programação Linear pelo Método Simplex (UNIMONTES, Pesquisa Operacional).",
    version=VERSION,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _error(status: int, code: str, message: str, details=None):
    return JSONResponse(status_code=status, content={
        "ok": False, "error": {"code": code, "message": message, "details": details or []}})


@app.exception_handler(ModelValidationError)
async def model_error(_: Request, exc: ModelValidationError):
    n = len(exc.errors)
    return _error(422, "invalid_model",
                  f"O modelo possui {n} problema{'s' if n > 1 else ''} a corrigir.", exc.errors)


@app.exception_handler(RequestValidationError)
async def request_error(_: Request, exc: RequestValidationError):
    details = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", []) if p != "body")
        details.append({"field": loc, "message": f"Campo '{loc or 'corpo'}' ausente ou com formato inválido."})
    return _error(422, "invalid_request", "A requisição não segue o formato esperado do modelo.", details)


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    log.exception("Erro inesperado: %s", exc)
    return _error(500, "internal_error",
                  "Ocorreu um erro inesperado ao processar o modelo. Verifique os dados informados e tente "
                  "novamente.")


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    """O front-end servido aqui é sempre revalidado (evita CSS/JS desatualizados após alterações)."""
    response = await call_next(request)
    path = request.url.path
    if not path.startswith("/api") and "/vendor/" not in path:
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"ok": True, "data": {"status": "online", "service": "SimpliFlix API", "version": VERSION}}


for r in (model_routes, simplex_routes, graph_routes, integer_routes, dual_routes):
    app.include_router(r.router)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
