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
const PARAMS = ["brillo", "contraste", "gamma", "invertir", "forma", "contorno", "puntas", "interior", "lados", "base_plana", "colgar", "colgar_ancho", "colgar_agujero", "collage", "collage_filas", "separacion", "diametro_arriba", "ondas", "onda_mm", "agujero_arriba", "cuello", "alto_grados", "ancho", "angulo", "diametro", "agujero", "ajuste", "cobertura", "relieve", "relleno", "textura_mm", "textura_relieve", "textura_invertir", "textura_bn", "texto", "texto_mm", "min", "max", "resolucion", "marco", "voladizo", "caras"];
const DEFAULTS = {
  brillo: 1, contraste: 1, gamma: 1, invertir: false,
  forma: "plana", contorno: "rectangulo", puntas: 5, interior: 50, lados: 6, base_plana: 0,
  colgar: false, colgar_ancho: 14, colgar_agujero: 5, collage: false, collage_filas: 1, separacion: 2,
  diametro_arriba: 60, ondas: 0, onda_mm: 2, agujero_arriba: 0, cuello: 0, alto_grados: 0, ancho: 150, angulo: 120, diametro: 80, agujero: 40, ajuste: "centrada", cobertura: 150, relieve: "dentro", relleno: "liso", textura_mm: 40, textura_relieve: 1, textura_invertir: false, textura_bn: false, texto: "", texto_mm: 8,
  min: 0.8, max: 3, resolucion: 0.2, marco: 3, voladizo: 0, caras: 0,
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
      || (el.dataset.contour && el.dataset.contour !== $("#contorno").value)
      || (el.dataset.fill && el.dataset.fill !== $("#relleno").value);
  });
  $$("[data-text]").forEach((el) => (el.hidden = !$("#texto").value.trim()));
  $$("[data-hang]").forEach((el) => (el.hidden = forma !== "plana" || !$("#colgar").checked));
  $$("[data-waves]").forEach((el) => (el.hidden = !LAMP.includes(forma) || !Number($("#ondas").value)));
  // Accesorios: el aro para casquillo no lleva altura, portapilas ni vela; la peana de escritorio, su inclinación.
  const accTipo = LAMP.includes(forma) ? $("#acc_tipo").value : "base";
  $$("[data-acc]").forEach((el) => { if (el.dataset.acc !== accTipo) el.hidden = true; });
  $$("[data-desk]").forEach((el) => (el.hidden = forma !== "plana" || !$("#acc_escritorio").checked));
  $$("[data-bat]").forEach((el) => { if (!$("#acc_pilas").checked) el.hidden = true; });
  // Caja de caras: se da el ancho de cada cara en vez del diámetro.
  const faces = forma === "cilindro" && Number($("#caras").value) > 0;
  $("#ancho").closest("label").hidden = forma === "cilindro" ? !faces : !["plana", "arco"].includes(forma);
  $("#diametro").closest("label").hidden = !ROUND.includes(forma) || faces;
  $("#anchoLabel").textContent = faces ? "Ancho de cada cara" : "Ancho total";
  $$("[data-waves]").forEach((el) => { if (faces) el.hidden = true; });
  $("#diametroLabel").textContent = forma === "cono" ? "Diámetro de abajo" : "Diámetro exterior";
  $$("[data-collage]").forEach((el) => (el.hidden = !$("#collage").checked));
  updateAccessoryButton();
}
/* Ancho de la imagen ya colocada: el de la plana, la longitud del arco o el perímetro del cilindro. */
const ROUND = ["cilindro", "cono", "esfera", "cupula"];
const LAMP = ["cilindro", "cono"];   // dan la vuelta completa con la foto
/* Diámetro mayor: en el cono, el más ancho de los dos marca el ancho desarrollado de la foto. */
const widest = (p) => (p.forma === "cono" ? Math.max(p.diametro, p.diametro_arriba) : p.diametro);
const SPHERE = ["esfera", "cupula"];
const prism = (p) => p.forma === "cilindro" && p.caras > 0;   // caja de caras planas, una foto en cada una
const developed = (p) => (prism(p) ? p.caras * p.ancho : ROUND.includes(p.forma) ? Math.PI * widest(p) : p.ancho);

function validParams(p) {
  let ok = true;
  for (const k of ["ancho", "angulo", "diametro", "agujero", "cobertura", "textura_mm", "texto_mm", "min", "max", "resolucion", "marco", "voladizo", "caras",
    "puntas", "interior", "lados", "base_plana", "colgar_ancho", "colgar_agujero", "collage_filas", "separacion",
    "diametro_arriba", "ondas", "onda_mm", "agujero_arriba", "cuello", "alto_grados"]) {
    const el = $(`#${k}`);
    const bad = !el.closest("[hidden]") && !(p[k] >= Number(el.min) && p[k] <= Number(el.max));
    el.classList.toggle("bad", bad);
    ok &&= !bad;
  }
  if (p.min >= p.max) { $("#min").classList.add("bad"); $("#max").classList.add("bad"); ok = false; }
  if (prism(p) && (p.caras < 3 || p.ancho <= 2 * p.max + 10)) { $("#caras").classList.add("bad"); ok = false; }
  if (!ROUND.includes(p.forma) && p.ancho <= 2 * p.marco + 5) { $("#marco").classList.add("bad"); ok = false; }
  if (ROUND.includes(p.forma) && !prism(p) && p.diametro <= 2 * p.max + 10) { $("#diametro").classList.add("bad"); ok = false; }
  if (p.forma === "esfera" && p.agujero >= p.diametro - 10) { $("#agujero").classList.add("bad"); ok = false; }
  if (p.forma === "cono" && p.diametro_arriba <= 2 * p.max + 10) { $("#diametro_arriba").classList.add("bad"); ok = false; }
  if (LAMP.includes(p.forma) && p.ondas && p.onda_mm * 4 >= Math.min(p.diametro, p.forma === "cono" ? p.diametro_arriba : p.diametro) / 2) {
    $("#onda_mm").classList.add("bad"); ok = false;
  }
  if (SPHERE.includes(p.forma) && p.agujero_arriba && p.agujero_arriba >= p.diametro - 10) { $("#agujero_arriba").classList.add("bad"); ok = false; }
  if (p.forma === "plana" && p.colgar && p.colgar_agujero > p.colgar_ancho - 4) { $("#colgar_agujero").classList.add("bad"); ok = false; }
  if (needsMask(p) || needsTexture(p)) ok = false;
  if (collageOn(p) && !collageGeom(p).ok) { $("#separacion").classList.add("bad"); ok = false; }
  return ok;
}

/* ───────── Estado ───────── */
let images = [];
let current = null;      // ficha de la imagen abierta
const source = new Image();
/* Foto girada y recortada: es la que usan todas las vistas (el servidor hace lo mismo con girar y recorte). */
const PROC_MAX = 2000;
const src = document.createElement("canvas");
const rotFull = document.createElement("canvas");   // foto entera girada, para el modo recortar
let srcVersion = 0;
let crop = { x: 0, y: 0, w: 1, h: 1, rot: 0 };
let cropMode = false;
function rebuildSource() {
  if (!source.naturalWidth) return;
  const W0 = source.naturalWidth, H0 = source.naturalHeight, side = crop.rot % 180 !== 0;
  const rw = side ? H0 : W0, rh = side ? W0 : H0;
  const k = Math.min(1, PROC_MAX / Math.max(rw, rh));
  rotFull.width = Math.max(1, Math.round(rw * k));
  rotFull.height = Math.max(1, Math.round(rh * k));
  const r = rotFull.getContext("2d");
  r.save();
  r.translate(rotFull.width / 2, rotFull.height / 2);
  r.rotate((crop.rot * Math.PI) / 180);
  r.drawImage(source, (-W0 * k) / 2, (-H0 * k) / 2, W0 * k, H0 * k);
  r.restore();
  const cx = Math.round(crop.x * rotFull.width), cy = Math.round(crop.y * rotFull.height);
  src.width = Math.max(2, Math.round(crop.w * rotFull.width));
  src.height = Math.max(2, Math.round(crop.h * rotFull.height));
  src.getContext("2d").drawImage(rotFull, -cx, -cy);
  srcVersion++;
}
function setCrop(c, save = true) {
  crop = { ...crop, ...c };
  rebuildSource();
  if (save && current) store.set(`recorte.${current.id}`, crop);
  setFrame({}, false);
}
const fullCrop = () => crop.x === 0 && crop.y === 0 && crop.w === 1 && crop.h === 1;
let masks = [];
let maskId = store.get("mascara");
const maskImg = new Image();
let frame = { zoom: 1, cx: 0.5, cy: 0.5 };   // encuadre de la foto en la plana, guardado por imagen

const maskMeta = () => masks.find((m) => m.id === maskId);
const customMask = (p) => p.forma === "plana" && p.contorno === "propia";
const needsMask = (p) => customMask(p) && !maskMeta();

/* Texturas propias para el relleno: la app las guarda en gris. */
let textures = [];
let textureId = store.get("textura");
const textureFill = (p) => p.relleno === "textura" && ["plana", ...SPHERE].includes(p.forma)
  && !(SPHERE.includes(p.forma) && p.ajuste === "panoramica");
const needsTexture = (p) => textureFill(p) && !textures.some((t) => t.id === textureId);

async function loadTextures() {
  textures = await (await api("GET", "/api/texturas")).json();
  const box = $("#textures");
  box.innerHTML = textures.length ? "" : `<div class="none">Todavía no has subido ninguna textura.</div>`;
  for (const t of textures.slice(0, 24)) {
    const b = document.createElement("button");
    b.type = "button";
    b.title = t.nombre;
    b.dataset.id = t.id;
    b.style.backgroundImage = `url(/api/texturas/${t.id}/archivo)`;
    b.classList.toggle("sel", t.id === textureId);
    b.addEventListener("click", () => selectTexture(t.id));
    box.append(b);
  }
  queueDraw();
}
function selectTexture(id) {
  textureId = id;
  store.set("textura", id);
  $$("#textures button").forEach((b) => b.classList.toggle("sel", b.dataset.id === id));
  queueDraw();
}
async function uploadTexture(file) {
  if (!file || !file.type.startsWith("image/")) { toast("Eso no parece una imagen.", "err"); return; }
  const fd = new FormData();
  fd.append("archivo", file);
  try {
    const meta = await (await api("POST", "/api/texturas", fd)).json();
    textureId = meta.id;
    await loadTextures();
    selectTexture(meta.id);
    $("#relleno").value = "textura";
    showShapeFields();
    const small = Math.min(meta.ancho, meta.alto) < 256 ? " Es pequeña: se verá borrosa si el motivo es grande." : "";
    toast(`Textura «${meta.nombre}» lista (${meta.ancho} × ${meta.alto} px, en grises).${small}`, "ok");
  } catch (e) { toast(e.message, "err"); }
}

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

/* ───────── Varias fotos en una pieza (collage) ─────────
   Cada foto guarda su giro, recorte y encuadre como cuando se abre sola; aquí solo se elige cuáles y en qué orden. */
let collageIds = store.get("collage") || [];
const ownCollage = (p) => p.collage && collageIds.length >= 2;
// La caja de caras siempre lleva una foto por cara: las del collage o, sin collage, la abierta repetida.
const collageOn = (p) => ownCollage(p) || (prism(p) && !!current);
const collageList = (p) => (ownCollage(p) ? collageIds : prism(p) && current ? Array(p.caras).fill(current.id) : collageIds);
const photoCache = new Map();   // id → { img, canvas, key }: foto girada y recortada de las que no están abiertas

function saveCollage() {
  store.set("collage", collageIds);
  renderCollage();
  showShapeFields();
  setFrame({}, false);
}
function renderCollage() {
  const box = $("#collageList");
  box.innerHTML = collageIds.length ? "" : `<div class="none">Abre una foto y añádela; hacen falta al menos dos.</div>`;
  collageIds.forEach((id, n) => {
    const m = images.find((x) => x.id === id);
    const b = document.createElement("button");
    b.type = "button";
    b.title = m ? `${n + 1}. ${m.nombre}` : "";
    b.style.backgroundImage = `url(/api/imagenes/${id}/archivo)`;
    b.classList.toggle("sel", current?.id === id);
    b.innerHTML = `<span class="n">${n + 1}</span><span class="x" role="button" aria-label="Quitar del collage" title="Quitar del collage">×</span>`;
    b.addEventListener("click", (e) => {
      if (e.target.classList.contains("x")) { collageIds = collageIds.filter((x) => x !== id); saveCollage(); return; }
      if (m) select(m);
    });
    box.append(b);
  });
  $("#btnCollageAdd").disabled = !current || collageIds.includes(current.id) || collageIds.length >= 8;
}
$("#btnCollageAdd").addEventListener("click", () => {
  if (!current || collageIds.includes(current.id)) return;
  collageIds = [...collageIds, current.id];
  $("#collage").checked = true;
  saveCollage();
});

/* Foto lista para el collage: la abierta es `src`; las demás se giran y recortan aquí con lo guardado. */
function photoCanvas(id) {
  if (id === current?.id && srcVersion) return src;
  const c = { x: 0, y: 0, w: 1, h: 1, rot: 0, ...(store.get(`recorte.${id}`) || {}) };
  const key = JSON.stringify(c);
  let e = photoCache.get(id);
  if (!e) {
    e = { img: new Image(), canvas: null, key: "" };
    e.img.addEventListener("load", () => { e.key = ""; queueDraw(); });
    e.img.src = `/api/imagenes/${id}/archivo`;
    photoCache.set(id, e);
  }
  if (!e.img.complete || !e.img.naturalWidth) return null;
  if (e.key !== key) {
    const W0 = e.img.naturalWidth, H0 = e.img.naturalHeight, side = c.rot % 180 !== 0;
    const k = Math.min(1, 800 / Math.max(W0, H0));
    const rw = Math.round((side ? H0 : W0) * k), rh = Math.round((side ? W0 : H0) * k);
    const cv = document.createElement("canvas");
    cv.width = Math.max(2, Math.round(c.w * rw));
    cv.height = Math.max(2, Math.round(c.h * rh));
    const ctx = cv.getContext("2d");
    ctx.translate(-c.x * rw + rw / 2, -c.y * rh + rh / 2);
    ctx.rotate((c.rot * Math.PI) / 180);
    ctx.drawImage(e.img, (-W0 * k) / 2, (-H0 * k) / 2, W0 * k, H0 * k);
    e.canvas = cv;
    e.key = key;
  }
  return e.canvas;
}
const photoFrame = (id) => (id === current?.id ? frame : { zoom: 1, cx: 0.5, cy: 0.5, ...(store.get(`encuadre.${id}`) || {}) });

/* Mismo reparto que litofania/collage.py (layout): si se cambia uno, cambiar el otro. */
function collageLayout(n, cols, rowsWanted, sep, wrap, aspect, rows = null) {
  const nc = Math.ceil(n / Math.max(1, Math.min(rowsWanted, n)));
  const nr = Math.ceil(n / nc);
  const cw = (cols - (wrap ? nc : nc - 1) * sep) / nc;
  if (rows === null) rows = Math.max(2, Math.round(nr * (cw / aspect) + (nr - 1) * sep));
  const ch = (rows - (nr - 1) * sep) / nr;
  const off = wrap ? (cols - cw) / 2 : 0;
  const slots = [];
  for (let i = 0; i < nr; i++)
    for (let j = 0; j < nc; j++) slots.push({ x: off + j * (cw + sep), y: i * (ch + sep), w: cw, h: ch });
  return { rows, slots, ok: cw >= 2 && ch >= 2 };
}

/* Medidas del collage en milímetros: ancho y alto de la zona de fotos, huecos y proporción de cada hueco. */
function collageGeom(p) {
  const list = collageList(p);
  const first = photoCanvas(list[0]);
  const m0 = images.find((x) => x.id === list[0]);
  const a0 = first ? first.width / first.height : m0 ? m0.ancho / m0.alto : 1;
  const wrap = LAMP.includes(p.forma) || (SPHERE.includes(p.forma) && p.ajuste === "panoramica");
  const cut = p.forma === "plana" && p.contorno !== "rectangulo";
  let W, H = null;
  if (SPHERE.includes(p.forma)) {
    const R = p.diametro / 2;
    W = Math.PI * p.diametro * (wrap ? 1 : p.cobertura / 360);
    if (wrap) H = R * (Math.PI / 2 - (p.forma === "cupula" ? 0 : -Math.acos(Math.min(1, p.agujero / p.diametro))));
  } else W = wrap ? developed(p) : cut ? p.ancho : developed(p) - 2 * p.marco;
  if (customMask(p) && maskMeta()) H = W / (maskMeta().ancho / maskMeta().alto);
  const L = collageLayout(list.length, W, p.forma === "plana" ? p.collage_filas : 1, p.separacion, wrap, a0, H);
  return { W, H: L.rows, slots: L.slots, wrap, ok: L.ok, cellAspect: L.slots[0].w / L.slots[0].h };
}

/* Collage dibujado a `q` píxeles por mm: fotos en sus huecos (transparente donde no hay foto) y los huecos
   en píxeles de la vista previa para pintar la separación. */
function collageComposite(p, q) {
  const g = collageGeom(p);
  const cv = document.createElement("canvas");
  cv.width = Math.max(2, Math.round(g.W * q));
  cv.height = Math.max(2, Math.round(g.H * q));
  const ctx = cv.getContext("2d");
  const rects = g.slots.map((s) => ({ x: s.x * q, y: s.y * q, w: s.w * q, h: s.h * q }));
  collageList(p).forEach((id, n) => {
    const P = photoCanvas(id), r = rects[n];
    if (!P || !r) return;
    const f = photoFrame(id), a = r.w / r.h;
    let w, h;
    if (P.width / P.height > a) { h = P.height / f.zoom; w = h * a; } else { w = P.width / f.zoom; h = w / a; }
    const k = r.w / w, x = f.cx * P.width - w / 2, y = f.cy * P.height - h / 2;
    for (const dx of g.wrap ? [0, -cv.width] : [0]) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(r.x + dx, r.y, r.w, r.h);
      ctx.clip();
      ctx.drawImage(P, r.x + dx - x * k, r.y - y * k, P.width * k, P.height * k);
      ctx.restore();
    }
  });
  return { canvas: cv, rects, wrap: g.wrap };
}
/* 1 donde va foto (o su hueco), 0 en la separación, en una rejilla w × h que cubre el collage. */
function slotMask(col, w, h) {
  const m = new Uint8Array(w * h);
  const k = w / col.canvas.width;
  for (const r of col.rects) {
    const x0 = Math.round(r.x * k), x1 = Math.round((r.x + r.w) * k);
    const y0 = Math.max(0, Math.round(r.y * k)), y1 = Math.min(h, Math.round((r.y + r.h) * k));
    for (let i = y0; i < y1; i++)
      for (let x = x0; x < x1; x++) {
        const j = col.wrap ? ((x % w) + w) % w : x;
        if (j >= 0 && j < w) m[i * w + j] = 1;
      }
  }
  return m;
}

const ZOOM = { min: 0.25, max: 4 };

/* ───────── Encuadre ─────────
   Mismo cálculo que crop_window en litofania/heightmap.py: si se cambia uno, cambiar el otro. El centro
   es el punto de la foto que cae en el centro de la pieza; con zoom menor que 1 la foto es más pequeña que la pieza. */
function pieceAspect(p) {
  return customMask(p) && maskMeta() ? maskMeta().ancho / maskMeta().alto : src.width / src.height;
}
/* En el collage cada foto se encuadra en su hueco (en cualquier forma); si no, solo la plana se encuadra. */
const inCollage = (p) => collageOn(p) && collageIds.includes(current?.id);
const framable = (p) => p.forma === "plana" || inCollage(p);
function cropWindow(p) {
  const W = src.width, H = src.height;
  if (!framable(p)) return { x: 0, y: 0, w: W, h: H };
  const a = inCollage(p) ? collageGeom(p).cellAspect : pieceAspect(p), z = frame.zoom;
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
  collageIds = collageIds.filter((id) => images.some((m) => m.id === id));
  renderCollage();
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
  crop = { x: 0, y: 0, w: 1, h: 1, rot: 0, ...(store.get(`recorte.${meta.id}`) || {}) };
  srcVersion = 0;
  if (cropMode) toggleCrop(false);
  $("#zoom").value = frame.zoom;
  showSliderValues();
  source.src = `/api/imagenes/${meta.id}/archivo`;
  $$("#images button").forEach((b) => b.classList.toggle("sel", b.title === meta.nombre && b.style.backgroundImage.includes(meta.id)));
  renderCollage();
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
function polygonPoints(p) {
  const pts = [];
  if (p.contorno === "estrella") {
    for (let k = 0; k < 2 * p.puntas; k++) {
      const r = k % 2 ? p.interior / 100 : 1, a = Math.PI / 2 + (Math.PI * k) / p.puntas;
      pts.push([r * Math.cos(a), r * Math.sin(a)]);
    }
  } else {
    for (let k = 0; k < p.lados; k++) {
      const a = -Math.PI / 2 + Math.PI / p.lados + (2 * Math.PI * k) / p.lados;
      pts.push([Math.cos(a), Math.sin(a)]);
    }
  }
  return pts;
}
function contourMask(rows, cols, p) {
  const contour = p.contorno;
  const m = new Uint8Array(rows * cols).fill(1);
  if (contour === "rectangulo") return m;
  const aspect = (cols - 1) / (rows - 1);
  let poly = null;
  if (contour === "estrella" || contour === "poligono") {   // centrado y sin deformar, como el círculo
    const pts = polygonPoints(p), xs = pts.map((q) => q[0]), ys = pts.map((q) => q[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const s = Math.min(aspect / ((x1 - x0) / 2), 1 / ((y1 - y0) / 2));
    poly = pts.map(([x, y]) => [(x - (x0 + x1) / 2) * s, (y - (y0 + y1) / 2) * s]);
  }
  const flatBase = p.base_plana / 100;
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
      } else if (poly) {
        const x = u * aspect;
        inside = false;
        for (let a = 0, b = poly.length - 1; a < poly.length; b = a++) {
          const [xi, yi] = poly[a], [xj, yj] = poly[b];
          if (yi !== yj && (yi > v) !== (yj > v) && x < ((xj - xi) * (v - yi)) / (yj - yi) + xi) inside = !inside;
        }
      } else {
        const x = u * 1.16, y = (flatBase + ((v + 1) / 2) * (1 - flatBase)) * 2.27 - 1.02;
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
  if (!current || !source.complete || !source.naturalWidth || !srcVersion) return;

  const flat = p.forma === "plana";
  if (customMask(p) && !(maskImg.complete && maskImg.naturalWidth)) return;   // se redibuja al cargar
  const wrap = LAMP.includes(p.forma);
  const cut = flat && p.contorno !== "rectangulo";   // el marco sigue el contorno
  const border = SPHERE.includes(p.forma) || cut ? 0 : p.marco;
  const inner = Math.max(5, developed(p) - (wrap ? 0 : 2 * border));
  const win = cropWindow(p);
  const col = collageOn(p) ? collageGeom(p) : null;   // varias fotos: la vista a contraluz es el collage entero
  const area = col ? { w: col.W, h: col.H } : win;
  const scale = Math.min(PREVIEW_MAX / Math.max(area.w, area.h), flat && !col ? 4 : Infinity);
  const w = Math.max(2, Math.round(area.w * scale));
  const h = Math.max(2, Math.round(area.h * scale));
  const pad = Math.round((border / inner) * w);
  const padX = wrap ? 0 : pad;
  const mask = cut ? shapeMask(p, h, w) : null;
  const band = cut ? erode(mask, h, w, Math.round((p.marco / Math.max(5, p.ancho)) * w)) : null;
  const fill = flat ? fillLayer(p, w, h, (cut ? Math.max(5, p.ancho) : inner) / w) : null;
  if (!col) drawFrame(p, win, w, h, mask, band, fill);
  else {   // la foto abierta, en la proporción de su hueco del collage
    const fs = Math.min(PREVIEW_MAX / Math.max(win.w, win.h), 4);
    drawFrame(p, win, Math.max(2, Math.round(win.w * fs)), Math.max(2, Math.round(win.h * fs)), null, null, null);
  }

  // Capa de la foto (transparente donde no llega) y gris del relleno debajo.
  const k = w / win.w;
  const layer = document.createElement("canvas");
  layer.width = w;
  layer.height = h;
  const lctx = layer.getContext("2d", { willReadFrequently: true });
  const comp = col ? collageComposite(p, w / col.W) : null;
  if (comp) lctx.drawImage(comp.canvas, 0, 0, w, h);
  else lctx.drawImage(src, -win.x * k, -win.y * k, src.width * k, src.height * k);
  const d = lctx.getImageData(0, 0, w, h).data;
  const bg = fill ? fillGray(fill, w, h) : null;

  // El servidor aplica el contraste a cada foto con su propia media; aquí, para abreviar, con la del collage.
  const mean = comp ? sourceMean(p.brillo, comp.canvas, -1) : sourceMean(p.brillo);
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
  if (comp) {   // separación entre las fotos, a grosor máximo
    const sm = slotMask(comp, w, h);
    for (let j = 0; j < sm.length; j++) if (!sm[j]) { const i = 4 * j; o[i] = 255 * edge; o[i + 1] = 222 * edge; o[i + 2] = 170 * edge; }
  }
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
  if (flat && p.colgar) drawTab(cv, p, pxPerMm, mask, lit(p.max));
}

/* Pestaña para colgar, como contours.add_tab: círculo con agujero encima y un vástago que entra en la pieza. */
function drawTab(cv, p, pxmm, mask, color) {
  const R = (p.colgar_ancho / 2) * pxmm, r = (p.colgar_agujero / 2) * pxmm, extra = Math.ceil(2 * R) + 1;
  const old = document.createElement("canvas");
  old.width = cv.width;
  old.height = cv.height;
  old.getContext("2d").drawImage(cv, 0, 0);
  cv.height += extra;
  const ctx = cv.getContext("2d");
  ctx.drawImage(old, 0, extra);
  const c = cv.width / 2, cy = R + 0.5;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(c, cy, R, 0, 2 * Math.PI);
  ctx.fill();
  for (let x = Math.max(0, Math.floor(c - R)); x <= Math.min(cv.width - 1, Math.ceil(c + R)); x++) {
    let first = 0;
    if (mask) { const W = cv.width, H = mask.length / W; while (first < H && !mask[first * W + x]) first++; }
    ctx.fillRect(x, cy, 1, extra + first + 2 - cy);
  }
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(c, cy, r, 0, 2 * Math.PI);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
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
function sourceMean(brillo, img = src, version = srcVersion) {
  if (statsFor !== version || version < 0) {
    const c = document.createElement("canvas");
    const s = Math.min(1, 128 / Math.max(img.width, img.height));
    c.width = Math.max(1, Math.round(img.width * s));
    c.height = Math.max(1, Math.round(img.height * s));
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, c.width, c.height);
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    const gray = [];
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 127) gray.push(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
    statsGray = gray.length ? Float32Array.from(gray) : new Float32Array([128]);
    statsFor = version;
  }
  let sum = 0;
  for (const g of statsGray) sum += Math.min(255, g * brillo);
  return Math.round(sum / statsGray.length);
}

/* Relleno de lo que la foto no tapa: liso (gris fijo) o la luna que genera el servidor, la misma del STL. */
const PLAIN = 0.85;   // como textures.PLAIN
const fillImg = new Image();
fillImg.addEventListener("load", () => queueDraw());
function fillLayer(p, w, h, mmPx) {
  if (p.relleno === "liso" || (p.relleno === "textura" && needsTexture(p))) return { kind: "liso" };
  const q = new URLSearchParams({ relleno: p.relleno, ancho: w, alto: h, mm_px: mmPx.toFixed(4) });
  if (p.relleno === "textura") {
    q.set("textura_id", textureId);
    for (const k of ["textura_mm", "textura_relieve", "textura_invertir", "textura_bn"]) q.set(k, p[k]);
  }
  const url = `/api/relleno.png?${q}`;
  if (!fillImg.src.endsWith(url)) fillImg.src = url;
  return fillImg.complete && fillImg.naturalWidth === w && fillImg.naturalHeight === h && fillImg.src.endsWith(url)
    ? { kind: "img", img: fillImg } : { kind: "liso" };
}
function fillGray(fill, w, h) {
  const g = new Float32Array(w * h);
  if (fill.kind !== "img") return g.fill(PLAIN);
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
  if (!customMask(p)) return contourMask(rows, cols, p);
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

/* Modo recortar: la foto entera (girada) con el rectángulo del recorte; se mueve arrastrando dentro y se
   cambia de tamaño desde las esquinas. */
const CROP_VIEW = 640;
let cropGeom = { k: 1 };
function drawCrop() {
  const cv = $("#cvFrame");
  const k = CROP_VIEW / Math.max(rotFull.width, rotFull.height);
  const w = Math.round(rotFull.width * k), h = Math.round(rotFull.height * k);
  cv.width = w;
  cv.height = h;
  cropGeom = { w, h };
  cv.classList.add("movable");
  $("#capFrame").textContent = "Recortar (arrastra el recuadro o sus esquinas)";
  const ctx = cv.getContext("2d");
  ctx.drawImage(rotFull, 0, 0, w, h);
  const x = crop.x * w, y = crop.y * h, cw = crop.w * w, ch = crop.h * h;
  ctx.fillStyle = "rgba(14, 17, 22, 0.7)";
  ctx.fillRect(0, 0, w, y);
  ctx.fillRect(0, y + ch, w, h - y - ch);
  ctx.fillRect(0, y, x, ch);
  ctx.fillRect(x + cw, y, w - x - cw, ch);
  ctx.strokeStyle = "#fbbf24";
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, cw, ch);
  ctx.fillStyle = "#fbbf24";
  for (const [hx, hy] of [[x, y], [x + cw, y], [x, y + ch], [x + cw, y + ch]]) ctx.fillRect(hx - 6, hy - 6, 12, 12);
}

/* Primera vista: la pieza con la foto colocada y un margen alrededor donde se ve, atenuada, la parte de la
   foto que se queda fuera. En la plana se arrastra y se hace zoom; lo que queda fuera del contorno se
   oscurece y la franja del marco se marca en ámbar. */
let frameGeom = { w: 1, total: 1 };
function drawFrame(p, win, w, h, mask, band, fill) {
  if (cropMode) { drawCrop(); return; }
  const flat = framable(p);
  const cv = $("#cvFrame");
  cv.classList.toggle("movable", flat);
  $("#capFrame").textContent = inCollage(p) ? `Foto ${collageIds.indexOf(current.id) + 1} del collage (arrastra para encuadrarla)`
    : flat ? "Encuadre (arrastra la foto)" : fullCrop() && !crop.rot ? "Original" : "Foto recortada";
  const M = flat ? Math.round(0.2 * Math.max(w, h)) : 0;
  cv.width = w + 2 * M;
  cv.height = h + 2 * M;
  frameGeom = { w, total: w + 2 * M };
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#0e1116";
  ctx.fillRect(0, 0, cv.width, cv.height);
  if (fill) {
    if (fill.kind === "img") ctx.drawImage(fill.img, M, M, w, h);
    else { ctx.fillStyle = `rgb(${255 * PLAIN},${255 * PLAIN},${255 * PLAIN})`; ctx.fillRect(M, M, w, h); }
  }
  const k = w / win.w;
  ctx.drawImage(src, M - win.x * k, M - win.y * k, src.width * k, src.height * k);
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
  updateSummaryText(p, ok);
  if (current && ok && p.collage) $("#summary").textContent += collageOn(p) ? ` · collage de ${collageIds.length} fotos`
    : " · añade al menos dos fotos al collage (ahora va solo esta)";
}
function updateSummaryText(p, ok) {
  if (!current) { $("#summary").textContent = ""; return; }
  if (!ok) { $("#summary").textContent = needsMask(p) ? "Sube o elige una máscara para el contorno propio."
    : needsTexture(p) ? "Sube o elige una textura para el relleno." : "Revisa los valores marcados en rojo."; $("#btnStl").disabled = true; return; }
  $("#btnStl").disabled = false;
  const wrap = LAMP.includes(p.forma);
  const W = developed(p);
  const pad = Math.round(p.marco / p.resolucion);
  const cols = wrap ? Math.round(W / p.resolucion) : Math.max(2, Math.round((W - 2 * p.marco) / p.resolucion) + 1) + 2 * pad;
  const imgCols = wrap ? cols : cols - 2 * pad;
  const aspect = collageOn(p) ? (() => { const g = collageGeom(p); return g.W / g.H; })()
    : p.forma === "plana" ? pieceAspect(p) : src.width / src.height;
  const rows = Math.max(2, Math.round(imgCols / aspect)) + 2 * pad;
  const textBand = p.texto.trim() && !(p.forma === "plana" && p.contorno !== "rectangulo") ? p.texto_mm * (1 + 2 * TEXT_MARGIN) : 0;
  const tab = p.forma === "plana" && p.colgar ? (Math.ceil(p.colgar_ancho / p.resolucion) + 1) * p.resolucion : 0;
  const H = (rows - 1) * p.resolucion + textBand + tab;
  const tris = 4 * rows * cols;
  const fmt = (n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 });

  let size, onBed;
  if (SPHERE.includes(p.forma)) {
    const R = p.diametro / 2;
    let top = Math.PI / 2 - p.resolucion / R;
    if (p.agujero_arriba) top = Math.min(top, Math.acos(Math.min(1, p.agujero_arriba / p.diametro)));
    const bottom = p.forma === "cupula" ? 0 : -Math.acos(Math.min(1, p.agujero / p.diametro));
    const neck = p.forma === "esfera" ? p.cuello : 0;
    const sRows = Math.round((R * (top - bottom)) / p.resolucion) + 1 + Math.ceil(neck / p.resolucion);
    const sCols = Math.round((2 * Math.PI * R) / p.resolucion);
    const high = R * (Math.sin(top) + Math.sin(-bottom)) + neck;
    const what = (p.forma === "cupula" ? "cúpula" : `esfera con abertura de ${fmt(p.agujero)} mm`)
      + (neck ? ` y cuello de ${fmt(neck)} mm` : "") + (p.agujero_arriba ? ` · agujero arriba de ${fmt(p.agujero_arriba)} mm` : "");
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
  } else if (prism(p)) {
    const across = p.ancho / Math.sin(Math.PI / p.caras);   // de esquina a esquina
    size = `caja de ${p.caras} caras de ${fmt(p.ancho)} mm × ${fmt(H)} mm de alto`;
    onBed = across <= BED.x && H <= BED.z;
    if (ownCollage(p) && collageIds.length !== p.caras) size += ` · ¡pon ${p.caras} fotos, una por cara! (hay ${collageIds.length})`;
  } else if (p.forma === "cono") {
    const dr = Math.abs(p.diametro - p.diametro_arriba) / 2;
    if (H <= dr * 1.05) {
      $("#summary").textContent = "La lámpara es demasiado baja para tanta diferencia de diámetros: usa una foto más alta o diámetros más parecidos.";
      $("#btnStl").disabled = true;
      return;
    }
    const high = Math.sqrt(H * H - dr * dr);
    size = `lámpara cónica · Ø ${fmt(p.diametro)} abajo y Ø ${fmt(p.diametro_arriba)} arriba × ${fmt(high)} mm de alto`;
    onBed = widest(p) + 2 * (p.ondas ? p.onda_mm : 0) <= BED.x && high <= BED.z;
  } else {
    size = `Ø ${fmt(p.diametro)} × ${fmt(H)} mm de alto`;
    onBed = p.diametro + 2 * (p.ondas ? p.onda_mm : 0) <= BED.x && H <= BED.z;
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
  cono: "Generar base con luz", cupula: "Generar base con luz", esfera: "Generar peana con luz" };
function updateAccessoryButton() {
  const forma = $("#forma").value;
  $("#accLabel").textContent = LAMP.includes(forma) && $("#acc_tipo").value === "casquillo" ? "Generar aro para casquillo"
    : forma === "plana" && $("#acc_escritorio").checked ? "Generar caja y peana" : ACC_LABEL[forma];
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
      fondo: Number($("#acc_fondo").value), alto: Number($("#acc_alto").value), holgura: Number($("#acc_holgura").value), holgura_marco: Number($("#acc_holgura_marco").value),
      tipo: $("#acc_tipo").value, casquillo: Number($("#acc_casquillo").value),
      montaje: $("#acc_montaje").value, escritorio: $("#acc_escritorio").checked, inclinacion: Number($("#acc_inclinacion").value),
      pilas: $("#acc_pilas").checked, pilas_largo: Number($("#acc_pilas_largo").value),
      pilas_ancho: Number($("#acc_pilas_ancho").value), pilas_alto: Number($("#acc_pilas_alto").value),
      vela: $("#acc_vela").checked,
    })).json();
    const [w, h, d] = info.medidas_mm.map((n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
    window.Visor.open({
      url: info.vista,
      name: `${info.nombre} · ${current.nombre}`,
      details: `${w} × ${h} × ${d} mm · unos ${info.gramos} g de PLA${info.piezas > 1 ? ` · ${info.piezas} piezas` : ""}`,
      download: info.stl,
      download3mf: info.tresmf,
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
for (const id of ["#acc_tipo", "#acc_escritorio", "#acc_pilas"]) $(id).addEventListener("input", showShapeFields);

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
      imagen_id: current.id, ...p, mascara_id: customMask(p) ? maskId : null, textura_id: textureFill(p) ? textureId : null,
      collage: collageOn(p) ? collageList(p).map((id) => {
        const c = id === current.id ? crop : { x: 0, y: 0, w: 1, h: 1, rot: 0, ...(store.get(`recorte.${id}`) || {}) };
        const f = photoFrame(id), full = c.x === 0 && c.y === 0 && c.w === 1 && c.h === 1;
        return { imagen_id: id, girar: c.rot, recorte: full ? null : [c.x, c.y, c.w, c.h], zoom: f.zoom, centro_x: f.cx, centro_y: f.cy };
      }) : [],
      zoom: frame.zoom, centro_x: frame.cx, centro_y: frame.cy,
      girar: crop.rot, recorte: fullCrop() ? null : [crop.x, crop.y, crop.w, crop.h],
    })).json();
    const [w, h, d] = info.medidas_mm.map((n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
    const tri = info.triangulos.toLocaleString("es-ES");
    window.Visor.open({
      url: info.vista,
      name: current.nombre,
      details: `${w} × ${h} × ${d} mm · ${tri} triángulos · unos ${info.gramos} g de PLA`,
      download: info.stl,
      download3mf: info.tresmf,
      settings: info.ajustes,
      radius: info.radio_mm,
      sphere: SPHERE.includes(info.forma),
      rIn: info.relieve_fuera ? info.radio_mm * (info.caras ? Math.cos(Math.PI / info.caras) : 1) - (info.conico?.pared_mm ?? info.grosor_mm[1]) : 0,
      lamp: info.conico,
      sides: info.caras,
      tMax: info.grosor_mm[1],
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
source.addEventListener("load", () => setCrop({}, false));
maskImg.addEventListener("load", () => setFrame({}, false));
$("#btnMask").addEventListener("click", () => $("#fileMask").click());
$("#fileMask").addEventListener("change", (e) => { uploadMask(e.target.files[0]); e.target.value = ""; });
$("#zoom").addEventListener("input", () => setFrame({ zoom: Number($("#zoom").value) }));
$("#contorno").addEventListener("change", () => setFrame({}, false));

let dragFrom = null;
const cvFrame = $("#cvFrame");
let cropDrag = null;
function cropPoint(e) {   // posición del puntero en fracciones de la foto girada
  const r = cvFrame.getBoundingClientRect();
  return { u: (e.clientX - r.left) / r.width, v: (e.clientY - r.top) / r.height, px: 14 / r.width, py: 14 / r.height };
}
cvFrame.addEventListener("pointerdown", (e) => {
  if (current && cropMode) {
    const { u, v, px, py } = cropPoint(e);
    const near = (a, b, t) => Math.abs(a - b) < t;
    const cx = near(u, crop.x, px) ? "l" : near(u, crop.x + crop.w, px) ? "r" : "";
    const cy = near(v, crop.y, py) ? "t" : near(v, crop.y + crop.h, py) ? "b" : "";
    const inside = u > crop.x && u < crop.x + crop.w && v > crop.y && v < crop.y + crop.h;
    if ((cx && cy) || inside) {
      cropDrag = { u, v, corner: cx && cy ? cx + cy : "", start: { ...crop } };
      cvFrame.setPointerCapture(e.pointerId);
    }
    return;
  }
  if (!current || !framable(readParams())) return;
  dragFrom = { x: e.clientX, y: e.clientY, cx: frame.cx, cy: frame.cy };
  cvFrame.setPointerCapture(e.pointerId);
});
cvFrame.addEventListener("pointermove", (e) => {
  if (cropDrag) {
    const { u, v } = cropPoint(e);
    const s = cropDrag.start, du = u - cropDrag.u, dv = v - cropDrag.v, MIN = 0.05;
    const clamp = (a, lo, hi) => Math.min(hi, Math.max(lo, a));
    let { x, y, w, h } = s;
    if (!cropDrag.corner) {
      x = clamp(s.x + du, 0, 1 - s.w);
      y = clamp(s.y + dv, 0, 1 - s.h);
    } else {
      if (cropDrag.corner.includes("l")) { x = clamp(s.x + du, 0, s.x + s.w - MIN); w = s.x + s.w - x; }
      if (cropDrag.corner.includes("r")) w = clamp(s.w + du, MIN, 1 - s.x);
      if (cropDrag.corner.includes("t")) { y = clamp(s.y + dv, 0, s.y + s.h - MIN); h = s.y + s.h - y; }
      if (cropDrag.corner.includes("b")) h = clamp(s.h + dv, MIN, 1 - s.y);
    }
    crop = { ...crop, x, y, w, h };
    drawCrop();
    return;
  }
  if (!dragFrom) return;
  const win = cropWindow(readParams());
  const k = win.w / (cvFrame.clientWidth * frameGeom.w / frameGeom.total);   // píxeles de foto por píxel de pantalla
  setFrame({
    cx: dragFrom.cx - ((e.clientX - dragFrom.x) * k) / src.width,
    cy: dragFrom.cy - ((e.clientY - dragFrom.y) * k) / src.height,
  }, false);
});
const endDrag = () => {
  if (cropDrag) { cropDrag = null; setCrop({}); }
  if (dragFrom) { dragFrom = null; setFrame({}); }
};
cvFrame.addEventListener("pointerup", endDrag);
cvFrame.addEventListener("pointercancel", endDrag);
cvFrame.addEventListener("wheel", (e) => {
  if (!current || cropMode || !framable(readParams())) return;
  e.preventDefault();
  setFrame({ zoom: frame.zoom * Math.exp(-e.deltaY * 0.0015) });
}, { passive: false });
cvFrame.addEventListener("dblclick", () => {
  if (!current) return;
  if (cropMode) setCrop({ x: 0, y: 0, w: 1, h: 1 });
  else setFrame({ zoom: 1, cx: 0.5, cy: 0.5 });
});

function toggleCrop(on = !cropMode) {
  cropMode = on;
  $("#btnCrop").setAttribute("aria-pressed", on);
  $("#btnCrop").textContent = on ? "Listo" : "Recortar";
  queueDraw();
}
function rotate(delta) {
  // El recorte se gira con la foto para que siga enmarcando lo mismo.
  const { x, y, w, h } = crop;
  const r = delta > 0 ? { x: 1 - y - h, y: x, w: h, h: w } : { x: y, y: 1 - x - w, w: h, h: w };
  setCrop({ ...r, rot: (crop.rot + delta + 360) % 360 });
}
$("#btnCrop").addEventListener("click", () => current && toggleCrop());
$("#btnRotL").addEventListener("click", () => current && rotate(-90));
$("#btnRotR").addEventListener("click", () => current && rotate(90));

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
loadTextures().catch((e) => toast(e.message, "err"));
$("#btnTex").addEventListener("click", () => $("#fileTex").click());
$("#fileTex").addEventListener("change", (e) => { uploadTexture(e.target.files[0]); e.target.value = ""; });
loadPresets().catch((e) => toast(e.message, "err"));
loadImages().then(() => {
  const last = images.find((m) => m.id === store.get("ultima")) || images[0];
  if (last) select(last);
}).catch((e) => toast(e.message, "err"));
