@echo off
rem Bajorrelieves, fase 0: arrastra fotos (o una carpeta) sobre este archivo para comparar los mapas de profundidad.
rem Usa el mismo entorno que iniciar.bat. La primera vez instala onnxruntime y descarga los modelos (necesita internet).
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Prueba de profundidad

if "%~1"=="" (
  echo Arrastra una o varias fotos, o una carpeta, sobre probar_profundidad.bat
  pause
  exit /b 1
)

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

fc /b requirements-ia.txt .venv\requirements-ia.instalado >nul 2>nul
if errorlevel 1 (
  echo Instalando las librerias de IA, solo la primera vez...
  "%VPY%" -m pip install --disable-pip-version-check -r requirements-ia.txt
  if errorlevel 1 goto :error
  copy /y requirements-ia.txt .venv\requirements-ia.instalado >nul
)

"%VPY%" prueba_profundidad.py --stl %*
if errorlevel 1 goto :error
start "" "resultados_profundidad"
pause
exit /b 0

:error
echo.
echo Algo ha fallado (mira el mensaje de arriba).
echo Si se repite, envia el archivo resultados_profundidad\errores.txt.
pause
exit /b 1
