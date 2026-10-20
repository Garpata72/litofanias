#!/usr/bin/env bash
# Crea un acceso directo a Litofanías: en macOS en el escritorio, en Linux en el menú y el escritorio.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/iniciar.sh"
if [ "$(uname)" = "Darwin" ]; then
  LANZ="$HOME/Desktop/Litofanias.command"
  printf '#!/bin/bash\nexec "%s/iniciar.sh"\n' "$DIR" > "$LANZ"
  chmod +x "$LANZ"
  echo "Creado $LANZ (doble clic para abrir; puedes arrastrarlo al Dock)."
else
  APPS="$HOME/.local/share/applications"
  mkdir -p "$APPS"
  cat > "$APPS/litofanias.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Litofanías
Comment=Crea litofanías a partir de tus fotos
Exec="$DIR/iniciar.sh"
Icon=$DIR/app/static/icono.png
Terminal=true
Categories=Graphics;
DESK
  chmod +x "$APPS/litofanias.desktop"
  DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
  [ -d "$DESKTOP" ] && cp "$APPS/litofanias.desktop" "$DESKTOP/" && chmod +x "$DESKTOP/litofanias.desktop"
  echo "Acceso directo creado en el menú de aplicaciones y en el escritorio."
fi
