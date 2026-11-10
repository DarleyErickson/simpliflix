"""Testes de integração da API REST."""
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

WYNDOR = {
    "objective": {"type": "max", "coefficients": [3, 5]},
    "variables": [{"name": "X1", "domain": "continuous", "lower_bound": 0},
                  {"name": "X2", "domain": "continuous", "lower_bound": 0}],
    "constraints": [
        {"coefficients": [1, 0], "operator": "<=", "rhs": 4},
        {"coefficients": [0, 2], "operator": "<=", "rhs": 12},
        {"coefficients": [3, 2], "operator": "<=", "rhs": 18},
    ],
}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_validate_and_routes():
    assert client.post("/api/model/validate", json=WYNDOR).json()["data"]["valid"] is True
    for route in ("/api/solve/simplex", "/api/solve/graph", "/api/solve/integer", "/api/solve/rounding",
                  "/api/solve/dual", "/api/model/dual", "/api/solve/algebraic"):
        r = client.post(route, json=WYNDOR)
        assert r.status_code == 200, route
        assert r.json()["ok"] is True


def test_solve_all_consistente():
    body = dict(WYNDOR, options={"methods": ["graphical", "algebraic", "simplex", "big_m", "dual_simplex"]})
    d = client.post("/api/solve/all", json=body).json()["data"]
    assert d["summary"]["objective_value"]["exact"] == "36"
    assert d["analysis"]["all_ok"] is True
    assert d["tabular"]["dual_simplex"]["status"] == "not_applicable"


def test_limites_viram_restricoes():
    body = {
        "objective": {"type": "max", "coefficients": [1, 1]},
        "variables": [{"name": "X1", "sign": "nonneg", "upper_bound": 3}, {"name": "X2", "lower_bound": 1, "upper_bound": 2}],
        "constraints": [{"coefficients": [1, 1], "operator": "<=", "rhs": 10}],
    }
    d = client.post("/api/solve/simplex", json=body).json()["data"]
    assert d["model"]["n_constraints"] == 4
    assert d["result"]["objective_value"]["exact"] == "5"


def test_validacao_em_portugues():
    bad = {"objective": {"type": "max", "coefficients": [1, "abc"]},
           "constraints": [{"coefficients": [1], "operator": "<", "rhs": ""}]}
    r = client.post("/api/solve/all", json=bad)
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False and len(body["error"]["details"]) == 4
    assert "não é um número válido" in body["error"]["details"][0]["message"]


def test_funcao_objetivo_zerada_e_sem_restricoes():
    r = client.post("/api/solve/all", json={"objective": {"type": "min", "coefficients": [0, 0]}, "constraints": []})
    assert r.status_code == 422
    msgs = " ".join(e["message"] for e in r.json()["error"]["details"])
    assert "zero" in msgs and "restrição" in msgs


def test_requisicao_malformada():
    r = client.post("/api/solve/all", json={"foo": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_figura_matplotlib():
    assinatura = {"png": b"\x89PNG", "pdf": b"%PDF", "svg": b"<?xml"}
    for fmt, magic in assinatura.items():
        r = client.post(f"/api/solve/graph/figure?fmt={fmt}", json=WYNDOR)
        assert r.status_code == 200, fmt
        assert r.content.startswith(magic), fmt
        assert len(r.content) > 5000, fmt
    # casos especiais também precisam desenhar: inviável e ilimitado
    inviavel = {"objective": {"type": "max", "coefficients": [1, 1]},
                "constraints": [{"coefficients": [1, 1], "operator": "<=", "rhs": 2},
                                {"coefficients": [1, 1], "operator": ">=", "rhs": 5}]}
    ilimitado = {"objective": {"type": "max", "coefficients": [1, 1]},
                 "constraints": [{"coefficients": [1, -1], "operator": "<=", "rhs": 2}]}
    multiplo = {"objective": {"type": "max", "coefficients": [3, 2]},
                "constraints": [{"coefficients": [3, 2], "operator": "<=", "rhs": 18},
                                {"coefficients": [1, 0], "operator": "<=", "rhs": 4}]}
    for body in (inviavel, ilimitado, multiplo):
        assert client.post("/api/solve/graph/figure", json=body).status_code == 200
    # formato inválido e modelo com 3 variáveis são recusados com mensagem
    assert client.post("/api/solve/graph/figure?fmt=gif", json=WYNDOR).status_code == 422
    tres = {"objective": {"type": "max", "coefficients": [1, 1, 1]},
            "constraints": [{"coefficients": [1, 1, 1], "operator": "<=", "rhs": 5}]}
    r = client.post("/api/solve/graph/figure", json=tres)
    assert r.status_code == 422 and r.json()["ok"] is False
