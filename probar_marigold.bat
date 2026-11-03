@echo off
rem Prueba de Marigold: arrastra fotos (o una carpeta) sobre este archivo para compararlo con Depth Anything V3.
rem Usa un entorno aparte (.venv-marigold) con PyTorch. La primera vez instala unos 3 GB y descarga el modelo (necesita internet).
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Prueba de Marigold

if "%~1"=="" (
  echo Arrastra una o varias fotos, o una carpeta, sobre probar_marigold.bat
  pause
  exit /b 1
)

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not exist ".venv-marigold\Scripts\python.exe" (
  if not defined PY (
    echo No se encuentra Python. Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    pause
    exit /b 1
  )
  echo Preparando el entorno de Marigold por primera vez...
  %PY% -m venv .venv-marigold
  if errorlevel 1 goto :error
)
set "VPY=.venv-marigold\Scripts\python.exe"

fc /b requirements-marigold.txt .venv-marigold\requirements.instalado >nul 2>nul
if errorlevel 1 (
  echo Instalando PyTorch con CUDA, solo la primera vez. Puede tardar varios minutos...
  "%VPY%" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cu121
  if errorlevel 1 goto :error
  echo Instalando el resto de librerias...
  "%VPY%" -m pip install --disable-pip-version-check -r requirements-marigold.txt
  if errorlevel 1 goto :error
  copy /y requirements-marigold.txt .venv-marigold\requirements.instalado >nul
)

"%VPY%" prueba_marigold.py --stl %*
if errorlevel 1 goto :error
start "" "resultados_marigold"
pause
exit /b 0

:error
echo.
echo Algo ha fallado (mira el mensaje de arriba).
echo Si se repite, envia el archivo resultados_marigold\errores.txt.
pause
exit /b 1
