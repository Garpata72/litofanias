# Litofanías

App local para ajustar una foto y convertirla en una litofanía lista para imprimir en 3D. Funciona en tu ordenador, sin internet (solo la primera instalación descarga las librerías).

Genera litofanías **planas**, en **arco**, en **cilindro** y **lámpara cónica**, en **cúpula** (media esfera) y en **esfera** con abertura para la luz (tipo lámpara luna). Las cajas de luz y los soportes llegarán en la siguiente fase.

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
3. Elige la forma (plana, arco o cilindro), el tamaño, los grosores, la resolución y el marco, y pulsa **Generar y ver en 3D**. En el arco se indica el ancho desarrollado y el ángulo; en el cilindro, el diámetro exterior (la imagen da la vuelta completa y el marco va solo arriba y abajo). En la esfera y la cúpula, el diámetro exterior, la abertura de abajo (esfera) y cómo va la foto: **centrada delante** (ocupando los grados que elijas, con fondo claro alrededor) o **panorámica** (estirada a toda la esfera, ideal para fotos 2:1). La plana puede recortarse con un **contorno**: rectángulo, esquinas redondeadas, círculo, óvalo, corazón (con **base plana** opcional, que corta la punta para que se pegue mejor a la cama), **estrella** (número de puntas y radio interior) o **polígono** regular (de 3 a 12 lados, apoyado en un lado), y el marco sigue el borde; o con una **máscara propia**: sube una silueta negra sobre blanco (o un PNG con transparencia) y la pieza toma su forma. En la plana, la vista «Encuadre» permite arrastrar la foto y hacer zoom para colocarla dentro del contorno; con zoom menor que 1 la foto queda más pequeña que la pieza. Lo que la foto no tapa (en la plana, la esfera o la cúpula) lleva un **relleno**: liso o **luna** con mares y cráteres. El relleno también puede ser una **textura propia**: sube una imagen (mejor cuadrada, de 512 a 1024 px y «sin costuras»), se pasa a grises sola y puedes cambiar el tamaño del motivo, subir o bajar su relieve, invertirla o dejarla en blanco y negro. En la esfera también se puede elegir *Sin foto (solo relleno)* para una lámpara luna clásica.
   **Pestaña para colgar** (plana): añade arriba una pestaña redonda con agujero, del ancho y el agujero que elijas.
   **Varias fotos en una pieza**: marca *Usar varias fotos*, abre cada foto y pulsa *Añadir la foto abierta*. Van una al lado de otra con un borde oscuro entre ellas (*Separación*), en una o varias *Filas* en la plana, alrededor del cilindro (la primera delante) o en la esfera y la cúpula. Cada foto conserva su giro, su recorte y su encuadre: toca su miniatura para abrirla y arrástrala en su hueco. Todas toman la proporción de la primera.
   **Lámpara cónica**: como el cilindro, pero con un diámetro abajo y otro arriba (la foto da la vuelta entera). Tanto el cilindro como el cono admiten **ondas** en la pared (número y tamaño). La esfera y la cúpula admiten un **agujero arriba**, el **alto de la foto en grados** (la foto se recorta lo justo para llenar ese hueco) y, la esfera, un **cuello** recto bajo la abertura que encaja en una ranura de la peana y le da base plana.
   **Exportar 3MF**: el visor tiene un botón **3MF** con cada pieza como un objeto aparte; el de la litofanía lleva también su caja o su base si la has generado después, colocada al lado.
   **Más accesorios**: aro para colgar el cilindro o la lámpara de un casquillo **E27 o E14** (con radios; usa bombillas LED), caja de luz **de escritorio** con una peana que la inclina hacia atrás, hueco para **portapilas** por debajo de las bases (3 pilas AA por defecto, medidas ajustables) y aro que centra una **vela LED** de 39 mm.
   **Texto grabado** añade un nombre o una fecha en letras que se encienden: en una franja bajo la foto (plana rectangular, arco y cilindro), sobre la parte de abajo de la pieza (plana recortada) o encima de la abertura (esfera y cúpula).
   **Caja de luz y soporte** genera, a la medida de la última litofanía, una caja de luz (plana: bandeja con un repecho donde descansa la pieza y un **marco frontal que se quita y se pone**, sin puentes al imprimir, o, si prefieres, ranura por arriba; la ventana sigue el contorno), una base redonda (cilindro y cúpula), una base curva (arco) o una peana (esfera). Todas llevan hueco para una luz LED USB de 5 V y paso para el cable, y se imprimen sin soportes.
   **Voladizo máximo** limita en grados cuánto puede sobresalir el relieve (y el paso al marco) al imprimir de pie, para que salga sin hilos ni soportes. **Caras (caja)** convierte el cilindro en una caja de 3 a 8 caras planas con una foto por cara (con el collage, una foto distinta en cada una; sin collage, la misma en todas) y tiene su base con ranura poligonal.
   Con **Plantillas** guardas los ajustes con un nombre (se guardan en `datos/plantillas.json`) y los recuperas con un clic.
4. En el visor 3D gira la pieza, cambia entre **Relieve** (luz frontal) y **Contraluz** (cómo se verá encendida) y pulsa **Descargar STL** cuando te guste. **Ajustes de impresión** descarga un texto con la configuración recomendada para la Ender 3 V3 KE (orientación, capa, relleno, soportes) y el filamento aproximado.

Con **Ver STL / 3MF** (o arrastrando el archivo a la ventana) puedes abrir cualquier STL o 3MF de tu ordenador en el mismo visor. El visor usa three.js, incluido en `app/static/vendor/three` (licencia MIT), así que funciona sin internet.

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

PLA blanco, relleno 100 %, altura de capa 0,12 mm y la pieza de pie (en vertical) en el laminador. En la plana el relieve queda en la cara delantera y la trasera es plana. En arco y cilindro la cara exterior es lisa y el relieve va por dentro, junto a la luz; los STL curvos ya salen de pie.

## Licencias

El texto grabado usa la fuente DejaVu Sans Bold, incluida en `litofania/fuentes/` con su licencia.

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest
```

## Bajorrelieves: prueba de mapas de profundidad (fase 0)

Primer paso para hacer monedas y medallones en relieve a partir de una foto: comparar cómo calcula la profundidad cada método con tus propias fotos, todo en tu ordenador.

- **Windows:** arrastra una o varias fotos (o una carpeta) sobre `probar_profundidad.bat`. La primera vez instala `onnxruntime-directml` (usa la tarjeta gráfica sin instalar CUDA) y descarga los modelos a la carpeta `modelos` (unos 1,4 GB en total, comprobados con SHA-256); después funciona sin internet.
- **A mano:** `pip install -r requirements-ia.txt` y `python prueba_profundidad.py fotos/ --stl`.

Para cada foto deja en `resultados_profundidad/<foto>/` una hoja `comparativa.png` (mapa de profundidad y bajorrelieve con luz rasante por método, con el tiempo de cálculo), los mapas en PNG de 16 bits y, con `--stl`, una moneda de prueba de 50 mm por método (base 2 mm, relieve 1,6 mm, aro 2,5 mm). Los tiempos de todas las fotos quedan en `tiempos.txt`.

Métodos: **Detalle sin IA** (luminancia con contraste local, para monedas o grabados fotografiados), **Depth Anything V2 Small** por procesador y por gráfica, y **Depth Anything V2 Large** (licencia no comercial, válida para uso personal). `--depthpro` añade Apple Depth Pro (600 MB, muy lento sin una gráfica potente) y `--sin-large` se salta el modelo grande.

`--fondo auto` (por defecto, también en `probar_profundidad.bat`) deja liso el fondo con BiRefNet lite (MIT, 224 MB, también local) cuando la foto tiene un motivo claro (retrato, animal, objeto), para que cortinas, ramas o halos no entren en el relieve. Si la foto ya es un relieve (un panel con varias figuras) lo conserva entero. `--fondo si` lo fuerza y `--fondo no` lo desactiva.

Con `--stl` la moneda de prueba puede tener otra forma (`--forma circulo|ovalo|redondeado|escudo`) y pestaña para colgar (`--colgar`); además del STL deja una vista `*-moneda.png` de la pieza entera.

Fotos recomendadas: JPEG de calidad alta o PNG, de 2000 a 4000 px en el lado corto, luz difusa sin sombras duras, motivo nítido ocupando el 60-80 % y fondo liso.
