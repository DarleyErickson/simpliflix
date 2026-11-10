@echo off
setlocal
chcp 65001 >nul
title SimpliFlix
REM =====================================================================
REM  SimpliFlix - inicia a API e o front-end (basta dar dois cliques)
REM  1a execucao: cria o ambiente virtual e instala as dependencias
REM  (precisa de internet). Depois disso funciona totalmente offline.
REM =====================================================================
if "%PORT%"=="" set PORT=8000
cd /d "%~dp0backend"

REM --- ambiente ja pronto? (testa se as bibliotecas carregam de verdade;
REM     uma pasta .venv copiada de outro computador costuma estar quebrada)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import fastapi, uvicorn, numpy" >nul 2>&1 && goto :extras
  echo Ambiente virtual invalido ^(provavelmente copiado de outro PC^). Recriando...
  rmdir /s /q ".venv"
)

REM --- localizar o Python (launcher "py" primeiro; evita o atalho da Microsoft Store)
set "PY="
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo [ERRO] Python 3.10 ou superior nao encontrado.
  echo Instale em https://www.python.org/downloads/ e marque a opcao
  echo "Add python.exe to PATH" durante a instalacao. Depois rode este arquivo de novo.
  echo.
  pause
  exit /b 1
)

echo Preparando o SimpliFlix pela primeira vez (requer internet, 1-3 minutos)...
%PY% -m venv .venv || goto :erro
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :erro
echo Ambiente pronto.
goto :run

REM --- ambiente antigo, criado antes da exportacao de figuras: instala so o que falta.
REM     Sem internet o site continua funcionando; apenas o botao de baixar figura avisa.
:extras
".venv\Scripts\python.exe" -c "import matplotlib" >nul 2>&1 && goto :run
echo Instalando o componente de exportacao de figuras...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 echo [AVISO] Nao foi possivel instalar agora. O site funciona, mas sem exportar figuras.

:run
echo.
echo  SimpliFlix rodando em http://localhost:%PORT%
echo  Para encerrar, feche esta janela ou pressione Ctrl+C.
echo.
REM abre o navegador alguns segundos depois, quando o servidor ja respondeu
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://localhost:%PORT%"
".venv\Scripts\python.exe" -m uvicorn app.main:app --port %PORT%
if errorlevel 1 (
  echo.
  echo [ERRO] O servidor nao iniciou. Se a porta %PORT% estiver em uso, feche o outro
  echo programa ou rode:  set PORT=8001 ^&^& iniciar.bat
  pause
)
exit /b 0

:erro
echo.
echo [ERRO] Falha ao preparar o ambiente. Verifique a conexao com a internet
echo e se o Python 3.10+ esta instalado, depois rode este arquivo novamente.
pause
exit /b 1
