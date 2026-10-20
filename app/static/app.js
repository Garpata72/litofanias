/* Litofanías — interfaz. Sin librerías externas: todo funciona sin internet. */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const ICONS = {
  menu: "M4 6h16 M4 12h16 M4 18h16",
  plus: "M12 5v14 M5 12h14",
  power: "M12 3v8 M6.6 6.6a8 8 0 1 0 10.8 0",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7 M20 4v7h-7",
  upload: "M12 16V4 M7 9l5-5 5 5 M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
  download: "M12 4v12 M7 11l5 5 5-5 M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
  cube: "M12 3l8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9",
  fit: "M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5",
  close: "M6 6l12 12 M18 6L6 18",
  save: "M5 4h11l3 3v13H5z M8 4v5h7V4 M8 20v-6h8v6",
  trash: "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13 M10 11v6 M14 11v6",
  doc: "M7 3h7l5 5v13H7z M14 3v5h5 M10 13h6 M10 17h6",
  lamp: "M9 18h6 M10 21h4 M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
};
const icon = (name) => `<span class="ico" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${ICONS[name] || ""}"/></svg></span>`;
$$("[data-icon]").forEach((e) => e.insertAdjacentHTML("afterbegin", icon(e.dataset.icon)));

let toastTimer;
function toast(msg, kind = "") {
  const t = $("#toast");
  $(".msgtext", t).textContent = msg;
  t.className = `show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = ""), kind === "err" ? 6000 : 3500);
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = `Error ${r.status}`;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : msg; } catch { /* sin cuerpo */ }
    throw new Error(msg);
  }
  return r;
}

/* ───────── Ajustes guardados en este navegador ───────── */
const PARAMS = ["brillo", "contraste", "gamma", "invertir", "forma", "contorno", "ancho", "angulo", "diametro", "agujero", "ajuste", "cobertura", "relleno", "texto", "texto_mm", "min", "max", "resolucion", "marco"];
const DEFAULTS = {
  brillo: 1, contraste: 1, gamma: 1, invertir: false,
  forma: "plana", contorno: "rectangulo", ancho: 150, angulo: 120, diametro: 80, agujero: 40, ajuste: "centrada", cobertura: 150, relleno: "liso", texto: "", texto_mm: 8,
  min: 0.8, max: 3, resolucion: 0.2, marco: 3,
};
const BED = { x: 220, y: 220, z: 240 };   // Ender 3 V3 KE
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(`lito.${k}`)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(`lito.${k}`, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
};

function readParams() {
  const p = {};
  for (const k of PARAMS) {
    const el = $(`#${k}`);
    p[k] = el.type === "checkbox" ? el.checked : el.tagName === "SELECT" || el.type === "text" ? el.value : Number(el.value);
  }
  return p;
}
function writeParams(p) {
  for (const k of PARAMS) {
    const el = $(`#${k}`);
    if (el.type === "checkbox") el.checked = !!p[k]; else el.value = p[k] ?? DEFAULTS[k];
  }
  showSliderValues();
}
function showSliderValues() {
  $$("output[data-for]").forEach((o) => (o.textContent = Number($(`#${o.dataset.for}`).value).toFixed(2)));
}
function showShapeFields() {
  const forma = $("#forma").value;
  const ajuste = $("#ajuste").value;
  $$("[data-shapes]").forEach((el) => {
    el.hidden = !el.dataset.shapes.split(" ").includes(forma)
      || (el.dataset.fit && SPHERE.includes(forma) && !el.dataset.fit.split(" ").includes(ajuste))
      || (el.dataset.contour && el.dataset.contour !== $("#contorno").value);
  });
  $$("[data-text]").forEach((el) => (el.hidden = !$("#texto").value.trim()));
  updateAccessoryButton();
}
/* Ancho de la imagen ya colocada: el de la plana, la longitud del arco o el perímetro del cilindro. */
const ROUND = ["cilindro", "esfera", "cupula"];
const SPHERE = ["esfera", "cupula"];
const developed = (p) => (ROUND.includes(p.forma) ? Math.PI * p.diametro : p.ancho);

function validParams(p) {
  let ok = true;
  for (const k of ["ancho", "angulo", "diametro", "agujero", "cobertura", "texto_mm", "min", "max", "resolucion", "marco"]) {
    const el = $(`#${k}`);
    const bad = !el.closest("label").hidden && !(p[k] >= Number(el.min) && p[k] <= Number(el.max));
    el.classList.toggle("bad", bad);
    ok &&= !bad;
  }
  if (p.min >= p.max) { $("#min").classList.add("bad"); $("#max").classList.add("bad"); ok = false; }
  if (!ROUND.includes(p.forma) && p.ancho <= 2 * p.marco + 5) { $("#marco").classList.add("bad"); ok = false; }
  if (ROUND.includes(p.forma) && p.diametro <= 2 * p.max + 10) { $("#diametro").classList.add("bad"); ok = false; }
  if (p.forma === "esfera" && p.agujero >= p.diametro - 10) { $("#agujero").classList.add("bad"); ok = false; }
  if (needsMask(p)) ok = false;
  return ok;
}

/* ───────── Estado ───────── */
let images = [];
let current = null;      // ficha de la imagen abierta
const source = new Image();
let masks = [];
let maskId = store.get("mascara");
const maskImg = new Image();
let frame = { zoom: 1, cx: 0.5, cy: 0.5 };   // encuadre de la foto en la plana, guardado por imagen

const maskMeta = () => masks.find((m) => m.id === maskId);
const customMask = (p) => p.forma === "plana" && p.contorno === "propia";
const needsMask = (p) => customMask(p) && !maskMeta();

async function loadMasks() {
  masks = await (await api("GET", "/api/mascaras")).json();
  const box = $("#masks");
  box.innerHTML = masks.length ? "" : `<div class="none">Todavía no has subido ninguna máscara.</div>`;
  for (const m of masks.slice(0, 24)) {
    const b = document.createElement("button");
    b.type = "button";
    b.title = m.nombre;
    b.style.backgroundImage = `url(/api/mascaras/${m.id}/archivo)`;
    b.classList.toggle("sel", m.id === maskId);
    b.addEventListener("click", () => selectMask(m.id));
    box.append(b);
  }
  if (maskMeta() && !maskImg.src.includes(maskId)) maskImg.src = `/api/mascaras/${maskId}/archivo`;
  queueDraw();
}

function selectMask(id) {
  maskId = id;
  store.set("mascara", id);
  maskImg.src = `/api/mascaras/${id}/archivo`;
  $$("#masks button").forEach((b) => b.classList.toggle("sel", b.style.backgroundImage.includes(id)));
  queueDraw();
}

async function uploadMask(file) {
  if (!file || !file.type.startsWith("image/")) { toast("Eso no parece una imagen.", "err"); return; }
  const fd = new FormData();
  fd.append("archivo", file);
  try {
    const meta = await (await api("POST", "/api/mascaras", fd)).json();
    maskId = meta.id;
    await loadMasks();
    selectMask(meta.id);
    $("#contorno").value = "propia";
    showShapeFields();
    toast(`Máscara «${meta.nombre}» lista.`, "ok");
  } catch (e) { toast(e.message, "err"); }
}

const ZOOM = { min: 0.25, max: 4 };

/* ───────── Encuadre ─────────
   Mismo cálculo que crop_window en litofania/heightmap.py: si se cambia uno, cambiar el otro. El centro
   es el punto de la foto que cae en el centro de la pieza; con zoom menor que 1 la foto es más pequeña que la pieza. */
function pieceAspect(p) {
  return customMask(p) && maskMeta() ? maskMeta().ancho / maskMeta().alto : current.ancho / current.alto;
}
function cropWindow(p) {
  const W = source.naturalWidth, H = source.naturalHeight;
  if (p.forma !== "plana") return { x: 0, y: 0, w: W, h: H };
  const a = pieceAspect(p), z = frame.zoom;
  let w, h;
  if (W / H > a) { h = H / z; w = h * a; } else { w = W / z; h = w / a; }
  return { x: frame.cx * W - w / 2, y: frame.cy * H - h / 2, w, h };
}
function setFrame(f, save = true) {
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  frame = { ...frame, ...f };
  frame = { zoom: clamp(frame.zoom, ZOOM.min, ZOOM.max), cx: clamp(frame.cx, 0, 1), cy: clamp(frame.cy, 0, 1) };
  $("#zoom").value = frame.zoom;
  showSliderValues();
  if (save && current) store.set(`encuadre.${current.id}`, frame);
  queueDraw();
}

async function loadImages() {
  images = await (await api("GET", "/api/imagenes")).json();
  const box = $("#images");
  box.innerHTML = images.length ? "" : `<div class="none">Todavía no has abierto ninguna imagen.</div>`;
  for (const m of images.slice(0, 24)) {
    const b = document.createElement("button");
    b.type = "button";
    b.title = m.nombre;
    b.style.backgroundImage = `url(/api/imagenes/${m.id}/archivo)`;
    b.classList.toggle("sel", current?.id === m.id);
    b.addEventListener("click", () => select(m));
    box.append(b);
  }
}

function select(meta) {
  current = meta;
  updateAccessoryButton();
  store.set("ultima", meta.id);
  $("#title").textContent = meta.nombre;
  $("#empty").hidden = true;
  $("#views").hidden = false;
  $("#btnStl").disabled = false;
  frame = { zoom: 1, cx: 0.5, cy: 0.5, ...(store.get(`encuadre.${meta.id}`) || {}) };
  $("#zoom").value = frame.zoom;
  showSliderValues();
  source.src = `/api/imagenes/${meta.id}/archivo`;
  $$("#images button").forEach((b) => b.classList.toggle("sel", b.title === meta.nombre && b.style.backgroundImage.includes(meta.id)));
  if (innerWidth <= 900) document.body.classList.remove("side-open");
}

async function upload(file) {
  if (!file || !file.type.startsWith("image/")) { toast("Eso no parece una imagen.", "err"); return; }
  const fd = new FormData();
  fd.append("archivo", file);
  try {
    const meta = await (await api("POST", "/api/imagenes", fd)).json();
    await loadImages();
    select(meta);
    toast(`Abierta «${meta.nombre}» (${meta.ancho} × ${meta.alto} px).`, "ok");
  } catch (e) { toast(e.message, "err"); }
}

/* ───────── Contornos de la plana ─────────
   Mismas fórmulas que litofania/contours.py: si se cambia una, cambiar la otra. */
function contourMask(rows, cols, contour) {
  const m = new Uint8Array(rows * cols).fill(1);
  if (contour === "rectangulo") return m;
  const aspect = (cols - 1) / (rows - 1);
  for (let i = 0; i < rows; i++) {
    const v = 1 - (2 * i) / (rows - 1);
    for (let j = 0; j < cols; j++) {
      const u = (2 * j) / (cols - 1) - 1;
      let inside;
      if (contour === "ovalo") inside = u * u + v * v <= 1;
      else if (contour === "circulo") {
        const [x, y] = aspect >= 1 ? [u * aspect, v] : [u, v / aspect];
        inside = x * x + y * y <= 1;
      } else if (contour === "redondeado") {
        const w = aspect, h = 1, r = 0.15 * 2 * Math.min(w, h);
        const x = Math.abs(u) * w, y = Math.abs(v) * h;
        inside = x <= w - r || y <= h - r || (x - (w - r)) ** 2 + (y - (h - r)) ** 2 <= r * r;
      } else {
        const x = u * 1.16, y = ((v + 1) / 2) * 2.27 - 1.02;
        inside = (x * x + y * y - 1) ** 3 - x * x * y ** 3 <= 0;
      }
      m[i * cols + j] = inside ? 1 : 0;
    }
  }
  return m;
}
function erode(mask, rows, cols, steps) {
  let m = mask;
  for (let s = 0; s < steps; s++) {
    const out = new Uint8Array(m.length);
    for (let i = 1; i < rows - 1; i++)
      for (let j = 1; j < cols - 1; j++) {
        const k = i * cols + j;
        out[k] = m[k] & m[k - 1] & m[k + 1] & m[k - cols] & m[k + cols];
      }
    m = out;
  }
  return m;
}

/* ───────── Vista previa a contraluz ─────────
   Reproduce en pequeño lo que hace el servidor: gris, brillo, contraste (sobre la media, como Pillow),
   gamma e inversión; luego grosor = mín + (1 - gris)·(máx - mín) y la luz que pasa decae con el grosor. */
const PREVIEW_MAX = 640;
const ABSORB = 1.1;    // por mm; aproximado para PLA blanco
let drawQueued = false;

function queueDraw() {
  if (drawQueued) return;
  drawQueued = true;
  requestAnimationFrame(() => { drawQueued = false; draw(); });
}

function draw() {
  const p = readParams();
  const ok = validParams(p);
  store.set("params", p);
  updateSummary(p, ok);
  if (!current || !source.complete || !source.naturalWidth) return;

  const flat = p.forma === "plana";
  if (customMask(p) && !(maskImg.complete && maskImg.naturalWidth)) return;   // se redibuja al cargar
  const wrap = p.forma === "cilindro";
  const cut = flat && p.contorno !== "rectangulo";   // el marco sigue el contorno
  const border = SPHERE.includes(p.forma) || cut ? 0 : p.marco;
  const inner = Math.max(5, developed(p) - (wrap ? 0 : 2 * border));
  const win = cropWindow(p);
  const scale = Math.min(PREVIEW_MAX / Math.max(win.w, win.h), flat ? 4 : 1);
  const w = Math.max(2, Math.round(win.w * scale));
  const h = Math.max(2, Math.round(win.h * scale));
  const pad = Math.round((border / inner) * w);
  const padX = wrap ? 0 : pad;
  const mask = cut ? shapeMask(p, h, w) : null;
  const band = cut ? erode(mask, h, w, Math.round((p.marco / Math.max(5, p.ancho)) * w)) : null;
  const fill = flat ? fillLayer(p, w, h) : null;
  drawFrame(p, win, w, h, mask, band, fill);

  // Capa de la foto (transparente donde no llega) y gris del relleno debajo.
  const k = w / win.w;
  const layer = document.createElement("canvas");
  layer.width = w;
  layer.height = h;
  const lctx = layer.getContext("2d", { willReadFrequently: true });
  lctx.drawImage(source, -win.x * k, -win.y * k, source.naturalWidth * k, source.naturalHeight * k);
  const d = lctx.getImageData(0, 0, w, h).data;
  const bg = fill ? fillGray(fill, w, h) : null;

  const mean = sourceMean(p.brillo);
  const tMin = Math.exp(-ABSORB * p.min);
  const light = (t) => Math.exp(-ABSORB * t) / tMin;

  // Texto grabado: franja debajo en las piezas rectangulares, banda sobre la pieza en las recortadas.
  const text = SPHERE.includes(p.forma) ? "" : p.texto.trim();
  const pxPerMm = w / (cut ? Math.max(5, p.ancho) : inner);
  const textPx = p.texto_mm * pxPerMm;
  const bandH = text && !cut ? Math.round(textPx * (1 + 2 * TEXT_MARGIN)) : 0;

  const cv = $("#cvLit");
  cv.width = w + 2 * padX;
  cv.height = h + bandH + 2 * pad;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(w, h);
  const o = img.data;
  for (let i = 0, j = 0; j < w * h; i += 4, j++) {
    const a = d[i + 3] / 255;
    let g = bg ? bg[j] : 0;
    if (a > 0) {
      const raw = Math.min(255, (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) * p.brillo);
      let gp = Math.min(255, Math.max(0, mean + (raw - mean) * p.contraste)) / 255;
      if (p.gamma !== 1) gp = gp ** p.gamma;
      if (p.invertir) gp = 1 - gp;
      g = a * gp + (1 - a) * g;
    }
    const L = light(p.min + (1 - g) * (p.max - p.min));
    o[i] = 255 * L; o[i + 1] = 222 * L; o[i + 2] = 170 * L; o[i + 3] = 255;
  }
  const edge = light(p.max);
  if (cut) {
    for (let j = 0; j < mask.length; j++) {
      const i = 4 * j;
      if (!mask[j]) o[i + 3] = 0;
      else if (!band[j]) { o[i] = 255 * edge; o[i + 1] = 222 * edge; o[i + 2] = 170 * edge; }
    }
  } else {
    ctx.fillStyle = `rgb(${255 * edge},${222 * edge},${170 * edge})`;
    ctx.fillRect(0, 0, cv.width, cv.height);
  }
  ctx.putImageData(img, padX, pad);
  const lit = (t) => { const L = light(t); return `rgb(${255 * L},${222 * L},${170 * L})`; };
  if (text && !cut) engrave(ctx, text, textPx, padX, pad + h, w, bandH, lit(p.max), lit(p.min), false);
  if (text && cut) {
    // Misma búsqueda que text.overlay: la banda sube hasta caber dentro de la pieza sin el marco.
    const allowed = erode(mask, h, w, Math.round((p.marco / Math.max(5, p.ancho)) * w) + 2);
    let size = textPx;
    let bw = Math.round(textWidth(text, size) + 2 * TEXT_MARGIN * size);
    if (bw > 0.7 * w) { size *= (0.7 * w) / bw; bw = Math.round(0.7 * w); }
    const bh = Math.round(size * (1 + 2 * TEXT_MARGIN));
    const c0 = Math.max(0, Math.round(w / 2 - bw / 2));
    let bottom = h - 1;
    const fits = (b) => {
      for (let i = b - bh + 1; i <= b; i++) for (let j = c0; j < c0 + bw; j++) if (!allowed[i * w + j]) return false;
      return true;
    };
    while (bottom - bh + 1 > 0 && !fits(bottom)) bottom--;
    engrave(ctx, text, size, padX + c0, pad + Math.max(0, bottom - bh + 1), bw, bh, lit(p.max), lit(p.min), true);
  }
}

/* Texto grabado con la misma fuente que el STL (la sirve la app): banda gruesa y letras finas. */
const TEXT_MARGIN = 0.4;   // como text.MARGIN
const engraveFont = new FontFace("Grabado", "url(/api/fuente.ttf)");
engraveFont.load().then((f) => { document.fonts.add(f); queueDraw(); }).catch(() => { /* se usa la de sistema */ });
const measureCtx = document.createElement("canvas").getContext("2d");
function textBox(text, px) {
  measureCtx.font = `100px Grabado, sans-serif`;
  const m = measureCtx.measureText(text);
  const k = px / Math.max(1, m.actualBoundingBoxAscent + m.actualBoundingBoxDescent);
  return { size: 100 * k, width: m.width * k, ascent: m.actualBoundingBoxAscent * k, descent: m.actualBoundingBoxDescent * k };
}
const textWidth = (text, px) => textBox(text, px).width;
function engrave(ctx, text, px, x, y, bw, bh, dark, light, fixedWidth) {
  let box = textBox(text, px);
  const room = bw - 2 * TEXT_MARGIN * px;
  if (!fixedWidth && box.width > room) box = textBox(text, (px * room) / box.width);
  ctx.fillStyle = dark;
  ctx.fillRect(x, y, bw, bh);
  ctx.fillStyle = light;
  ctx.font = `${box.size}px Grabado, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(text, x + bw / 2, y + bh / 2 + (box.ascent - box.descent) / 2);
}

/* Media de gris de la foto entera tras el brillo, como hace Pillow con el contraste. */
let statsFor = null, statsGray = null;
function sourceMean(brillo) {
  if (statsFor !== source.src) {
    const c = document.createElement("canvas");
    const s = Math.min(1, 128 / Math.max(source.naturalWidth, source.naturalHeight));
    c.width = Math.max(1, Math.round(source.naturalWidth * s));
    c.height = Math.max(1, Math.round(source.naturalHeight * s));
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(source, 0, 0, c.width, c.height);
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    statsGray = new Float32Array(d.length / 4);
    for (let i = 0, j = 0; j < statsGray.length; i += 4, j++) statsGray[j] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    statsFor = source.src;
  }
  let sum = 0;
  for (const g of statsGray) sum += Math.min(255, g * brillo);
  return Math.round(sum / statsGray.length);
}

/* Relleno de lo que la foto no tapa: liso (gris fijo) o la luna que genera el servidor, la misma del STL. */
const PLAIN = 0.85;   // como textures.PLAIN
const moonImg = new Image();
moonImg.addEventListener("load", () => queueDraw());
function fillLayer(p, w, h) {
  if (p.relleno !== "luna") return { kind: "liso" };
  const url = `/api/relleno/luna.png?ancho=${w}&alto=${h}`;
  if (!moonImg.src.endsWith(url)) moonImg.src = url;
  return moonImg.complete && moonImg.naturalWidth === w && moonImg.naturalHeight === h ? { kind: "luna", img: moonImg } : { kind: "liso" };
}
function fillGray(fill, w, h) {
  const g = new Float32Array(w * h);
  if (fill.kind !== "luna") return g.fill(PLAIN);
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(fill.img, 0, 0);
  const d = ctx.getImageData(0, 0, w, h).data;
  for (let j = 0; j < g.length; j++) g[j] = d[4 * j] / 255;
  return g;
}

/* Máscara de la pieza en la rejilla de la vista previa: un contorno de fórmula o la máscara subida. */
function shapeMask(p, rows, cols) {
  if (!customMask(p)) return contourMask(rows, cols, p.contorno);
  const c = document.createElement("canvas");
  c.width = cols;
  c.height = rows;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(maskImg, 0, 0, cols, rows);
  const d = ctx.getImageData(0, 0, cols, rows).data;
  const m = new Uint8Array(rows * cols);
  for (let k = 0; k < m.length; k++) m[k] = d[4 * k] >= 128 ? 1 : 0;
  return m;
}

/* Primera vista: la pieza con la foto colocada y un margen alrededor donde se ve, atenuada, la parte de la
   foto que se queda fuera. En la plana se arrastra y se hace zoom; lo que queda fuera del contorno se
   oscurece y la franja del marco se marca en ámbar. */
let frameGeom = { w: 1, total: 1 };
function drawFrame(p, win, w, h, mask, band, fill) {
  const flat = p.forma === "plana";
  const cv = $("#cvFrame");
  cv.classList.toggle("movable", flat);
  $("#capFrame").textContent = flat ? "Encuadre (arrastra la foto)" : "Original";
  const M = flat ? Math.round(0.2 * Math.max(w, h)) : 0;
  cv.width = w + 2 * M;
  cv.height = h + 2 * M;
  frameGeom = { w, total: w + 2 * M };
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#0e1116";
  ctx.fillRect(0, 0, cv.width, cv.height);
  if (fill) {
    if (fill.kind === "luna") ctx.drawImage(fill.img, M, M, w, h);
    else { ctx.fillStyle = `rgb(${255 * PLAIN},${255 * PLAIN},${255 * PLAIN})`; ctx.fillRect(M, M, w, h); }
  }
  const k = w / win.w;
  ctx.drawImage(source, M - win.x * k, M - win.y * k, source.naturalWidth * k, source.naturalHeight * k);
  if (!flat) return;

  // Fuera de la pieza: la foto se ve atenuada.
  ctx.fillStyle = "rgba(14, 17, 22, 0.7)";
  ctx.fillRect(0, 0, cv.width, M);
  ctx.fillRect(0, M + h, cv.width, M);
  ctx.fillRect(0, M, M, h);
  ctx.fillRect(M + w, M, M, h);
  ctx.strokeStyle = "rgba(251, 191, 36, 0.8)";
  ctx.setLineDash([6, 4]);
  ctx.strokeRect(M - 0.5, M - 0.5, w + 1, h + 1);
  if (!mask) return;
  const over = new ImageData(w, h);
  for (let j = 0; j < mask.length; j++) {
    const i = 4 * j;
    if (!mask[j]) { over.data[i] = 14; over.data[i + 1] = 17; over.data[i + 2] = 22; over.data[i + 3] = 200; }
    else if (!band[j]) { over.data[i] = 251; over.data[i + 1] = 191; over.data[i + 2] = 36; over.data[i + 3] = 120; }
  }
  const tmp = document.createElement("canvas");
  tmp.width = w;
  tmp.height = h;
  tmp.getContext("2d").putImageData(over, 0, 0);
  ctx.drawImage(tmp, M, M);
}

function updateSummary(p, ok) {
  if (!current) { $("#summary").textContent = ""; return; }
  if (!ok) { $("#summary").textContent = needsMask(p) ? "Sube o elige una máscara para el contorno propio." : "Revisa los valores marcados en rojo."; $("#btnStl").disabled = true; return; }
  $("#btnStl").disabled = false;
  const wrap = p.forma === "cilindro";
  const W = developed(p);
  const pad = Math.round(p.marco / p.resolucion);
  const cols = wrap ? Math.round(W / p.resolucion) : Math.max(2, Math.round((W - 2 * p.marco) / p.resolucion) + 1) + 2 * pad;
  const imgCols = wrap ? cols : cols - 2 * pad;
  const rows = Math.max(2, Math.round(imgCols / (p.forma === "plana" ? pieceAspect(p) : current.ancho / current.alto))) + 2 * pad;
  const textBand = p.texto.trim() && !(p.forma === "plana" && p.contorno !== "rectangulo") ? p.texto_mm * (1 + 2 * TEXT_MARGIN) : 0;
  const H = (rows - 1) * p.resolucion + textBand;
  const tris = 4 * rows * cols;
  const fmt = (n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 });

  let size, onBed;
  if (SPHERE.includes(p.forma)) {
    const R = p.diametro / 2;
    const top = Math.PI / 2 - p.resolucion / R;
    const bottom = p.forma === "cupula" ? 0 : -Math.acos(Math.min(1, p.agujero / p.diametro));
    const sRows = Math.round((R * (top - bottom)) / p.resolucion) + 1;
    const sCols = Math.round((2 * Math.PI * R) / p.resolucion);
    const high = R * (1 + Math.sin(-bottom));
    const what = p.forma === "cupula" ? "cúpula" : `esfera con abertura de ${fmt(p.agujero)} mm`;
    $("#summary").textContent = `${what} · Ø ${fmt(p.diametro)} × ${fmt(high)} mm de alto · unos ${fmt((4 * sRows * sCols) / 1e6)} millones de triángulos`;
    if (p.diametro > BED.x || high > BED.z) $("#summary").textContent += " · no cabe en la Ender 3 V3 KE (220 × 220 × 240 mm)";
    return;
  }
  if (p.forma === "plana") {
    const shape = customMask(p) ? `máscara «${maskMeta().nombre}»` : $("#contorno").selectedOptions[0].text.toLowerCase();
    size = `${fmt(W)} × ${fmt(H)} × ${fmt(p.max)} mm${p.contorno !== "rectangulo" ? ` · ${shape}` : ""}`;
    onBed = W <= BED.x && H <= BED.z;
  } else if (p.forma === "arco") {
    const theta = (p.angulo * Math.PI) / 180, R = W / theta;
    const chord = theta >= Math.PI ? 2 * R : 2 * R * Math.sin(theta / 2);
    size = `arco de ${fmt(p.angulo)}° · ${fmt(chord)} mm de ancho × ${fmt(H)} mm de alto`;
    onBed = chord <= BED.x && H <= BED.z;
  } else {
    size = `Ø ${fmt(p.diametro)} × ${fmt(H)} mm de alto`;
    onBed = p.diametro <= BED.x && H <= BED.z;
  }
  $("#summary").textContent = `${size} · unos ${fmt(tris / 1e6)} millones de triángulos`;
  if (!onBed) $("#summary").textContent += " · no cabe de pie en la Ender 3 V3 KE (220 × 220 × 240 mm)";
}

/* ───────── Plantillas: ajustes guardados con un nombre (en la carpeta «datos») ───────── */
let presets = [];
async function loadPresets(selected = "") {
  presets = await (await api("GET", "/api/plantillas")).json();
  const sel = $("#plantilla");
  sel.innerHTML = `<option value="">Plantillas…</option>`;
  for (const t of presets) sel.append(new Option(t.nombre, t.nombre));
  sel.value = selected;
  $("#btnPresetDel").disabled = !selected;
}
$("#plantilla").addEventListener("change", (e) => {
  const t = presets.find((x) => x.nombre === e.target.value);
  $("#btnPresetDel").disabled = !t;
  if (!t) return;
  const { zoom, centro_x, centro_y, ...params } = t.ajustes;
  writeParams({ ...readParams(), ...params });
  showShapeFields();
  queueDraw();
  toast(`Plantilla «${t.nombre}» aplicada.`, "ok");
});
$("#btnPresetSave").addEventListener("click", async () => {
  const name = prompt("Nombre de la plantilla:", $("#plantilla").value || "");
  if (!name?.trim()) return;
  try {
    await api("PUT", `/api/plantillas/${encodeURIComponent(name.trim())}`, readParams());
    await loadPresets(name.trim());
    toast(`Plantilla «${name.trim()}» guardada.`, "ok");
  } catch (e) { toast(e.message, "err"); }
});
$("#btnPresetDel").addEventListener("click", async () => {
  const name = $("#plantilla").value;
  if (!name || !confirm(`¿Borrar la plantilla «${name}»?`)) return;
  try {
    await api("DELETE", `/api/plantillas/${encodeURIComponent(name)}`);
    await loadPresets();
    toast(`Plantilla «${name}» borrada.`, "ok");
  } catch (e) { toast(e.message, "err"); }
});

/* ───────── Caja de luz y soportes (fase 8) ───────── */
const ACC_LABEL = { plana: "Generar caja de luz", arco: "Generar base con luz", cilindro: "Generar base con luz",
  cupula: "Generar base con luz", esfera: "Generar peana con luz" };
function updateAccessoryButton() {
  const forma = $("#forma").value;
  $("#accLabel").textContent = ACC_LABEL[forma];
  $("#btnAcc").disabled = !current;
  $("#btnAcc").title = "Se ajusta a la última litofanía generada con esta imagen y esta forma";
}
async function generateAccessory() {
  const forma = $("#forma").value;
  const btn = $("#btnAcc");
  btn.disabled = true;
  try {
    const info = await (await api("POST", "/api/accesorios", {
      imagen_id: current.id, forma,
      fondo: Number($("#acc_fondo").value), alto: Number($("#acc_alto").value), holgura: Number($("#acc_holgura").value),
    })).json();
    const [w, h, d] = info.medidas_mm.map((n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
    window.Visor.open({
      url: info.vista,
      name: `${info.nombre} · ${current.nombre}`,
      details: `${w} × ${h} × ${d} mm · unos ${info.gramos} g de PLA`,
      download: info.stl,
      settings: info.ajustes,
      mode: "relief",
    });
  } catch (e) {
    toast(e.message, "err");
  } finally {
    updateAccessoryButton();
  }
}
$("#btnAcc").addEventListener("click", generateAccessory);

/* ───────── Generar STL y verlo en 3D ───────── */
async function generate() {
  const p = readParams();
  if (!current || !validParams(p)) return;
  const btn = $("#btnStl");
  btn.disabled = true;
  btn.classList.add("busy");
  const label = btn.lastChild.textContent;
  btn.lastChild.textContent = " Generando…";
  try {
    const info = await (await api("POST", "/api/litofanias", {
      imagen_id: current.id, ...p, mascara_id: customMask(p) ? maskId : null,
      zoom: frame.zoom, centro_x: frame.cx, centro_y: frame.cy,
    })).json();
    const [w, h, d] = info.medidas_mm.map((n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
    const tri = info.triangulos.toLocaleString("es-ES");
    window.Visor.open({
      url: info.vista,
      name: current.nombre,
      details: `${w} × ${h} × ${d} mm · ${tri} triángulos · unos ${info.gramos} g de PLA`,
      download: info.stl,
      settings: info.ajustes,
      radius: info.radio_mm,
      sphere: SPHERE.includes(info.forma),
    });
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.lastChild.textContent = label;
    btn.classList.remove("busy");
    btn.disabled = false;
  }
}

/* ───────── Eventos ───────── */
$("#btnMenu").addEventListener("click", () => {
  if (innerWidth <= 900) document.body.classList.toggle("side-open");
  else document.body.classList.toggle("side-hidden");
});
$("#scrim").addEventListener("click", () => document.body.classList.remove("side-open"));
$("#btnOpen").addEventListener("click", () => $("#file").click());
$("#file").addEventListener("change", (e) => { upload(e.target.files[0]); e.target.value = ""; });
$("#btnReset").addEventListener("click", () => {
  writeParams({ ...readParams(), brillo: 1, contraste: 1, gamma: 1, invertir: false });
  queueDraw();
});
$("#btnStl").addEventListener("click", generate);
$("#btnView").addEventListener("click", () => $("#file3d").click());
$("#file3d").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) window.Visor.open({ file: f, name: f.name }); e.target.value = ""; });
for (const k of PARAMS) $(`#${k}`).addEventListener("input", () => { showSliderValues(); showShapeFields(); queueDraw(); });
source.addEventListener("load", () => setFrame({}, false));
maskImg.addEventListener("load", () => setFrame({}, false));
$("#btnMask").addEventListener("click", () => $("#fileMask").click());
$("#fileMask").addEventListener("change", (e) => { uploadMask(e.target.files[0]); e.target.value = ""; });
$("#zoom").addEventListener("input", () => setFrame({ zoom: Number($("#zoom").value) }));
$("#contorno").addEventListener("change", () => setFrame({}, false));

let dragFrom = null;
const cvFrame = $("#cvFrame");
cvFrame.addEventListener("pointerdown", (e) => {
  if (!current || readParams().forma !== "plana") return;
  dragFrom = { x: e.clientX, y: e.clientY, cx: frame.cx, cy: frame.cy };
  cvFrame.setPointerCapture(e.pointerId);
});
cvFrame.addEventListener("pointermove", (e) => {
  if (!dragFrom) return;
  const win = cropWindow(readParams());
  const k = win.w / (cvFrame.clientWidth * frameGeom.w / frameGeom.total);   // píxeles de foto por píxel de pantalla
  setFrame({
    cx: dragFrom.cx - ((e.clientX - dragFrom.x) * k) / source.naturalWidth,
    cy: dragFrom.cy - ((e.clientY - dragFrom.y) * k) / source.naturalHeight,
  }, false);
});
const endDrag = () => { if (dragFrom) { dragFrom = null; setFrame({}); } };
cvFrame.addEventListener("pointerup", endDrag);
cvFrame.addEventListener("pointercancel", endDrag);
cvFrame.addEventListener("wheel", (e) => {
  if (!current || readParams().forma !== "plana") return;
  e.preventDefault();
  setFrame({ zoom: frame.zoom * Math.exp(-e.deltaY * 0.0015) });
}, { passive: false });
cvFrame.addEventListener("dblclick", () => { if (current) setFrame({ zoom: 1, cx: 0.5, cy: 0.5 }); });

$("#btnQuit").addEventListener("click", async () => {
  try { await api("POST", "/api/apagar", {}); } catch { /* ya se ha cerrado */ }
  $("#closed").hidden = false;
});

let dragDepth = 0;
addEventListener("dragenter", (e) => { if (e.dataTransfer?.types.includes("Files")) { dragDepth++; $("#dropzone").hidden = false; } });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropzone").hidden = true; } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("#dropzone").hidden = true;
  const f = e.dataTransfer.files[0];
  if (f && /\.(stl|3mf)$/i.test(f.name)) window.Visor.open({ file: f, name: f.name });
  else upload(f);
});

/* ───────── Arranque ───────── */
writeParams({ ...DEFAULTS, ...(store.get("params") || {}) });
showShapeFields();
loadMasks().catch((e) => toast(e.message, "err"));
loadPresets().catch((e) => toast(e.message, "err"));
loadImages().then(() => {
  const last = images.find((m) => m.id === store.get("ultima")) || images[0];
  if (last) select(last);
}).catch((e) => toast(e.message, "err"));
