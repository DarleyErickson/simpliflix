@echo off
REM SimpliFlix - inicia a API e o front-end em http://localhost:8000
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  python -m venv .venv || goto :erro
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :erro
)
start "" "http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000
goto :eof
:erro
echo Falha ao preparar o ambiente. Verifique se o Python 3.12+ esta instalado.
pause
