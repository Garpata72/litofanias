# Litofanías

App local para ajustar una foto y convertirla en una litofanía lista para imprimir en 3D. Funciona en tu ordenador, sin internet (solo la primera instalación descarga las librerías).

Hoy genera litofanías **planas**; arco, cilindro, esfera y cajas de luz llegarán en las próximas fases.

## Arrancar con un acceso directo

**Windows**

1. Instala Python 3 desde https://www.python.org/downloads/ marcando «Add python.exe to PATH».
2. Doble clic en `crear_acceso_directo.bat`. Crea el icono **Litofanías** en el escritorio y en el menú Inicio.
3. A partir de ahí, doble clic en el icono. La primera vez prepara el entorno (tarda un par de minutos y necesita internet); las siguientes arranca en segundos y abre el navegador en http://127.0.0.1:8040/.

Si la app ya está abierta, el acceso directo solo vuelve a mostrarla. Para cerrarla: botón de apagado (arriba a la derecha) o cerrar la ventana de consola.

**macOS / Linux:** `./crear_acceso_directo.sh` crea el acceso directo (en macOS un `Litofanias.command` en el escritorio, que puedes arrastrar al Dock). También puedes arrancar con `./iniciar.sh`.

**A mano:** `pip install -r requirements.txt` y `python run.py` (`--port 8041` para otro puerto, `--no-browser` para no abrir el navegador).

Puerto por defecto: **8040** (8000, 8010 y 8020 los usan otras apps).

## Cómo se usa

1. **Abrir imagen** o arrastrarla a la ventana.
2. Ajusta brillo, contraste, gamma o invierte; la vista **A contraluz** simula cómo se verá impresa.
3. Elige tamaño, grosores, resolución y marco, y pulsa **Generar STL**.

Las imágenes y los STL se guardan en `datos/`, junto a la app (se puede cambiar con la variable `LITOFANIAS_DATOS`).

## Línea de comandos

```bash
python make_flat.py foto.jpg litofania.stl --ancho 150
```

| Opción | Defecto | Qué hace |
| --- | --- | --- |
| `--ancho` | 150 | Ancho total en mm, marco incluido |
| `--min` / `--max` | 0,8 / 3,0 | Grosor en mm de las zonas claras / oscuras |
| `--resolucion` | 0,2 | mm por píxel |
| `--marco` | 3 | Ancho del marco en mm (0 = sin marco) |
| `--brillo`, `--contraste`, `--gamma` | 1 | Ajustes básicos de imagen |
| `--invertir` | no | Invierte claros y oscuros |

## Consejos de impresión (Ender 3 V3 KE)

PLA blanco, relleno 100 %, altura de capa 0,12 mm y la pieza de pie (en vertical) en el laminador. El relieve queda en la cara delantera; la trasera es plana.

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest
```
