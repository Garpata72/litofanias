# Litofanías

App local (Python + FastAPI, todo offline) para ajustar una imagen y generar litofanías: planas, curvas, cilíndricas y esféricas, más cajas de luz y soportes.

## Fase 0: litofanía plana desde la línea de comandos

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python make_flat.py foto.jpg litofania.stl --ancho 150
```

Opciones principales (valores por defecto pensados para una Ender 3 V3 KE con boquilla 0,4):

| Opción | Defecto | Qué hace |
| --- | --- | --- |
| `--ancho` | 150 | Ancho total en mm, marco incluido |
| `--min` / `--max` | 0,8 / 3,0 | Grosor en mm de las zonas claras / oscuras |
| `--resolucion` | 0,2 | mm por píxel |
| `--marco` | 3 | Ancho del marco en mm (0 = sin marco) |
| `--brillo`, `--contraste`, `--gamma` | 1 | Ajustes básicos de imagen |
| `--invertir` | no | Invierte claros y oscuros |

### Consejos de impresión

PLA blanco, relleno 100 %, altura de capa 0,12 mm y la pieza de pie (en vertical) en el laminador. El relieve queda en la cara delantera; la trasera es plana.

## Tests

```bash
pytest
```
