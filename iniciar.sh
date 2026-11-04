#!/usr/bin/env sh
# SimpliFlix - inicia a API e o front-end em http://localhost:8000
cd "$(dirname "$0")/backend" || exit 1
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
.venv/bin/python -m uvicorn app.main:app --port 8000
