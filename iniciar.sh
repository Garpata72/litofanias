#!/usr/bin/env bash
# Litofanías - arranque en macOS y Linux. Prepara el entorno la primera vez.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Preparando el entorno por primera vez..."
  python3 -m venv .venv
fi
if ! cmp -s requirements.txt .venv/requirements.instalado; then
  echo "Instalando dependencias..."
  .venv/bin/python -m pip install -r requirements.txt
  cp requirements.txt .venv/requirements.instalado
fi
exec .venv/bin/python run.py "$@"
