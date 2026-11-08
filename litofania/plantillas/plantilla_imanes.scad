// =====================================================================
//  Plantillas para imanes de nevera de acrílico (kit "DIY" 5x5 cm)
//  Paramétrico: cambia lado/radio/grosores para otros tamaños.
//
//  Piezas (elige con "pieza"):
//    "base_corte"  -> base plana con 2 pines y ranura bajo la línea de corte
//    "marco_corte" -> marco con ventana del tamaño del acrílico; encaja
//                     en los pines y guía el cúter por dentro
//    "montaje"     -> plantilla con hueco: acrílico boca abajo, luego
//                     foto recortada y luego lámina magnética
//    "todo"        -> las tres piezas juntas (vista)
//    "despiece"    -> vista explicativa
//
//  El script hacer_hoja_fotos.py genera el PDF con las fotos y las
//  cruces de los pines a la misma distancia (sep_pines).
// =====================================================================

pieza = "todo";

// --- Medidas del kit (mídelas con calibre) ---------------------------
lado            = 50;    // lado del acrílico (mm)
radio           = 4;     // radio de las esquinas del acrílico
grosor_acrilico = 3;     // grosor del acrílico
grosor_papel    = 0.25;  // foto + cinta doble cara
grosor_iman     = 0.8;   // lámina magnética

// --- Ajustes ---------------------------------------------------------
holgura         = 0.3;   // juego del hueco de montaje (por lado)
margen_corte    = 0.2;   // la foto queda este tanto más pequeña por lado
sep_pines       = lado/2 + 10;  // distancia del centro a cada pin (¡igual en el PDF!)
d_pin           = 2;     // diámetro de los pines
alto_pin        = 4;     // altura de los pines sobre la base
holgura_pin     = 0.4;   // juego de los agujeros del marco (en diámetro)
grosor_base     = 3;
grosor_marco    = 3;
borde           = 8;     // material alrededor de ventanas/huecos
ancho_ranura    = 1.2;   // ranura bajo la línea de corte
fondo_ranura    = 0.8;

$fn = 64;

// ---------------------------------------------------------------------
ancho_ext = 2*sep_pines + 2*borde;   // ancho exterior de base y marco
alto_ext  = lado + 2*borde;
radio_ext = 4;

module cuadrado_redondo(l, r, h) {
    r2 = max(r, 0.01);
    linear_extrude(h)
        offset(r = r2) square([l - 2*r2, l - 2*r2], center = true);
}

module rect_redondo(a, b, r, h) {
    linear_extrude(h)
        offset(r = r) square([a - 2*r, b - 2*r], center = true);
}

module texto(t, tam, h) {
    linear_extrude(h) text(t, size = tam, halign = "center", valign = "center",
                           font = "Liberation Sans:style=Bold");
}

// ---------------- BASE DE CORTE --------------------------------------
module base_corte() {
    difference() {
        rect_redondo(ancho_ext, alto_ext, radio_ext, grosor_base);
        // ranura bajo la línea de corte (el cúter no marca la base)
        lc = lado - 2*margen_corte;
        translate([0, 0, grosor_base - fondo_ranura])
            difference() {
                cuadrado_redondo(lc + ancho_ranura, radio + ancho_ranura/2, fondo_ranura + 1);
                translate([0, 0, -0.5])
                    cuadrado_redondo(lc - ancho_ranura, max(radio - ancho_ranura/2, 0.1), fondo_ranura + 2);
            }
        // texto
        translate([0, -alto_ext/2 + 3.2, grosor_base - 0.4])
            texto(str(lado, " mm"), 3, 1);
    }
    // pines con punta cónica para pinchar el papel por la cruz
    for (s = [-1, 1])
        translate([s*sep_pines, 0, grosor_base]) {
            cylinder(d = d_pin, h = alto_pin - 1.2);
            translate([0, 0, alto_pin - 1.2]) cylinder(d1 = d_pin, d2 = 0.4, h = 1.2);
        }
}

// ---------------- MARCO DE CORTE -------------------------------------
module marco_corte() {
    lc = lado - 2*margen_corte;
    difference() {
        rect_redondo(ancho_ext, alto_ext, radio_ext, grosor_marco);
        // ventana: el cúter se apoya en esta pared
        translate([0, 0, -1]) cuadrado_redondo(lc, radio - margen_corte, grosor_marco + 2);
        // agujeros de los pines
        for (s = [-1, 1])
            translate([s*sep_pines, 0, -1]) cylinder(d = d_pin + holgura_pin, h = grosor_marco + 2);
        // flecha "arriba" grabada
        translate([0, alto_ext/2 - borde/2, grosor_marco - 0.4])
            linear_extrude(1) polygon([[-2.5, -1.5], [2.5, -1.5], [0, 1.8]]);
    }
}

// ---------------- PLANTILLA DE MONTAJE -------------------------------
fondo_hueco = grosor_acrilico + grosor_papel + max(grosor_iman - 0.3, 0.2);
grosor_montaje = fondo_hueco + 2;

module montaje() {
    lh = lado + 2*holgura;
    le = lh + 2*borde;
    difference() {
        rect_redondo(le, le, radio_ext, grosor_montaje);
        // hueco
        translate([0, 0, grosor_montaje - fondo_hueco])
            cuadrado_redondo(lh, radio + holgura, fondo_hueco + 1);
        // muescas para sacar la pieza con el dedo (dos lados)
        for (s = [-1, 1])
            translate([s*(lh/2), 0, grosor_montaje - fondo_hueco + 0.01])
                scale([1, 1.6, 1]) cylinder(d = 14, h = fondo_hueco + 1);
        // texto
        translate([0, -le/2 + borde/2, grosor_montaje - 0.4])
            texto("CARA BOCA ABAJO", 2.6, 1);
    }
}

// ---------------- SALIDA --------------------------------------------
module pieza_acrilico() color([0.8, 0.9, 1, 0.5]) cuadrado_redondo(lado, radio, grosor_acrilico);

if (pieza == "base_corte")  base_corte();
if (pieza == "marco_corte") marco_corte();
if (pieza == "montaje")     montaje();
if (pieza == "todo") {
    translate([0, alto_ext/2 + 5, 0]) color("SteelBlue") base_corte();
    translate([0, -alto_ext/2 - 5, 0]) color("Orange") marco_corte();
    translate([ancho_ext/2 + lado/2 + borde + 15, 0, 0]) color("MediumSeaGreen") montaje();
}
if (pieza == "despiece") {
    color("SteelBlue") base_corte();
    translate([0, 0, grosor_base + 0.3]) color("white") cuadrado_redondo(lado + 8, 1, 0.25);
    translate([0, 0, grosor_base + 12]) color("Orange") marco_corte();
}

echo(str("Separación entre pines: ", 2*sep_pines, " mm (", sep_pines, " desde el centro)"));
echo(str("Foto recortada: ", lado - 2*margen_corte, " mm; hueco de montaje: ",
         lado + 2*holgura, " mm, fondo ", fondo_hueco, " mm"));
