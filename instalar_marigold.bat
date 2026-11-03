@echo off
rem Prepara Marigold para la app: crea .venv-marigold, instala PyTorch y baja el modelo (unos 3 GB + 2,6 GB, necesita internet).
rem Despues la app lo usa sola (metodo Marigold en el panel de Bajorrelieve), sin internet.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Instalar Marigold

set "PY="
rem PyTorch con CUDA publica ruedas para Python 3.9-3.12 de forma fiable: si hay un 3.12 instalado se usa ese.
py -3.12 --version >nul 2>nul && set "PY=py -3.12"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not exist ".venv-marigold\Scripts\python.exe" (
  if not defined PY (
    echo No se encuentra Python. Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
    pause
    exit /b 1
  )
  echo Preparando el entorno de Marigold...
  %PY% -m venv .venv-marigold
  if errorlevel 1 goto :error
)
set "VPY=.venv-marigold\Scripts\python.exe"

fc /b requirements-marigold.txt .venv-marigold\requirements.instalado >nul 2>nul
if errorlevel 1 (
  echo Instalando PyTorch con CUDA. Puede tardar varios minutos...
  "%VPY%" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cu126
  if errorlevel 1 "%VPY%" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cu121
  if errorlevel 1 "%VPY%" -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cu118
  if errorlevel 1 goto :torch
  echo Instalando el resto de librerias...
  "%VPY%" -m pip install --disable-pip-version-check -r requirements-marigold.txt
  if errorlevel 1 goto :error
  copy /y requirements-marigold.txt .venv-marigold\requirements.instalado >nul
)

echo Descargando el modelo de Marigold, solo la primera vez...
"%VPY%" marigold_worker.py --descargar
if errorlevel 1 goto :error
echo.
echo Marigold esta listo. Abre la app: aparece como metodo en Bajorrelieve.
pause
exit /b 0

:torch
echo.
echo No se ha podido instalar PyTorch. Casi siempre es porque tu Python es demasiado nuevo para PyTorch.
echo Version de Python de este entorno:
"%VPY%" --version
echo Solucion: instala Python 3.12 desde https://www.python.org/downloads/release/python-3129/
echo borra la carpeta .venv-marigold y vuelve a ejecutar este archivo.
pause
exit /b 1

:error
echo.
echo Algo ha fallado (mira el mensaje de arriba).
pause
exit /b 1
