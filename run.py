"""Arranque de Litofanías.

    python run.py                 solo este equipo, puerto 8040
    python run.py --port 8041     otro puerto
    python run.py --no-browser    no abrir el navegador

En Windows lo más cómodo es el acceso directo del escritorio (lo crea crear_acceso_directo.bat)
o doble clic en iniciar.bat. Las imágenes y los STL se guardan en la carpeta «datos» junto a
este fichero; se puede cambiar con la variable de entorno LITOFANIAS_DATOS.
"""
import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
DEFAULT_PORT = 8040   # 8000, 8010 y 8020 los usan otras aplicaciones

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows
    except (AttributeError, OSError):
        pass


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def already_running(port: int) -> bool:
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/salud", timeout=1).read()
        return b"litofanias" in body
    except OSError:
        return False


def wait_and_open(port: int) -> None:
    for _ in range(60):
        if already_running(port):
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return
        time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser(description="Litofanías")
    ap.add_argument("--host", default=os.environ.get("LITOFANIAS_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("LITOFANIAS_PORT", DEFAULT_PORT)))
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not port_free(args.host, args.port):
        if already_running(args.port):
            # Segundo doble clic en el acceso directo: la app ya está abierta, solo se muestra.
            if not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{args.port}/")
            print("Litofanías ya estaba abierta; se ha mostrado en el navegador.")
            return 0
        print(f"\nEl puerto {args.port} lo está usando otra aplicación.")
        print(f"Usa otro puerto:  python run.py --port {args.port + 1}\n")
        return 1

    from app import main as app_main
    from app import storage

    print("\n  Litofanías")
    print("  " + "-" * 56)
    print(f"  Dirección:   http://127.0.0.1:{args.port}/")
    print(f"  Datos:       {storage.ROOT}")
    print("  Para parar: botón de apagado de la app, cerrar esta ventana o Ctrl+C")
    print("  " + "-" * 56 + "\n")

    if not args.no_browser:
        threading.Thread(target=wait_and_open, args=(args.port,), daemon=True).start()

    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app_main.app, host=args.host, port=args.port, log_level="warning", access_log=False))
    app_main.SERVER = server
    server.run()
    print("Litofanías cerrada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
