/* Multicolor: foto en relieve de colores (tipo HueForge) y posavasos, para un solo extrusor con cambios M600.
   La vista previa de la foto se calcula aquí mismo, al momento, con el mismo modelo que el servidor
   (litofania/multicolor.py): cada filamento tapa min(1, grosor/TD) del color de debajo. Las capas de cambio
   que salen aquí son las que se mandan al generar, así que la pieza es la de la vista previa.
   Usa $, $$, api, toast, store, current, src, crop e icon de app.js. */
const Color = (() => {
  const MAX_FILS = 4;
  const LIBRARY = [   // PLA, TD aproximados: mídelos o usa los de HueForge para tus bobinas
    ["negro", "#1b1b1b", 0.5], ["gris oscuro", "#4a4a4a", 0.9], ["gris", "#8c8c8c", 1.2], ["marrón", "#a0602e", 1.6],
    ["rojo", "#c0262d", 1.8], ["naranja", "#e8762b", 2.4], ["amarillo", "#f2c14e", 3.5], ["verde", "#2e8b57", 1.5],
    ["azul", "#1f4e9c", 1.2], ["azul cielo", "#6fa8dc", 2.5], ["carne", "#e8b894", 3.0], ["blanco", "#f2eee4", 3.0],
  ];
  const DEF_FILS = [["negro", "#1b1b1b", 0.5], ["marrón", "#a0602e", 1.6], ["blanco", "#f2eee4", 3.0]];
  const FIELDS = ["c_ancho", "c_contorno", "c_borde", "c_borde_alto", "c_peso", "c_capas", "c_contraste", "c_auto", "c_capa", "c_primera", "c_base", "c_resolucion",
    "p_forma", "p_tamano", "p_esquinas", "p_modo", "p_pasada", "p_colores", "p_motivo", "p_texto2", "p_texto3", "p_texto_mm", "p_mascara2", "p_mascara3", "p_motivo_mm", "p_ajuste", "p_giro", "p_dx", "p_dy",
    "p_grosor", "p_margen", "p_alto2", "p_alto3", "p_borde", "p_borde_alto", "p_incrustacion"];
  let on = false, tipo = "foto";
  let fils = DEF_FILS.map(([nombre, color, td]) => ({ nombre, color, td }));
  let pal = [{ nombre: "fondo", color: "#2b3a55" }, { nombre: "motivo", color: "#f2c14e" }, { nombre: "detalle", color: "#e4572e" }];
  let starts = null;          // capas de cambio (sin la del primer filamento), de la vista previa o puestas a mano
  let shade = true, resin = false;
  let pix = null;             // la foto a la resolución de la vista previa: { w, h, lab, key }
  let lastKey = "", startsKey = "";
  let coasterGeo = null, coasterTimer = null, timer = null, masks = [];
  let svgs = [], svgMaps = {};   // SVG subidos y, por cada uno, qué color del SVG va a qué color del posavasos

  const read = (id) => { const e = $(`#${id}`); return e.type === "checkbox" ? e.checked : e.type === "range" || e.type === "number" ? Number(e.value) : e.value; };
  function save() {
    store.set("color1", { campos: Object.fromEntries(FIELDS.map((id) => [id, read(id)])), fils, pal, tipo, starts, shade, resin, svgMaps });
  }
  function restore() {
    const s = store.get("color1");
    if (!s) return;
    for (const [id, v] of Object.entries(s.campos || {})) {
      const e = $(`#${id}`); if (!e) continue;
      if (e.type === "checkbox") e.checked = !!v; else e.value = v;
    }
    if (Array.isArray(s.fils) && s.fils.length >= 2) fils = s.fils.slice(0, MAX_FILS);
    if (Array.isArray(s.pal) && s.pal.length === 3) pal = s.pal;
    tipo = s.tipo === "posavasos" ? "posavasos" : "foto";
    svgMaps = s.svgMaps || {};
    starts = Array.isArray(s.starts) ? s.starts : null;
    shade = s.shade !== false; resin = !!s.resin;
  }

  /* ───────── Color: sRGB → Lab, igual que el servidor ───────── */
  const lin = (c) => (c > 0.04045 ? ((c + 0.055) / 1.055) ** 2.4 : c / 12.92);
  const fx = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  function lab(r, g, b, w, out, o) {
    r = lin(r); g = lin(g); b = lin(b);
    const x = fx((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.9505);
    const y = fx(0.2126 * r + 0.7152 * g + 0.0722 * b);
    const z = fx((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.089);
    out[o] = 116 * y - 16; out[o + 1] = w * 500 * (x - y); out[o + 2] = w * 200 * (y - z);
  }
  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const rgbHex = (c) => "#" + c.map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0")).join("");
  const luma = (h) => { const [r, g, b] = hexRgb(h); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };

  /* Color visto desde arriba con 0..n capas sobre la base; st[i] = primera capa del filamento i (st[0] = 0). */
  function stackColors(st, n, h) {
    const rgb = fils.map((f) => hexRgb(f.color));
    const out = [];
    for (let k = 0; k <= n; k++) {
      let c = rgb[0].slice();
      for (let i = 1; i < fils.length; i++) {
        const end = i + 1 < fils.length ? st[i + 1] - 1 : n;
        const t = (Math.min(k, end) - st[i] + 1) * h;
        if (t > 0) { const o = Math.min(1, t / Math.max(0.01, fils[i].td)); c = c.map((v, j) => v * (1 - o) + rgb[i][j] * o); }
      }
      out.push(c);
    }
    return out;
  }
  function stackLab(st, n, h, w) {
    const s = stackColors(st, n, h), out = new Float64Array(s.length * 3);
    s.forEach((c, k) => lab(c[0], c[1], c[2], w, out, 3 * k));
    return out;
  }
  function errorOf(sample, weights, st, n, h, w) {
    const L = stackLab(st, n, h, w), m = n + 1;
    let e = 0, tw = 0;
    for (let i = 0; i < weights.length; i++) {
      const a = sample[3 * i], b = sample[3 * i + 1], c = sample[3 * i + 2];
      let best = Infinity;
      for (let k = 0; k < m; k++) {
        const d0 = a - L[3 * k], d1 = b - L[3 * k + 1], d2 = c - L[3 * k + 2];
        const d = d0 * d0 + d1 * d1 + d2 * d2;
        if (d < best) best = d;
      }
      e += best * weights[i]; tw += weights[i];
    }
    return e / tw;
  }
  function comb(n, k) { let r = 1; for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i; return r; }
  /* Las capas de cambio que mejor reproducen la foto: todas las combinaciones si son pocas; si no, cada
     cambio por turnos a su mejor sitio (como choose_starts del servidor). */
  function chooseStarts(sample, weights, n, h, w) {
    const k = fils.length - 1;
    const err = (cuts) => errorOf(sample, weights, [0, ...cuts], n, h, w);
    if (comb(n, k) <= 3000) {
      let best = null, be = Infinity;
      const rec = (from, acc) => {
        if (acc.length === k) { const e = err(acc); if (e < be) { be = e; best = acc.slice(); } return; }
        for (let c = from; c <= n - (k - acc.length - 1); c++) { acc.push(c); rec(c + 1, acc); acc.pop(); }
      };
      rec(1, []);
      return best;
    }
    let best = null, be = Infinity;
    for (const spread of [0.5, 0.75, 1]) {
      let cuts = Array.from({ length: k }, (_, i) => Math.max(1, Math.round(((i + 1) * spread * n) / (k + 1))));
      cuts = [...new Set(cuts.map((c, j) => Math.min(n, c + j)))].sort((a, b) => a - b);
      while (cuts.length < k) cuts.push(cuts[cuts.length - 1] + 1);
      let e = err(cuts);
      for (let round = 0; round < 12; round++) {
        let moved = false;
        for (let i = 0; i < k; i++) {
          const lo = i ? cuts[i - 1] + 1 : 1, hi = i + 1 < k ? cuts[i + 1] - 1 : n;
          for (let c = lo; c <= hi; c++) {
            if (c === cuts[i]) continue;
            const t = cuts.slice(); t[i] = c;
            const te = err(t);
            if (te < e - 1e-9) { cuts = t; e = te; moved = true; }
          }
        }
        if (!moved) break;
      }
      if (e < be) { be = e; best = cuts; }
    }
    return best;
  }

  /* ───────── La foto a la resolución de la vista previa ───────── */
  const PREVIEW_W = 300;
  function photoPixels(w8) {
    if (!src.width) return null;
    const cols = Math.max(8, Math.min(PREVIEW_W, Math.round(read("c_ancho") / read("c_resolucion")) + 1));
    const rows = Math.max(8, Math.round((cols * src.height) / src.width));
    const key = `${srcVersion}|${cols}|${read("c_contraste")}|${w8}`;
    if (pix && pix.key === key) return pix;
    const cv = document.createElement("canvas");
    cv.width = cols; cv.height = rows;
    const c = cv.getContext("2d", { willReadFrequently: true });
    c.imageSmoothingQuality = "high";
    c.drawImage(src, 0, 0, cols, rows);
    const d = c.getImageData(0, 0, cols, rows).data;
    let lo = [0, 0, 0], hi = [255, 255, 255];
    if (read("c_contraste")) {   // autocontraste por canal, con un 1 % de corte (como PIL)
      for (let ch = 0; ch < 3; ch++) {
        const hist = new Uint32Array(256);
        for (let i = ch; i < d.length; i += 4) hist[d[i]]++;
        const cut = (rows * cols) * 0.01;
        let a = 0, s = 0; while (a < 255 && s + hist[a] <= cut) s += hist[a++];
        let b = 255; s = 0; while (b > 0 && s + hist[b] <= cut) s += hist[b--];
        if (b > a) { lo[ch] = a; hi[ch] = b; }
      }
    }
    const L = new Float64Array(rows * cols * 3);
    for (let i = 0, p = 0; i < d.length; i += 4, p += 3) {
      const ch = (v, j) => Math.min(1, Math.max(0, (v - lo[j]) / (hi[j] - lo[j])));
      lab(ch(d[i], 0), ch(d[i + 1], 1), ch(d[i + 2], 2), w8, L, p);
    }
    pix = { w: cols, h: rows, lab: L, key };
    return pix;
  }

  /* Máscara de la forma, en la rejilla de la vista previa (dibujada con el mismo criterio que el servidor). */
  function shapeMask(w, h) {
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
    const c = cv.getContext("2d");
    c.fillStyle = "#fff";
    const f = read("c_contorno");
    c.beginPath();
    if (f === "rectangulo") c.rect(0, 0, w, h);
    else if (f === "ovalo") c.ellipse(w / 2, h / 2, w / 2, h / 2, 0, 0, 2 * Math.PI);
    else if (f === "circulo") c.arc(w / 2, h / 2, Math.min(w, h) / 2, 0, 2 * Math.PI);
    else if (f === "redondeado") c.roundRect(0, 0, w, h, 0.15 * Math.min(w, h));
    else {
      const n = f === "triangulo" ? 3 : 6, a0 = -Math.PI / 2 - Math.PI / n;
      const pts = Array.from({ length: n }, (_, i) => [Math.cos(a0 + (2 * Math.PI * i) / n), -Math.sin(a0 + (2 * Math.PI * i) / n)]);
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const s = Math.min(w / (Math.max(...xs) - Math.min(...xs)), h / (Math.max(...ys) - Math.min(...ys)));
      const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
      pts.forEach(([x, y], i) => c[i ? "lineTo" : "moveTo"](w / 2 + (x - cx) * s, h / 2 + (y - cy) * s));
      c.closePath();
    }
    c.fill();
    const d = c.getImageData(0, 0, w, h).data, m = new Uint8Array(w * h);
    for (let i = 0; i < m.length; i++) m[i] = d[4 * i + 3] >= 128 ? 1 : 0;
    return m;
  }

  /* ───────── Vista previa de la foto ───────── */
  function renderPhoto() {
    const info = $("#colorInfo");
    if (!current) { info.textContent = "Abre una foto para ver la vista previa."; return; }
    const w8 = read("c_peso"), n = read("c_capas"), h = read("c_capa");
    const P = photoPixels(w8);
    if (!P) return;
    const { w, h: rows, lab: L } = P;
    const mask = shapeMask(w, rows);
    const k = fils.length - 1;
    const fkey = JSON.stringify([fils, n, h, w8, P.key, read("c_contorno")]);
    if (read("c_auto")) {
      if (startsKey !== fkey || !starts || starts.length !== k) {
        // Muestra: colores cuantizados con su peso (los grandes fondos cuentan lo que ocupan).
        const bins = new Map();
        for (let i = 0; i < w * rows; i++) {
          if (!mask[i]) continue;
          const kk = `${Math.round(L[3 * i] / 4)},${Math.round(L[3 * i + 1] / 4)},${Math.round(L[3 * i + 2] / 4)}`;
          const b = bins.get(kk); if (b) b[1]++; else bins.set(kk, [i, 1]);
        }
        let entries = [...bins.values()];
        if (entries.length > 1500) entries = entries.sort((a, b) => b[1] - a[1]).slice(0, 1500);
        const sample = new Float64Array(entries.length * 3), weights = new Float64Array(entries.length);
        entries.forEach(([i, c], j) => { sample.set(L.subarray(3 * i, 3 * i + 3), 3 * j); weights[j] = c; });
        starts = chooseStarts(sample, weights, n, h, w8);
        startsKey = fkey;
        drawChanges();
      }
    } else if (!starts || starts.length !== k || starts.some((s, i) => s < 1 || s > n || (i && s <= starts[i - 1]))) {
      starts = Array.from({ length: k }, (_, i) => Math.round(((i + 1) * n) / (k + 1)));
      drawChanges();
    }
    const st = [0, ...starts];
    const top = read("c_borde") > 0 ? n + Math.max(1, Math.round(read("c_borde_alto") / h)) : n;
    const stack = stackColors(st, top, h), SL = stackLab(st, n, h, w8);
    // Capa de cada píxel
    const level = new Uint16Array(w * rows);
    let err = 0, cnt = 0;
    for (let i = 0; i < w * rows; i++) {
      const a = L[3 * i], b = L[3 * i + 1], c = L[3 * i + 2];
      let best = Infinity, bk = 0;
      for (let q = 0; q <= n; q++) {
        const d0 = a - SL[3 * q], d1 = b - SL[3 * q + 1], d2 = c - SL[3 * q + 2];
        const d = d0 * d0 + d1 * d1 + d2 * d2;
        if (d < best) { best = d; bk = q; }
      }
      level[i] = bk;
      if (mask[i]) { err += best; cnt++; }
    }
    // Borde para la resina
    const rimPx = read("c_borde") > 0 ? Math.max(1, Math.round((read("c_borde") / read("c_ancho")) * (w - 1))) : 0;
    if (rimPx) {
      let edge = mask.slice();
      for (let s = 0; s < rimPx; s++) {
        const next = edge.slice();
        for (let y = 0; y < rows; y++) for (let x = 0; x < w; x++) {
          const i = y * w + x;
          if (!edge[i]) continue;
          if (x === 0 || y === 0 || x === w - 1 || y === rows - 1 || !edge[i - 1] || !edge[i + 1] || !edge[i - w] || !edge[i + w]) next[i] = 0;
        }
        edge = next;
      }
      for (let i = 0; i < w * rows; i++) if (mask[i] && !edge[i]) level[i] = top;
    }
    // Pintar: color de la pila, sombreado del relieve y, si se pide, el brillo de la resina
    const scale = Math.max(1, Math.floor(560 / Math.max(w, rows)));
    const cv = $("#cvColor");
    cv.width = w * scale; cv.height = rows * scale;
    const ctx = cv.getContext("2d");
    const img = ctx.createImageData(w, rows);
    const mmpx = read("c_ancho") / (w - 1);
    const lx = -0.45, ly = 0.55, lz = 0.7;   // luz desde arriba a la izquierda
    for (let y = 0; y < rows; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x, o = 4 * i;
      if (!mask[i]) { img.data[o + 3] = 0; continue; }
      let [r, g, b] = stack[Math.min(level[i], top)];
      if (shade) {
        const zl = level[x > 0 ? i - 1 : i] * h, zr = level[x < w - 1 ? i + 1 : i] * h;
        const zu = level[y > 0 ? i - w : i] * h, zd = level[y < rows - 1 ? i + w : i] * h;
        const gx = (zr - zl) / (2 * mmpx) * 2.5, gy = (zu - zd) / (2 * mmpx) * 2.5;   // algo exagerado, como con luz rasante
        const len = Math.hypot(gx, gy, 1);
        const lam = (-gx * lx - gy * ly + lz) / len / lz;
        const f = Math.min(1.15, Math.max(0.7, 0.5 + 0.5 * lam));
        r *= f; g *= f; b *= f;
      }
      if (resin) {   // reflejo suave en diagonal, como un barniz
        const t = (x / w + y / rows) / 2, spec = Math.exp(-((t - 0.3) ** 2) / 0.006) * 0.35;
        r = r * 0.96 + spec; g = g * 0.96 + spec; b = b * 0.97 + spec;
      }
      img.data[o] = Math.min(255, r * 255); img.data[o + 1] = Math.min(255, g * 255); img.data[o + 2] = Math.min(255, b * 255); img.data[o + 3] = 255;
    }
    const tmp = document.createElement("canvas"); tmp.width = w; tmp.height = rows;
    tmp.getContext("2d").putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = scale < 2;
    ctx.drawImage(tmp, 0, 0, cv.width, cv.height);
    drawStack(stack, st, n);
    const base = read("c_base"), z0 = read("c_primera") + (base - 1) * h;
    const changes = starts.map((s, i) => `capa ${base + s} (Z ${(z0 + s * h).toFixed(2).replace(".", ",")} mm) → ${fils[i + 1].nombre}`);
    info.textContent = `${fils.length - 1} cambio(s): ${changes.join(" · ")}. Diferencia media con la foto: ${Math.sqrt(err / Math.max(1, cnt)).toFixed(1)} (cuanto menos, mejor).`;
  }

  function drawStack(stack, st, n) {
    const cv = $("#cvStack");
    cv.width = cv.clientWidth || 400;
    const c = cv.getContext("2d"), W = cv.width, m = stack.length;
    for (let k = 0; k < m; k++) { c.fillStyle = rgbHex(stack[k]); c.fillRect(Math.floor((k * W) / m), 0, Math.ceil(W / m) + 1, 26); }
    c.fillStyle = "#fff"; c.strokeStyle = "#000";
    st.slice(1).forEach((s) => { const x = Math.round((s * W) / m); c.fillRect(x - 1, 0, 2, 26); });
    c.font = "11px sans-serif"; c.fillStyle = "rgba(255,255,255,.85)";
    c.fillText("base", 4, 17); c.textAlign = "right"; c.fillText(`${n} capas`, W - 4, 17);
  }

  /* ───────── Filamentos ───────── */
  function drawFils() {
    const box = $("#c_fils");
    box.innerHTML = "";
    fils.forEach((f, i) => {
      const row = document.createElement("div");
      row.className = "filrow";
      row.innerHTML = `<input type="color" aria-label="Color del filamento ${i + 1}"><input type="text" maxlength="30" aria-label="Nombre"><input type="number" min="0.05" max="20" step="0.1" title="TD en mm" aria-label="TD en mm">`;
      const [col, name, td] = row.querySelectorAll("input");
      col.value = f.color; name.value = f.nombre; td.value = f.td;
      col.addEventListener("input", () => { f.color = col.value; changed(); });
      name.addEventListener("input", () => { f.nombre = name.value; save(); renderSoon(); });
      td.addEventListener("input", () => { f.td = Math.max(0.05, Number(td.value) || 0.05); changed(); });
      const del = document.createElement("button");
      del.type = "button"; del.className = "iconbtn"; del.title = "Quitar este filamento"; del.innerHTML = icon("close");
      del.disabled = fils.length <= 2;
      del.addEventListener("click", () => { fils.splice(i, 1); drawFils(); changed(); });
      row.append(del);
      box.append(row);
    });
    const sel = $("#c_biblio");
    sel.disabled = fils.length >= MAX_FILS;
    sel.innerHTML = `<option value="">${fils.length >= MAX_FILS ? "Máximo 4 filamentos" : "Añadir filamento…"}</option>` +
      LIBRARY.map(([n, c, t], i) => `<option value="${i}">${n} · TD ${String(t).replace(".", ",")}</option>`).join("");
  }
  function drawChanges() {
    const box = $("#c_cambios");
    box.innerHTML = "";
    if (read("c_auto") || !starts) return;
    starts.forEach((s, i) => {
      const row = document.createElement("label");
      row.className = "filrow chg";
      row.innerHTML = `<span>Capa de cambio a ${fils[i + 1]?.nombre || ""}</span><input type="number" min="1" max="${read("c_capas")}" step="1">`;
      const inp = row.querySelector("input");
      inp.value = s;
      inp.addEventListener("input", () => { starts[i] = Math.round(Number(inp.value)); save(); renderSoon(); });
      box.append(row);
    });
  }
  const changed = () => { save(); renderSoon(); };

  /* ───────── Posavasos ───────── */
  function drawPalette() {
    const box = $("#p_paleta");
    box.innerHTML = "";
    const n = Number(read("p_colores"));
    pal.slice(0, n).forEach((p, i) => {
      const row = document.createElement("div");
      row.className = "filrow pal";
      row.innerHTML = `<input type="color" aria-label="Color ${i + 1}"><input type="text" maxlength="30" aria-label="Nombre del color ${i + 1}">`;
      const [col, name] = row.querySelectorAll("input");
      col.value = p.color; name.value = p.nombre;
      col.title = ["Color 1: la base", "Color 2: el motivo", "Color 3: el detalle"][i];
      col.addEventListener("input", () => { p.color = col.value; save(); drawCoaster(); });
      name.addEventListener("input", () => { p.nombre = name.value; save(); });
      box.append(row);
    });
  }
  async function loadMasks() {
    try { masks = await (await api("GET", "/api/mascaras")).json(); } catch { masks = []; }
    for (const id of ["p_mascara2", "p_mascara3"]) {
      const sel = $(`#${id}`), was = sel.value || store.get("color1")?.campos?.[id] || "";
      sel.innerHTML = `<option value="">${id === "p_mascara2" ? "Elige una silueta" : "Ninguna"}</option>` +
        masks.map((m) => `<option value="${m.id}">${m.nombre || m.id}</option>`).join("");
      sel.value = masks.some((m) => m.id === was) ? was : "";
    }
  }
  /* ───────── SVG del motivo ───────── */
  const svgCurrent = () => svgs.find((m) => m.id === read("p_svg"));
  async function loadSvgs(select) {
    try { svgs = await (await api("GET", "/api/svgs")).json(); } catch { svgs = []; }
    const sel = $("#p_svg"), was = select || sel.value || store.get("color1")?.campos?.p_svg || "";
    sel.innerHTML = `<option value="">Elige un SVG</option>` + svgs.map((m) => `<option value="${m.id}">${m.nombre}</option>`).join("");
    sel.value = svgs.some((m) => m.id === was) ? was : "";
    drawSvgColors();
  }
  function svgMapOf(m) {
    if (!m) return null;
    const saved = svgMaps[m.id] || {};
    return Object.fromEntries(m.colores.map((c) => [c.color, c.color in saved ? saved[c.color] : c.asignado]));
  }
  function drawSvgColors() {
    const box = $("#p_svg_colores"), m = svgCurrent();
    box.innerHTML = "";
    $("#p_svg_avisos").textContent = m ? m.avisos.join(" ") : "";
    if (!m) return;
    const map = svgMapOf(m);
    m.colores.forEach((c) => {
      const row = document.createElement("label");
      row.className = "filrow svgc";
      row.innerHTML = `<i class="sw" style="background:${c.color}"></i><span>${c.color} · ${String(c.area).replace(".", ",")} %</span><select><option value="0">Ignorar</option><option value="2">Color 2 (motivo)</option><option value="3">Color 3 (detalle)</option></select>`;
      const sel = row.querySelector("select");
      sel.value = String(map[c.color]);
      sel.addEventListener("change", () => { svgMaps[m.id] = { ...svgMapOf(m), [c.color]: Number(sel.value) }; save(); render(); });
      box.append(row);
    });
  }
  function coasterBody() {
    const n = Number(read("p_colores"));
    return {
      modo: read("p_modo"), pasada: Number(read("p_pasada")), colores: n, forma: read("p_forma"), tamano: read("p_tamano"), esquinas: read("p_esquinas"),
      grosor: read("p_grosor"), margen: read("p_margen"), incrustacion: Number(read("p_incrustacion")), alto2: read("p_alto2"),
      alto3: read("p_alto3"), borde: read("p_borde"), borde_alto: read("p_borde_alto"), motivo: read("p_motivo"),
      texto2: read("p_texto2"), texto3: read("p_texto3"), texto_mm: read("p_texto_mm"),
      mascara2_id: read("p_mascara2") || null, mascara3_id: read("p_mascara3") || null, motivo_mm: read("p_motivo_mm"),
      svg_id: read("p_svg") || null, svg_mapa: svgMapOf(svgCurrent()), ajuste: read("p_ajuste"), motivo_giro: read("p_giro"), motivo_dx: read("p_dx"), motivo_dy: read("p_dy"),
      paleta: pal.map((p) => p.color), nombres: pal.map((p) => p.nombre),
    };
  }
  async function fetchCoaster() {
    try {
      coasterGeo = await (await api("POST", "/api/posavasos/vista", coasterBody())).json();
      drawCoaster();
    } catch (e) { $("#colorInfo").textContent = e.message; }
  }
  function drawCoaster() {
    if (!coasterGeo) return;
    const cv = $("#cvColor"), S = 520, size = read("p_tamano");
    cv.width = cv.height = S;
    const c = cv.getContext("2d"), k = (S - 20) / size;
    c.clearRect(0, 0, S, S);
    const path = (polys) => { const p = new Path2D(); for (const loop of polys || []) { loop.forEach(([x, y], i) => (i ? p.lineTo(S / 2 + x * k, S / 2 - y * k) : p.moveTo(S / 2 + x * k, S / 2 - y * k))); p.closePath(); } return p; };
    const n = Number(read("p_colores")), rel = read("p_modo") === "relieve";
    const lastColor = pal[n === 3 && coasterGeo.c3.length ? 2 : 1].color;
    c.fillStyle = coasterGeo.interior ? lastColor : pal[0].color;   // el borde sube con la pieza: arriba es del último color
    c.fill(path(coasterGeo.contorno), "evenodd");
    if (coasterGeo.interior) { c.fillStyle = pal[0].color; c.fill(path(coasterGeo.interior), "evenodd"); }
    const drop = (p) => { if (!rel || !shade) return; c.save(); c.shadowColor = "rgba(0,0,0,.45)"; c.shadowBlur = 4; c.shadowOffsetX = 2; c.shadowOffsetY = 2; c.fill(p, "evenodd"); c.restore(); };
    c.fillStyle = pal[1].color; const p2 = path(rel ? [...coasterGeo.c2, ...coasterGeo.c3] : coasterGeo.c2); drop(p2); c.fill(p2, "nonzero");
    if (n === 3) { c.fillStyle = pal[2].color; const p3 = path(coasterGeo.c3); drop(p3); c.fill(p3, "evenodd"); }
    if (resin) {
      const g = c.createLinearGradient(0, 0, S, S);
      g.addColorStop(0.15, "rgba(255,255,255,0)"); g.addColorStop(0.3, "rgba(255,255,255,.32)"); g.addColorStop(0.45, "rgba(255,255,255,0)");
      c.save(); c.clip(path(coasterGeo.interior || coasterGeo.contorno), "evenodd"); c.fillStyle = g; c.fillRect(0, 0, S, S); c.restore();
    }
    const mp = read("p_modo") === "multipaso";
    const changes = mp ? `multipaso: ${n} pasadas en el mismo sitio de la cama, sin M600; se imprime boca abajo` : rel ? `${n - 1} cambio(s) de filamento, sin capas mixtas` : `incrustado: ${n - 1} cambio(s) en la primera capa; se imprime boca abajo`;
    const lost = coasterGeo.perdido > 0.02 ? ` Se recorta un ${Math.round(coasterGeo.perdido * 100)} % del motivo por salirse del área libre: redúcelo, muévelo o aumenta el tamaño.` : "";
    $("#colorInfo").textContent = coasterGeo.vacio ? "El motivo está vacío: escribe un texto, elige una silueta o un SVG." :
      `${size} mm · ${changes}${coasterGeo.interior ? ". El borde lleva arriba el último color: hace de molde para la resina UV." : "."}${lost}`;
    $("#cvStack").hidden = true;
  }

  /* ───────── Pintar y generar ───────── */
  function render() {
    if (!on) return;
    if (tipo === "posavasos") { clearTimeout(coasterTimer); coasterTimer = setTimeout(fetchCoaster, 150); return; }
    $("#cvStack").hidden = false;
    try { renderPhoto(); } catch (e) { console.error(e); }
  }
  function renderSoon() { clearTimeout(timer); timer = setTimeout(render, 120); }

  function refresh() {
    document.body.classList.toggle("color-pos", tipo === "posavasos");
    $("#c_tipoFoto").setAttribute("aria-pressed", String(tipo === "foto"));
    $("#c_tipoPos").setAttribute("aria-pressed", String(tipo === "posavasos"));
    $("[data-c-borde]").hidden = !(read("c_borde") > 0);
    const rel = read("p_modo") === "relieve", mot = read("p_motivo");
    $$("[data-p-rel]").forEach((e) => (e.hidden = !rel));
    $$("[data-p-inc]").forEach((e) => (e.hidden = rel || read("p_modo") === "multipaso"));
    $$("[data-p-mp]").forEach((e) => (e.hidden = read("p_modo") !== "multipaso"));
    $$("[data-p-mot]").forEach((e) => (e.hidden = !e.dataset.pMot.split(" ").includes(mot)));
    $("[data-p-esq]").hidden = ["redondo", "flor", "gota"].includes(read("p_forma"));
    $$("output[data-for^='c_']").forEach((o) => (o.textContent = Number($(`#${o.dataset.for}`).value).toLocaleString("es-ES")));
    $("#c_sombra").setAttribute("aria-pressed", String(shade));
    $("#c_resina").setAttribute("aria-pressed", String(resin));
    const btn = $("#btnColor");
    btn.lastChild.textContent = tipo === "posavasos" ? " Generar posavasos" : " Generar foto en color";
    btn.disabled = tipo === "foto" && !current;
    if (on && tipo === "posavasos") { $("#views").hidden = false; $("#empty").hidden = true; }
    else if (!current) { $("#views").hidden = true; $("#empty").hidden = false; }
  }

  async function generate() {
    const btn = $("#btnColor");
    const label = btn.lastChild.textContent;
    btn.disabled = true; btn.classList.add("busy");
    btn.lastChild.textContent = " Generando…";
    try {
      if (tipo === "posavasos") {
        const info = await (await api("POST", "/api/posavasos", coasterBody())).json();
        const [w, h, d] = info.medidas_mm.map((v) => v.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
        window.Visor.open({
          ...(info.capas_color ? { url: info.stl, colorLayers: info.capas_color } : { parts: info.partes }), name: `Posavasos ${read("p_forma")}`, mode: "color",
          details: `${w} × ${h} × ${d} mm · unos ${info.gramos} g de PLA` + (info.resina_ml ? ` · unos ${info.resina_ml.toLocaleString("es-ES")} ml de resina` : ""),
          download: info.stl, download3mf: info.tresmf, downloadZip: info.zip, settings: info.ajustes,
        });
      } else {
        if (!current) return;
        const info = await (await api("POST", "/api/multicolor/foto", {
          imagen_id: current.id, filamentos: fils.map((f) => ({ nombre: f.nombre.trim() || "filamento", color: f.color, td: f.td })),
          ancho: read("c_ancho"), resolucion: read("c_resolucion"), capa: read("c_capa"), primera: read("c_primera"), base: read("c_base"),
          capas: read("c_capas"), peso_color: read("c_peso"), contraste: read("c_contraste"), contorno: read("c_contorno"),
          borde: read("c_borde"), borde_alto: read("c_borde_alto"), girar: crop.rot, recorte: [crop.x, crop.y, crop.w, crop.h], cambios: starts,
        })).json();
        const [w, h, d] = info.medidas_mm.map((v) => v.toLocaleString("es-ES", { maximumFractionDigits: 2 }));
        window.Visor.open({
          url: info.vista, name: current.nombre, mode: "color", colorLayers: info.capas_color,
          details: `${w} × ${h} × ${d} mm · ${info.triangulos.toLocaleString("es-ES")} triángulos · unos ${info.gramos} g de PLA · ${info.cambios.length} cambio(s)`,
          download: info.stl, download3mf: info.tresmf, settings: info.ajustes,
        });
      }
    } catch (e) { toast(e.message, "err"); }
    finally { btn.lastChild.textContent = label; btn.classList.remove("busy"); refresh(); }
  }

  function init() {
    restore();
    drawFils();
    drawPalette();
    for (const id of FIELDS) $(`#${id}`).addEventListener("input", () => {
      if (id === "c_auto") { drawChanges(); }
      if (id === "p_colores") drawPalette();
      if (id === "c_capas") startsKey = "";
      refresh(); save(); render();
    });
    $("#c_biblio").addEventListener("change", (e) => {
      const it = LIBRARY[Number(e.target.value)];
      e.target.value = "";
      if (!it || fils.length >= MAX_FILS) return;
      fils.push({ nombre: it[0], color: it[1], td: it[2] });
      drawFils(); changed();
    });
    $("#c_ordenar").addEventListener("click", () => { fils.sort((a, b) => luma(a.color) - luma(b.color)); drawFils(); changed(); });
    $("#c_tipoFoto").addEventListener("click", () => { tipo = "foto"; refresh(); save(); render(); });
    $("#c_tipoPos").addEventListener("click", () => { tipo = "posavasos"; refresh(); save(); render(); });
    $("#c_sombra").addEventListener("click", () => { shade = !shade; refresh(); save(); tipo === "posavasos" ? drawCoaster() : render(); });
    $("#c_resina").addEventListener("click", () => { resin = !resin; refresh(); save(); tipo === "posavasos" ? drawCoaster() : render(); });
    $("#btnColor").addEventListener("click", generate);
    $("#p_subir").addEventListener("click", () => $("#p_fichero").click());
    $("#p_fichero").addEventListener("change", async (e) => {
      const file = e.target.files[0]; e.target.value = "";
      if (!file) return;
      const fd = new FormData(); fd.append("archivo", file);
      try {
        const m = await (await api("POST", "/api/mascaras", fd)).json();
        await loadMasks();
        const target = read("p_mascara2") ? "p_mascara3" : "p_mascara2";
        $(`#${target}`).value = m.id;
        save(); render();
      } catch (err) { toast(err.message, "err"); }
    });
    $("#p_svg").addEventListener("change", () => { drawSvgColors(); save(); render(); });
    $("#p_svg_subir").addEventListener("click", () => $("#p_svg_fichero").click());
    $("#p_svg_fichero").addEventListener("change", async (e) => {
      const file = e.target.files[0]; e.target.value = "";
      if (!file) return;
      const fd = new FormData(); fd.append("archivo", file);
      try {
        const m = await (await api("POST", "/api/svgs", fd)).json();
        await loadSvgs(m.id);
        save(); render();
      } catch (err) { toast(err.message, "err"); }
    });
    // Arrastrar el motivo SVG en la vista previa
    const cv = $("#cvColor");
    let drag = null;
    cv.addEventListener("pointerdown", (e) => {
      if (!on || tipo !== "posavasos" || read("p_motivo") !== "svg") return;
      drag = { x: e.clientX, y: e.clientY, dx: read("p_dx"), dy: read("p_dy") }; cv.setPointerCapture(e.pointerId); cv.style.cursor = "grabbing";
    });
    cv.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const mmPerPx = ((cv.width / (cv.width - 20)) * read("p_tamano")) / cv.getBoundingClientRect().width;   // el lienzo deja 10 px de margen por lado
      $("#p_dx").value = Math.max(-100, Math.min(100, Math.round((drag.dx + (e.clientX - drag.x) * mmPerPx) * 2) / 2));
      $("#p_dy").value = Math.max(-100, Math.min(100, Math.round((drag.dy - (e.clientY - drag.y) * mmPerPx) * 2) / 2));
      render();
    });
    const end = () => { if (drag) { drag = null; cv.style.cursor = ""; save(); } };
    cv.addEventListener("pointerup", end); cv.addEventListener("pointercancel", end);
    loadSvgs();
    loadMasks();
    refresh();
    drawChanges();
    on = document.body.classList.contains("modo-color");
    if (on) { refresh(); render(); }
  }

  const api_ = {
    onMode(v) { on = v; refresh(); if (on) render(); },
    onSelect() { pix = null; startsKey = ""; refresh(); },
    onSource() { pix = null; startsKey = ""; if (on && tipo === "foto") renderSoon(); },
  };
  window.Color = api_;
  init();
  return api_;
})();
