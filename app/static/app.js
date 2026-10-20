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
const PARAMS = ["brillo", "contraste", "gamma", "invertir", "ancho", "min", "max", "resolucion", "marco"];
const DEFAULTS = { brillo: 1, contraste: 1, gamma: 1, invertir: false, ancho: 150, min: 0.8, max: 3, resolucion: 0.2, marco: 3 };
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(`lito.${k}`)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(`lito.${k}`, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
};

function readParams() {
  const p = {};
  for (const k of PARAMS) {
    const el = $(`#${k}`);
    p[k] = el.type === "checkbox" ? el.checked : Number(el.value);
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
function validParams(p) {
  let ok = true;
  for (const k of ["ancho", "min", "max", "resolucion", "marco"]) {
    const el = $(`#${k}`);
    const bad = !(p[k] >= Number(el.min) && p[k] <= Number(el.max));
    el.classList.toggle("bad", bad);
    ok &&= !bad;
  }
  if (p.min >= p.max) { $("#min").classList.add("bad"); $("#max").classList.add("bad"); ok = false; }
  if (p.ancho <= 2 * p.marco + 5) { $("#marco").classList.add("bad"); ok = false; }
  return ok;
}

/* ───────── Estado ───────── */
let images = [];
let current = null;      // ficha de la imagen abierta
const source = new Image();

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
  $("#imgOrig").src = `/api/imagenes/${meta.id}/archivo`;
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

  const inner = Math.max(5, p.ancho - 2 * p.marco);
  const scale = Math.min(1, PREVIEW_MAX / Math.max(source.naturalWidth, source.naturalHeight));
  const w = Math.max(2, Math.round(source.naturalWidth * scale));
  const h = Math.max(2, Math.round(source.naturalHeight * scale));
  const pad = Math.round((p.marco / inner) * w);

  const cv = $("#cvLit");
  cv.width = w + 2 * pad;
  cv.height = h + 2 * pad;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(source, pad, pad, w, h);
  const img = ctx.getImageData(pad, pad, w, h);
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
  ctx.putImageData(img, pad, pad);
}

function updateSummary(p, ok) {
  if (!current) { $("#summary").textContent = ""; return; }
  if (!ok) { $("#summary").textContent = "Revisa los valores marcados en rojo."; $("#btnStl").disabled = true; return; }
  $("#btnStl").disabled = false;
  const cols = Math.max(2, Math.round((p.ancho - 2 * p.marco) / p.resolucion) + 1);
  const rows = Math.max(2, Math.round((cols * current.alto) / current.ancho));
  const pad = Math.round(p.marco / p.resolucion);
  const C = cols + 2 * pad, R = rows + 2 * pad;
  const tris = 4 * (R - 1) * (C - 1) + 4 * (R + C - 2);
  const fmt = (n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 });
  $("#summary").textContent =
    `${fmt((C - 1) * p.resolucion)} × ${fmt((R - 1) * p.resolucion)} × ${fmt(p.max)} mm · unos ${fmt(tris / 1e6)} millones de triángulos`;
  if ((R - 1) * p.resolucion > 220) $("#summary").textContent += " · más alta que la cama de 220 mm";
}

/* ───────── Generar STL ───────── */
async function generate() {
  const p = readParams();
  if (!current || !validParams(p)) return;
  const btn = $("#btnStl");
  btn.disabled = true;
  btn.classList.add("busy");
  const label = btn.lastChild.textContent;
  btn.lastChild.textContent = " Generando…";
  try {
    const r = await api("POST", "/api/litofanias/plana", { imagen_id: current.id, ...p });
    const blob = await r.blob();
    const name = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(r.headers.get("Content-Disposition") || "")?.[1];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name ? decodeURIComponent(name) : "litofania.stl";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    const tri = Number(r.headers.get("X-Triangulos") || 0).toLocaleString("es-ES");
    toast(`STL listo: ${r.headers.get("X-Medidas-Mm") || ""} mm, ${tri} triángulos.`, "ok");
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
for (const k of PARAMS) $(`#${k}`).addEventListener("input", () => { showSliderValues(); queueDraw(); });
source.addEventListener("load", queueDraw);

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
  upload(e.dataTransfer.files[0]);
});

/* ───────── Arranque ───────── */
writeParams({ ...DEFAULTS, ...(store.get("params") || {}) });
loadImages().then(() => {
  const last = images.find((m) => m.id === store.get("ultima")) || images[0];
  if (last) select(last);
}).catch((e) => toast(e.message, "err"));
