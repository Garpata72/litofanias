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
const PARAMS = ["brillo", "contraste", "gamma", "invertir", "forma", "contorno", "ancho", "angulo", "diametro", "agujero", "ajuste", "cobertura", "min", "max", "resolucion", "marco"];
const DEFAULTS = {
  brillo: 1, contraste: 1, gamma: 1, invertir: false,
  forma: "plana", contorno: "rectangulo", ancho: 150, angulo: 120, diametro: 80, agujero: 40, ajuste: "centrada", cobertura: 150,
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
    p[k] = el.type === "checkbox" ? el.checked : el.tagName === "SELECT" ? el.value : Number(el.value);
  }
  return p;
}
function writeParams(p) {
  for (const k of PARAMS) {
    const el = $(`#${k}`);
    if (el.type === "checkbox") el.checked = !!p[k]; else el.value = p[k];
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
    el.hidden = !el.dataset.shapes.split(" ").includes(forma) || (el.dataset.fit && el.dataset.fit !== ajuste)
      || (el.dataset.contour && el.dataset.contour !== $("#contorno").value);
  });
}
/* Ancho de la imagen ya colocada: el de la plana, la longitud del arco o el perímetro del cilindro. */
const ROUND = ["cilindro", "esfera", "cupula"];
const SPHERE = ["esfera", "cupula"];
const developed = (p) => (ROUND.includes(p.forma) ? Math.PI * p.diametro : p.ancho);

function validParams(p) {
  let ok = true;
  for (const k of ["ancho", "angulo", "diametro", "agujero", "cobertura", "min", "max", "resolucion", "marco"]) {
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

/* ───────── Encuadre ─────────
   Mismo cálculo que crop_window en litofania/heightmap.py: si se cambia uno, cambiar el otro. */
function pieceAspect(p) {
  return customMask(p) && maskMeta() ? maskMeta().ancho / maskMeta().alto : current.ancho / current.alto;
}
function cropWindow(p) {
  const W = source.naturalWidth, H = source.naturalHeight;
  if (p.forma !== "plana") return { x: 0, y: 0, w: W, h: H };
  const a = pieceAspect(p), z = frame.zoom;
  let w, h;
  if (W / H > a) { h = H / z; w = h * a; } else { w = W / z; h = w / a; }
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  return { x: clamp(frame.cx * W - w / 2, 0, W - w), y: clamp(frame.cy * H - h / 2, 0, H - h), w, h };
}
function setFrame(f, save = true) {
  frame = { ...frame, ...f };
  if (source.naturalWidth) {   // deja el centro donde de verdad queda tras no salirse de la foto
    const win = cropWindow(readParams());
    frame.cx = (win.x + win.w / 2) / source.naturalWidth;
    frame.cy = (win.y + win.h / 2) / source.naturalHeight;
  }
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
  const scale = PREVIEW_MAX / Math.max(win.w, win.h);
  const w = Math.max(2, Math.round(win.w * Math.min(scale, flat ? 4 : 1)));
  const h = Math.max(2, Math.round(win.h * Math.min(scale, flat ? 4 : 1)));
  const pad = Math.round((border / inner) * w);
  const padX = wrap ? 0 : pad;
  const mask = cut ? shapeMask(p, h, w) : null;
  const band = cut ? erode(mask, h, w, Math.round((p.marco / Math.max(5, p.ancho)) * w)) : null;
  drawFrame(p, win, w, h, mask, band);

  const cv = $("#cvLit");
  cv.width = w + 2 * padX;
  cv.height = h + 2 * pad;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(source, win.x, win.y, win.w, win.h, padX, pad, w, h);
  const img = ctx.getImageData(padX, pad, w, h);
  const d = img.data;

  const gray = new Float32Array(w * h);
  let sum = 0;
  for (let i = 0, j = 0; j < gray.length; i += 4, j++) {
    const g = Math.min(255, (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) * p.brillo);
    gray[j] = g;
    sum += g;
  }
  const mean = Math.round(sum / gray.length);
  const tMin = Math.exp(-ABSORB * p.min);
  const light = (t) => Math.exp(-ABSORB * t) / tMin;

  for (let i = 0, j = 0; j < gray.length; i += 4, j++) {
    let g = Math.min(255, Math.max(0, mean + (gray[j] - mean) * p.contraste)) / 255;
    if (p.gamma !== 1) g = g ** p.gamma;
    if (p.invertir) g = 1 - g;
    const L = light(p.min + (1 - g) * (p.max - p.min));
    d[i] = 255 * L; d[i + 1] = 222 * L; d[i + 2] = 170 * L; d[i + 3] = 255;
  }
  const edge = light(p.max);
  ctx.fillStyle = `rgb(${255 * edge},${222 * edge},${170 * edge})`;
  ctx.fillRect(0, 0, cv.width, cv.height);
  if (cut) {
    for (let k = 0; k < mask.length; k++) {
      const i = 4 * k;
      if (!mask[k]) d[i + 3] = 0;
      else if (!band[k]) { d[i] = 255 * edge; d[i + 1] = 222 * edge; d[i + 2] = 170 * edge; }
    }
    ctx.clearRect(0, 0, cv.width, cv.height);
  }
  ctx.putImageData(img, padX, pad);
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

/* Primera vista: la foto tal y como entra en la pieza. En la plana se puede arrastrar y hacer zoom;
   lo que queda fuera del contorno se oscurece y la franja del marco se marca en ámbar. */
function drawFrame(p, win, w, h, mask, band) {
  const flat = p.forma === "plana";
  const cv = $("#cvFrame");
  cv.classList.toggle("movable", flat);
  $("#capFrame").textContent = flat ? "Encuadre (arrastra la foto)" : "Original";
  cv.width = w;
  cv.height = h;
  const ctx = cv.getContext("2d");
  ctx.drawImage(source, win.x, win.y, win.w, win.h, 0, 0, w, h);
  if (!mask) return;
  const over = new ImageData(w, h);
  for (let k = 0; k < mask.length; k++) {
    const i = 4 * k;
    if (!mask[k]) { over.data[i] = 16; over.data[i + 1] = 19; over.data[i + 2] = 24; over.data[i + 3] = 215; }
    else if (!band[k]) { over.data[i] = 251; over.data[i + 1] = 191; over.data[i + 2] = 36; over.data[i + 3] = 120; }
  }
  const tmp = document.createElement("canvas");
  tmp.width = w;
  tmp.height = h;
  tmp.getContext("2d").putImageData(over, 0, 0);
  ctx.drawImage(tmp, 0, 0);
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
  const H = (rows - 1) * p.resolucion;
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
      details: `${w} × ${h} × ${d} mm · ${tri} triángulos en el STL`,
      download: info.stl,
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
  const k = win.w / cvFrame.clientWidth;   // píxeles de la foto por píxel de pantalla
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
  setFrame({ zoom: Math.min(4, Math.max(1, frame.zoom * Math.exp(-e.deltaY * 0.0015))) });
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
loadImages().then(() => {
  const last = images.find((m) => m.id === store.get("ultima")) || images[0];
  if (last) select(last);
}).catch((e) => toast(e.message, "err"));
