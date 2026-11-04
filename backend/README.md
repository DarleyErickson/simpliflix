# SimpliFlix — Back-end (API)

API REST em FastAPI com o Simplex tabular implementado pela equipe (aritmética racional exata).

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

```bash
.venv\Scripts\python -m pytest -q
```

- Swagger: <http://localhost:8000/docs>
- Front-end servido em <http://localhost:8000/>

Módulos principais: `app/algorithms/` (Simplex, Duas Fases, Grande M, Simplex Dual, gráfico, algébrico, Branch and Bound, dual), `app/services/` (validação, conversão do modelo, orquestração), `app/routes/` (rotas HTTP).

Veja o [README principal](../README.md) e a [documentação matemática](../docs/documentacao.md).
