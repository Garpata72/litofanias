@echo off
rem Litofanias - arranque. Doble clic (o el acceso directo del escritorio) para iniciar.
setlocal
cd /d "%~dp0"
title Litofanias

rem 1) Python y entorno virtual (se crea solo la primera vez en la carpeta ".venv")
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not exist ".venv\Scripts\python.exe" (
  if not defined PY (
    echo No se encuentra Python. Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    pause
    exit /b 1
  )
  echo Preparando el entorno por primera vez...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)
set "VPY=.venv\Scripts\python.exe"

rem 2) Dependencias: solo se instalan si requirements.txt ha cambiado (necesita internet solo entonces)
fc /b requirements.txt .venv\requirements.instalado >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias...
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  copy /y requirements.txt .venv\requirements.instalado >nul
)

rem 3) Servidor (los argumentos pasan a run.py: --port 8041, --no-browser)
"%VPY%" run.py %*
if errorlevel 1 pause
exit /b 0

:error
echo.
echo Algo ha fallado en la preparacion (mira el mensaje de arriba).
pause
exit /b 1
