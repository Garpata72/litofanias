/* Imanes de nevera: hoja de fotos en PDF y útiles de corte y montaje.
   Usa $, $$, api, toast, store, icon, current y loadImages de app.js. El recorte de cada foto sigue las mismas
   fórmulas que litofania/magnets.py (crop_box): si se cambia uno, cambiar el otro. */
"use strict";
const Iman = (() => {
  const FIELDS = { m_lado: "lado", m_radio: "radio", m_sep: "sep", m_acrilico: "grosor_acrilico", m_papel: "grosor_papel",
    m_iman: "grosor_iman", m_holgura: "holgura", m_margen: "margen_corte" };
  const DEFAULTS = { m_lado: 50, m_radio: 4, m_sep: "", m_acrilico: 3, m_papel: 0.25, m_iman: 0.8, m_holgura: 0.3, m_margen: 0.2 };
  const BLEED = 2, MIN_DPI = 300, ZMAX = 6;
  const fmt = (n, d = 1) => Number(n).toLocaleString("es-ES", { maximumFractionDigits: d });
  let on = false, sel = 0, page = 0, info = null, infoError = "", timer = null;
  let items = (store.get("imanes.fotos") || []).filter((it) => it && it.id);
  const imgs = new Map();

  /* ───────── Medidas ───────── */
  function kit() {
    const k = {};
    for (const [id, key] of Object.entries(FIELDS)) {
      const v = $(`#${id}`).value.trim();
      if (v !== "") k[key] = Number(v);
    }
    return k;
  }
  const query = () => new URLSearchParams(kit()).toString();
  const lado = () => kit().lado || 50;
  const paper = () => $("#m_papelsel").value;
  function saveFields() {
    store.set("imanes.kit", Object.fromEntries(Object.keys(FIELDS).map((id) => [id, $(`#${id}`).value])));
    store.set("imanes.papel", paper());
    store.set("imanes.rellenar", $("#m_rellenar").checked);
  }
  function restoreFields() {
    const saved = store.get("imanes.kit") || {};
    for (const id of Object.keys(FIELDS)) $(`#${id}`).value = id in saved ? saved[id] : DEFAULTS[id];
    if (store.get("imanes.papel")) $("#m_papelsel").value = store.get("imanes.papel");
    $("#m_rellenar").checked = !!store.get("imanes.rellenar");
  }
  const saveItems = () => store.set("imanes.fotos", items);

  async function fetchLayout() {
    try {
      info = await (await api("GET", `/api/imanes/papeles?${query()}`)).json();
      infoError = "";
      $("#m_sep").placeholder = fmt(info.sep);
    } catch (e) { info = null; infoError = e.message; }
    updateLinks();
    drawAll();
  }
  const relayout = () => { clearTimeout(timer); timer = setTimeout(fetchLayout, 200); };
  const sheet = () => info?.papeles[paper()];

  function updateLinks() {
    const q = query(), bad = !info;
    const links = { m_stl_base: `/api/imanes/utiles/base_corte.stl?${q}`, m_stl_marco: `/api/imanes/utiles/marco_corte.stl?${q}`,
      m_stl_montaje: `/api/imanes/utiles/montaje.stl?${q}`, m_3mf: `/api/imanes/utiles.3mf?${q}`, m_scad: `/api/imanes/utiles.scad?${q}`, m_txt: `/api/imanes/utiles.txt?${q}` };
    for (const [id, href] of Object.entries(links)) { $(`#${id}`).href = href; $(`#${id}`).classList.toggle("off", bad); }
    $("#m_view3d").disabled = bad;
  }

  /* ───────── Fotos ───────── */
  function image(id) {
    if (!imgs.has(id)) {
      const im = new Image();
      im.onload = () => { renderList(); drawAll(); };
      im.onerror = () => { im.broken = true; renderList(); };
      im.src = `/api/imagenes/${id}/archivo`;
      imgs.set(id, im);
    }
    return imgs.get(id);
  }
  const ready = (im) => im && im.complete && im.naturalWidth > 0;
  // Medidas de la foto ya girada (el navegador ya aplica la orientación EXIF, como exif_transpose).
  const dims = (im, rot) => (rot % 180 ? [im.naturalHeight, im.naturalWidth] : [im.naturalWidth, im.naturalHeight]);

  /* El cuadrado que se imprime (foto + sangrado), en píxeles de la foto girada. */
  function cropBox(it, im) {
    const [W, H] = dims(im, it.girar);
    const side = Math.max(1, Math.round(Math.min(W, H) / Math.max(1, it.zoom)));
    const x = Math.round(Math.min(Math.max(it.cx * W - side / 2, 0), W - side));
    const y = Math.round(Math.min(Math.max(it.cy * H - side / 2, 0), H - side));
    return { x, y, side, W, H };
  }
  const dpiOf = (it, im) => cropBox(it, im).side / ((lado() + 2 * BLEED) / 25.4);
  function clamp(it, im) {
    const b = cropBox(it, im);
    it.cx = (b.x + b.side / 2) / b.W;
    it.cy = (b.y + b.side / 2) / b.H;
  }

  /* Dibuja la foto girada de modo que el cuadrado de recorte ocupe (dx, dy, size). Sin recortar lo de fuera. */
  function paintPhoto(ctx, it, im, dx, dy, size) {
    const b = cropBox(it, im), k = size / b.side;
    ctx.save();
    ctx.translate(dx - b.x * k, dy - b.y * k);
    ctx.scale(k, k);
    ctx.translate(b.W / 2, b.H / 2);
    ctx.rotate((it.girar * Math.PI) / 180);
    ctx.drawImage(im, -im.naturalWidth / 2, -im.naturalHeight / 2);
    ctx.restore();
  }
  function rrect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, Math.max(0, Math.min(r, w / 2, h / 2)));
    else ctx.rect(x, y, w, h);
  }

  function addItem(meta) {
    const i = items.findIndex((it) => it.id === meta.id);
    if (i >= 0) { select(i); return false; }
    items.push({ id: meta.id, nombre: meta.nombre, girar: 0, zoom: 1, cx: 0.5, cy: 0.5, copias: 1 });
    saveItems();
    select(items.length - 1);
    return true;
  }
  function select(i) {
    sel = Math.max(0, Math.min(i, items.length - 1));
    const it = items[sel];
    if (it) $("#m_zoom").value = it.zoom;
    const s = sheet();
    if (s?.por_hoja) {   // ir a la hoja donde está la primera copia
      const idx = slots(s.por_hoja).findIndex((x) => x === it);
      if (idx >= 0) page = Math.floor(idx / s.por_hoja);
    }
    renderList();
    drawAll();
  }

  async function uploadFiles(files) {
    files = [...files].filter((f) => f.type.startsWith("image/"));
    if (!files.length) { toast("Eso no parece una imagen.", "err"); return; }
    let n = 0;
    for (const f of files) {
      const fd = new FormData();
      fd.append("archivo", f);
      try { addItem(await (await api("POST", "/api/imagenes", fd)).json()); n++; } catch (e) { toast(`${f.name}: ${e.message}`, "err"); }
    }
    try { await loadImages(); } catch { /* la lista de la izquierda se refresca la próxima vez */ }
    if (n) toast(n === 1 ? "Foto añadida a la hoja." : `${n} fotos añadidas a la hoja.`, "ok");
  }

  function renderList() {
    const box = $("#m_list");
    box.innerHTML = items.length ? "" : '<div class="none">Todavía no hay fotos en la hoja.</div>';
    items.forEach((it, i) => {
      const im = image(it.id);
      const row = document.createElement("div");
      row.className = `mrow${i === sel ? " sel" : ""}`;
      row.title = "Encuadrar esta foto";
      const th = document.createElement("span");
      th.className = "th";
      th.style.backgroundImage = `url(/api/imagenes/${it.id}/archivo)`;
      const nm = document.createElement("span");
      nm.className = "nm";
      const name = document.createElement("span");
      name.textContent = it.nombre;
      const res = document.createElement("small");
      if (im.broken) { res.textContent = "Ya no está en la app"; res.className = "low"; }
      else if (ready(im)) {
        const d = dpiOf(it, im);
        res.textContent = d < MIN_DPI ? `⚠ ${fmt(d, 0)} ppp: baja resolución` : `${fmt(d, 0)} ppp`;
        if (d < MIN_DPI) res.className = "low";
      }
      nm.append(name, res);
      const copies = document.createElement("input");
      copies.type = "number"; copies.min = 1; copies.max = 100; copies.step = 1; copies.value = it.copias;
      copies.title = "Copias de esta foto"; copies.setAttribute("aria-label", `Copias de ${it.nombre}`);
      copies.addEventListener("click", (e) => e.stopPropagation());
      copies.addEventListener("input", () => {
        it.copias = Math.max(1, Math.min(100, Math.round(Number(copies.value) || 1)));
        saveItems(); drawAll();
      });
      const x = document.createElement("button");
      x.type = "button"; x.className = "iconbtn"; x.innerHTML = icon("close");
      x.title = "Quitar de la hoja"; x.setAttribute("aria-label", `Quitar ${it.nombre} de la hoja`);
      x.addEventListener("click", (e) => {
        e.stopPropagation();
        items.splice(i, 1);
        saveItems();
        select(Math.min(sel, items.length - 1));
      });
      row.append(th, nm, copies, x);
      row.addEventListener("click", () => select(i));
      box.append(row);
    });
  }

  /* ───────── Hoja ───────── */
  // Igual que magnets.sheet_slots: cada foto tantas veces como copias; «rellenar» completa la última hoja.
  function slots(per) {
    const out = items.flatMap((it) => Array(Math.max(1, it.copias)).fill(it));
    if (!out.length) return Array(per).fill(null);
    if ($("#m_rellenar").checked) for (let i = 0; out.length % per; i++) out.push(items[i % items.length]);
    return out;
  }

  function drawFit() {
    const el = $("#m_fit"), s = sheet();
    el.classList.toggle("bad", !s?.por_hoja);
    if (!info) { el.textContent = infoError; $("#summary").textContent = ""; return; }
    if (!s.por_hoja) { el.textContent = `⚠ ${s.error}`; $("#summary").textContent = "No cabe en este papel"; return; }
    const all = slots(s.por_hoja), sheets = Math.ceil(all.length / s.por_hoja), photos = items.length ? all.length : 0;
    const others = Object.values(info.papeles).filter((p) => p.papel !== s.papel)
      .map((p) => `${p.nombre}: ${p.por_hoja || "no cabe"}`).join(" · ");
    el.textContent = `${s.por_hoja} imanes por hoja (${s.columnas} × ${s.filas}, papel ${s.horizontal ? "apaisado" : "vertical"})`
      + (s.regla ? "" : ". No cabe la regla de control.") + ` Otros papeles: ${others}.`;
    $("#summary").textContent = photos ? `${photos} imanes en ${sheets} ${sheets === 1 ? "hoja" : "hojas"} de ${s.nombre}` : `Papel ${s.nombre}`;
  }

  function drawSheet() {
    const cv = $("#m_sheet"), s = sheet();
    const ctx = cv.getContext("2d");
    if (!s?.por_hoja) {
      cv.width = 400; cv.height = 300;
      ctx.fillStyle = "#171c22"; ctx.fillRect(0, 0, 400, 300);
      ctx.fillStyle = "#ff8d6b"; ctx.font = "600 15px system-ui"; ctx.textAlign = "center";
      ctx.fillText(info ? `El imán no cabe en ${s.nombre}` : "Revisa las medidas", 200, 150);
      $("#m_capSheet").textContent = "Hoja";
      return;
    }
    const all = slots(s.por_hoja), pages = Math.ceil(all.length / s.por_hoja);
    page = Math.max(0, Math.min(page, pages - 1));
    const W = s.ancho_mm, H = s.alto_mm, k = Math.min(1040 / W, 1360 / H);
    cv.width = Math.round(W * k); cv.height = Math.round(H * k);
    const X = (x) => x * k, Y = (y) => (H - y) * k;   // el PDF tiene el origen abajo
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = "#222"; ctx.font = `600 ${Math.max(9, 2.4 * k)}px system-ui`; ctx.textAlign = "left";
    ctx.fillText(`Imanes ${fmt(lado())} mm · ${s.nombre} · imprimir al 100 %`, X(5), Y(H - 7));
    if (s.regla_mm) {
      const [rx, ry, up] = s.regla_mm;
      ctx.strokeStyle = "#000"; ctx.lineWidth = Math.max(1, 0.25 * k);
      ctx.beginPath();
      if (up) { ctx.moveTo(X(rx - 3), Y(ry)); ctx.lineTo(X(rx - 3), Y(ry + 50)); for (let t = 0; t <= 10; t++) { ctx.moveTo(X(rx - 3), Y(ry + 5 * t)); ctx.lineTo(X(rx - 3 - (t % 2 ? 1 : 2)), Y(ry + 5 * t)); } }
      else { ctx.moveTo(X(rx), Y(ry)); ctx.lineTo(X(rx + 50), Y(ry)); for (let t = 0; t <= 10; t++) { ctx.moveTo(X(rx + 5 * t), Y(ry)); ctx.lineTo(X(rx + 5 * t), Y(ry + (t % 2 ? 1 : 2))); } }
      ctx.stroke();
    }
    const L = lado(), S = L + 2 * BLEED, sep = info.sep, r = kit().radio ?? 4;
    s.centros_mm.forEach(([cx, cy], j) => {
      const it = all[page * s.por_hoja + j];
      if (it === undefined) return;
      const x0 = X(cx - S / 2), y0 = Y(cy + S / 2), size = S * k;
      const im = it && image(it.id);
      if (it && ready(im)) {
        ctx.save(); ctx.beginPath(); ctx.rect(x0, y0, size, size); ctx.clip();
        paintPhoto(ctx, it, im, x0, y0, size);
        ctx.restore();
      } else if (it) { ctx.fillStyle = "#ccd"; ctx.fillRect(x0, y0, size, size); }
      ctx.setLineDash([k, k]); ctx.strokeStyle = "#808080"; ctx.lineWidth = Math.max(1, 0.15 * k);
      rrect(ctx, X(cx - L / 2), Y(cy + L / 2), L * k, L * k, r * k); ctx.stroke();
      ctx.setLineDash([]); ctx.strokeStyle = "#000";
      for (const sx of [-sep, sep]) {
        ctx.beginPath();
        ctx.moveTo(X(cx + sx - 3), Y(cy)); ctx.lineTo(X(cx + sx + 3), Y(cy));
        ctx.moveTo(X(cx + sx), Y(cy - 3)); ctx.lineTo(X(cx + sx), Y(cy + 3));
        ctx.moveTo(X(cx + sx) + 1.2 * k, Y(cy)); ctx.arc(X(cx + sx), Y(cy), 1.2 * k, 0, 2 * Math.PI);
        ctx.stroke();
      }
      if (it && it === items[sel]) {
        ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = Math.max(3, 0.7 * k);
        ctx.strokeRect(x0 - 2, y0 - 2, size + 4, size + 4);
      }
    });
    $("#m_capSheet").textContent = `Hoja ${page + 1} de ${pages} · ${s.nombre}`;
    $("#m_prevPage").disabled = page === 0;
    $("#m_nextPage").disabled = page >= pages - 1;
  }

  /* ───────── Encuadre ───────── */
  const VIEW = { size: 560, win: 400 };
  function frameGeom() { const o = (VIEW.size - VIEW.win) / 2; return { o, win: VIEW.win }; }

  function drawFrame() {
    const cv = $("#m_cv"), ctx = cv.getContext("2d"), it = items[sel];
    ctx.fillStyle = "#0d1014"; ctx.fillRect(0, 0, cv.width, cv.height);
    const { o, win } = frameGeom();
    const res = $("#m_res");
    res.classList.remove("low");
    if (!it) {
      ctx.fillStyle = "#8b96a4"; ctx.font = "600 17px system-ui"; ctx.textAlign = "center";
      ctx.fillText("Añade fotos para encuadrarlas", VIEW.size / 2, VIEW.size / 2);
      res.textContent = ""; $("#m_capFrame").textContent = "Encuadre";
      drawMagnet(null, null);
      return;
    }
    $("#m_capFrame").textContent = `Encuadre · ${it.nombre}`;
    $("#m_zoomOut").textContent = `${fmt(it.zoom, 2)}×`;
    const im = image(it.id);
    if (!ready(im)) { res.textContent = im.broken ? "Esta foto ya no está en la app: quítala de la hoja." : "Cargando…"; drawMagnet(null, null); return; }
    paintPhoto(ctx, it, im, o, o, win);
    const L = lado(), S = L + 2 * BLEED, r = kit().radio ?? 4, kk = win / S, inset = BLEED * kk;
    // Fuera del cuadrado: oscuro. Sangrado (entre el cuadrado y el corte): algo oscuro.
    ctx.fillStyle = "rgba(13,16,20,.72)";
    ctx.beginPath(); ctx.rect(0, 0, cv.width, cv.height); ctx.rect(o, o, win, win); ctx.fill("evenodd");
    ctx.save();
    ctx.beginPath(); ctx.rect(o, o, win, win);
    if (ctx.roundRect) ctx.roundRect(o + inset, o + inset, win - 2 * inset, win - 2 * inset, r * kk);
    ctx.fillStyle = "rgba(13,16,20,.45)"; ctx.fill("evenodd");
    ctx.restore();
    ctx.setLineDash([6, 5]); ctx.strokeStyle = "#fbbf24"; ctx.lineWidth = 2;
    rrect(ctx, o + inset, o + inset, win - 2 * inset, win - 2 * inset, r * kk); ctx.stroke();
    ctx.setLineDash([]); ctx.strokeStyle = "rgba(255,255,255,.35)"; ctx.lineWidth = 1;
    ctx.strokeRect(o + .5, o + .5, win - 1, win - 1);
    const b = cropBox(it, im), d = dpiOf(it, im);
    if (d < MIN_DPI) {
      res.classList.add("low");
      res.textContent = `⚠ Baja resolución: ${fmt(d, 0)} ppp a ${fmt(S)} mm (${b.side} px de lado). Se verá borrosa; quita zoom o usa una foto más grande (300 ppp son unos ${Math.ceil((MIN_DPI * S) / 25.4)} px).`;
    } else res.textContent = `Resolución al imprimir: ${fmt(d, 0)} ppp (${b.side} px de lado para ${fmt(S)} mm con el sangrado). Arrastra para mover y usa la rueda o el zoom para acercar.`;
    drawMagnet(it, im);
  }

  /* El imán terminado: lo de dentro de la línea de corte, con las esquinas redondeadas y un brillo de acrílico. */
  function drawMagnet(it, im) {
    const cv = $("#m_magnet"), ctx = cv.getContext("2d"), n = cv.width, pad = 14, size = n - 2 * pad;
    ctx.clearRect(0, 0, n, n);
    const L = lado(), S = L + 2 * BLEED, r = ((kit().radio ?? 4) / L) * size;
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 12; ctx.shadowOffsetY = 4;
    rrect(ctx, pad, pad, size, size, r); ctx.fillStyle = "#fff"; ctx.fill();
    ctx.restore();
    ctx.save();
    rrect(ctx, pad, pad, size, size, r); ctx.clip();
    if (it && im) { const full = (size * S) / L, off = pad - (BLEED / L) * size; paintPhoto(ctx, it, im, off, off, full); }
    const g = ctx.createLinearGradient(pad, pad, pad + size, pad + size);
    g.addColorStop(0, "rgba(255,255,255,.42)"); g.addColorStop(0.38, "rgba(255,255,255,.08)"); g.addColorStop(0.5, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.fillRect(pad, pad, size, size);
    ctx.restore();
    rrect(ctx, pad + .5, pad + .5, size - 1, size - 1, r); ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 1.5; ctx.stroke();
  }

  function drawAll() { if (!on) return; drawFit(); drawFrame(); drawSheet(); }

  function changed(it, im) { clamp(it, im); saveItems(); drawFrame(); drawSheet(); queueList(); }
  let listTimer;
  const queueList = () => { clearTimeout(listTimer); listTimer = setTimeout(renderList, 250); };

  function bindFrame() {
    const cv = $("#m_cv");
    let drag = null;
    const scale = () => cv.width / cv.getBoundingClientRect().width;
    cv.addEventListener("pointerdown", (e) => {
      const it = items[sel], im = it && image(it.id);
      if (!ready(im)) return;
      drag = { x: e.clientX, y: e.clientY };
      cv.setPointerCapture(e.pointerId);
    });
    cv.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const it = items[sel], im = image(it.id), b = cropBox(it, im), k = VIEW.win / b.side, s = scale();
      it.cx -= ((e.clientX - drag.x) * s) / (k * b.W);
      it.cy -= ((e.clientY - drag.y) * s) / (k * b.H);
      drag = { x: e.clientX, y: e.clientY };
      changed(it, im);
    });
    const end = () => (drag = null);
    cv.addEventListener("pointerup", end);
    cv.addEventListener("pointercancel", end);
    cv.addEventListener("wheel", (e) => {
      const it = items[sel], im = it && image(it.id);
      if (!ready(im)) return;
      e.preventDefault();
      it.zoom = Math.min(ZMAX, Math.max(1, it.zoom * Math.exp(-e.deltaY * 0.0015)));
      $("#m_zoom").value = it.zoom;
      changed(it, im);
    }, { passive: false });
    $("#m_zoom").addEventListener("input", () => {
      const it = items[sel], im = it && image(it.id);
      if (!ready(im)) return;
      it.zoom = Number($("#m_zoom").value);
      changed(it, im);
    });
    const rotate = (d) => {
      const it = items[sel], im = it && image(it.id);
      if (!ready(im)) return;
      it.girar = (it.girar + d + 360) % 360;
      it.cx = 0.5; it.cy = 0.5;
      changed(it, im);
    };
    $("#m_rotL").addEventListener("click", () => rotate(-90));
    $("#m_rotR").addEventListener("click", () => rotate(90));
    $("#m_center").addEventListener("click", () => {
      const it = items[sel], im = it && image(it.id);
      if (!ready(im)) return;
      Object.assign(it, { zoom: 1, cx: 0.5, cy: 0.5 });
      $("#m_zoom").value = 1;
      changed(it, im);
    });
    $("#m_sheet").addEventListener("click", (e) => {
      const s = sheet();
      if (!s?.por_hoja) return;
      const cv2 = $("#m_sheet"), rect = cv2.getBoundingClientRect();
      const mmx = ((e.clientX - rect.left) / rect.width) * s.ancho_mm, mmy = s.alto_mm - ((e.clientY - rect.top) / rect.height) * s.alto_mm;
      const half = lado() / 2 + BLEED, all = slots(s.por_hoja);
      s.centros_mm.forEach(([cx, cy], j) => {
        const it = all[page * s.por_hoja + j];
        if (it && Math.abs(mmx - cx) <= half && Math.abs(mmy - cy) <= half) select(items.indexOf(it));
      });
    });
    $("#m_prevPage").addEventListener("click", () => { page--; drawSheet(); });
    $("#m_nextPage").addEventListener("click", () => { page++; drawSheet(); });
  }

  /* ───────── PDF y útiles ───────── */
  async function makePdf(blank) {
    const btn = blank ? $("#m_blank") : $("#m_pdf");
    if (!blank && !items.length) { toast("Añade al menos una foto (o descarga la hoja sin fotos para probar los útiles).", "err"); return; }
    btn.disabled = true; btn.classList.add("busy");
    try {
      const body = { ...kit(), papel: paper(), rellenar: $("#m_rellenar").checked,
        fotos: blank ? [] : items.map((it) => ({ imagen_id: it.id, girar: it.girar, zoom: it.zoom, centro_x: it.cx, centro_y: it.cy, copias: it.copias })) };
      const r = await (await api("POST", "/api/imanes/pdf", body)).json();
      const a = document.createElement("a");
      a.href = r.pdf; a.download = ""; document.body.append(a); a.click(); a.remove();
      const low = r.baja_resolucion.map((x) => `«${x.nombre}» (${x.ppp} ppp)`);
      const msg = blank ? `Hoja de prueba lista (${r.por_hoja} recuadros).`
        : `PDF listo: ${r.fotos} imanes en ${r.hojas} ${r.hojas === 1 ? "hoja" : "hojas"}.`;
      toast(low.length ? `${msg} Ojo, baja resolución: ${low.join(", ")}.` : msg, low.length ? "err" : "ok");
    } catch (e) { toast(e.message, "err"); }
    finally { btn.disabled = false; btn.classList.remove("busy"); }
  }

  function view3d() {
    const q = query(), url = `/api/imanes/utiles/todo.stl?${q}`;
    window.Visor?.open({ url, name: `Útiles para imanes de ${fmt(lado())} mm`, mode: "relief", download: url,
      download3mf: `/api/imanes/utiles.3mf?${q}`, settings: `/api/imanes/utiles.txt?${q}` });
  }

  /* ───────── Modo ───────── */
  function setOn(v) {
    on = v;
    document.body.classList.toggle("modo-iman", v);
    $("#modeIman").setAttribute("aria-pressed", String(v));
    store.set("imanes.on", v);
    if (v) {
      $$("#modeSeg .segbtn").forEach((b) => b.id !== "modeIman" && b.setAttribute("aria-pressed", "false"));
      $("#views").hidden = false;
      $("#empty").hidden = true;
      $("#title").textContent = "Imanes de nevera";
      fetchLayout();
      renderList();
    } else {
      $("#views").hidden = !current;
      $("#empty").hidden = !!current;
      $("#title").textContent = current ? current.nombre : "Sin imagen";
      $("#summary").textContent = "";
    }
  }

  function init() {
    const btn = document.createElement("button");
    btn.id = "modeIman"; btn.type = "button"; btn.className = "segbtn"; btn.textContent = "Imán de nevera";
    btn.setAttribute("aria-pressed", "false");
    btn.title = "Hoja de fotos en PDF para imanes de nevera de acrílico, con los útiles de corte y montaje";
    $("#modeSeg").append(btn);
    btn.addEventListener("click", () => setOn(true));
    $$("#modeSeg .segbtn").forEach((b) => b !== btn && b.addEventListener("click", () => on && setOn(false)));

    restoreFields();
    for (const id of Object.keys(FIELDS)) $(`#${id}`).addEventListener("input", () => { saveFields(); relayout(); });
    $("#m_papelsel").addEventListener("change", () => { saveFields(); page = 0; drawAll(); });
    $("#m_rellenar").addEventListener("change", () => { saveFields(); drawAll(); });
    $("#m_reset").addEventListener("click", () => {
      for (const [id, v] of Object.entries(DEFAULTS)) $(`#${id}`).value = v;
      saveFields(); fetchLayout();
      toast("Medidas del kit: 50 mm, radio 4 mm y cruces a 35 mm del centro.", "ok");
    });
    $("#m_add").addEventListener("click", () => $("#m_files").click());
    $("#m_files").addEventListener("change", (e) => { uploadFiles(e.target.files); e.target.value = ""; });
    $("#m_pdf").addEventListener("click", () => makePdf(false));
    $("#m_blank").addEventListener("click", () => makePdf(true));
    $("#m_view3d").addEventListener("click", view3d);
    bindFrame();

    // En este modo, tocar una imagen de la lista la añade a la hoja (o la selecciona si ya está).
    $("#images").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!on || !b) return;
      const meta = images.find((m) => b.style.backgroundImage.includes(`/${m.id}/`));
      if (meta && addItem(meta)) toast(`«${meta.nombre}» añadida a la hoja.`, "ok");
    });
    // Arrastrar fotos a la ventana: todas van a la hoja.
    addEventListener("drop", (e) => {
      if (!on || !e.dataTransfer?.files.length || /\.(stl|3mf)$/i.test(e.dataTransfer.files[0].name)) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      try { dragDepth = 0; } catch { /* app.js sin contador */ }
      $("#dropzone").hidden = true;
      uploadFiles(e.dataTransfer.files);
    }, true);

    updateLinks();
    if (store.get("imanes.on")) setOn(true);
  }
  init();

  return { setOn };
})();
window.Iman = Iman;
