/* Bajorrelieves: moneda o medallón a partir de la foto abierta. Usa $, $$, api, toast, store, current y crop de app.js. */
const Relieve = (() => {
  const FIELDS = ["r_metodo", "r_fondo", "r_forma", "r_ancho", "r_alto", "r_base", "r_relieve", "r_aro", "r_campo", "r_compresion", "r_textura",
    "r_zoom", "r_cx", "r_cy", "r_colgar", "r_colgar_ancho", "r_colgar_agujero", "r_resolucion"];
  let on = false, models = null, poll = null;

  const read = (id) => { const e = $(`#${id}`); return e.type === "checkbox" ? e.checked : e.type === "range" || e.type === "number" ? Number(e.value) : e.value; };
  const save = () => store.set("relieve", Object.fromEntries(FIELDS.map((id) => [id, read(id)])));
  function restore() {
    const saved = store.get("relieve") || {};
    for (const id of FIELDS) if (id in saved) { const e = $(`#${id}`); if (e.type === "checkbox") e.checked = !!saved[id]; else e.value = saved[id]; }
  }

  function refresh() {
    $("[data-r-alto]").hidden = $("#r_forma").value === "circulo";
    $$("[data-r-hang]").forEach((e) => (e.hidden = !$("#r_colgar").checked));
    $$("output[data-for^='r_']").forEach((o) => (o.textContent = Number($(`#${o.dataset.for}`).value).toFixed(2)));
  }

  function setMode(relief) {
    on = relief;
    document.body.classList.toggle("modo-relieve", on);
    $("#modeLito").setAttribute("aria-pressed", String(!on));
    $("#modeRelieve").setAttribute("aria-pressed", String(on));
    $("#btnStl").hidden = on;
    $("#btnRelieve").hidden = !on;
    $("#btnRelieve").disabled = !current;
    store.set("modo", on ? "relieve" : "lito");
    if (on) loadModels();
  }

  /* ───────── Modelos de IA ───────── */
  const mb = (n) => (n / 1048576).toLocaleString("es-ES", { maximumFractionDigits: 0 });
  async function loadModels() {
    try { models = await (await api("GET", "/api/modelos")).json(); } catch (e) { return; }
    drawModels();
    clearTimeout(poll);
    if (models.modelos.some((m) => m.descargando)) poll = setTimeout(loadModels, 1500);
  }
  function drawModels() {
    const box = $("#modelBox");
    if (!models.ort) { box.innerHTML = '<p class="hint">Falta onnxruntime: cierra la app y vuelve a abrirla con iniciar.bat para instalarlo. Mientras, solo funciona «Sin IA».</p>'; return; }
    box.innerHTML = "";
    for (const m of models.modelos) {
      const row = document.createElement("div");
      row.className = "modelrow";
      const label = document.createElement("span");
      label.textContent = `${m.nombre} · ${m.mb} MB`;
      row.append(label);
      if (m.instalado) { const ok = document.createElement("b"); ok.textContent = "✓ instalado"; row.append(ok); }
      else if (m.descargando) { const pc = m.total ? Math.round((100 * m.hecho) / m.total) : 0; const b = document.createElement("b"); b.textContent = `descargando ${pc} % (${mb(m.hecho)} MB)`; row.append(b); }
      else {
        const b = document.createElement("button");
        b.type = "button"; b.className = "btn small"; b.textContent = "Descargar";
        b.title = m.licencia;
        b.addEventListener("click", async () => {
          try { await api("POST", `/api/modelos/${m.clave}/instalar`); loadModels(); } catch (e) { toast(e.message, "err"); }
        });
        row.append(b);
        if (m.error) { const er = document.createElement("small"); er.textContent = m.error; row.append(er); }
      }
      box.append(row);
    }
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = "Se descargan una sola vez; después todo funciona sin internet. El grande es para uso personal (CC-BY-NC).";
    box.append(hint);
    const sel = $("#r_metodo");
    const have = (k) => models.modelos.find((m) => m.clave === k)?.instalado;
    if (!store.get("relieve")?.r_metodo) sel.value = models.predeterminado;
    if (sel.value !== "sin-ia" && !have(sel.value)) sel.title = "Este modelo aún no está descargado";
    else sel.title = "";
  }

  /* ───────── Generar ───────── */
  async function generate() {
    if (!current) return;
    const btn = $("#btnRelieve");
    btn.disabled = true; btn.classList.add("busy");
    const label = btn.lastChild.textContent;
    btn.lastChild.textContent = " Calculando relieve…";
    const circle = read("r_forma") === "circulo";
    try {
      const info = await (await api("POST", "/api/bajorrelieves", {
        imagen_id: current.id, metodo: read("r_metodo"), fondo: read("r_fondo"), forma: read("r_forma"),
        ancho: read("r_ancho"), alto: circle ? read("r_ancho") : read("r_alto"), base: read("r_base"), relieve: read("r_relieve"),
        aro: read("r_aro"), campo: read("r_campo"), compresion: read("r_compresion"), textura: read("r_textura"),
        girar: crop.rot, zoom: read("r_zoom"), centro_x: read("r_cx"), centro_y: read("r_cy"),
        colgar: read("r_colgar"), colgar_ancho: read("r_colgar_ancho"), colgar_agujero: read("r_colgar_agujero"), resolucion: read("r_resolucion"),
      })).json();
      $("#imgLuz").src = info.luz;
      $("#imgProf").src = info.profundidad;
      const [w, h, d] = info.medidas_mm.map((n) => n.toLocaleString("es-ES", { maximumFractionDigits: 1 }));
      $("#summary").textContent = [info.nota, `${info.dispositivo}, ${info.segundos} s`].filter(Boolean).join(" · ");
      window.Visor.open({
        url: info.vista, name: current.nombre, mode: "relief",
        details: `${w} × ${h} × ${d} mm · ${info.triangulos.toLocaleString("es-ES")} triángulos · unos ${info.gramos} g de PLA`,
        download: info.stl, download3mf: info.tresmf, settings: info.ajustes, tMax: info.medidas_mm[2],
      });
    } catch (e) { toast(e.message, "err"); }
    finally { btn.lastChild.textContent = label; btn.classList.remove("busy"); btn.disabled = !current; }
  }

  function init() {
    restore();
    refresh();
    for (const id of FIELDS) $(`#${id}`).addEventListener("input", () => { refresh(); save(); });
    $("#modeLito").addEventListener("click", () => setMode(false));
    $("#modeRelieve").addEventListener("click", () => setMode(true));
    $("#btnRelieve").addEventListener("click", generate);
    setMode(store.get("modo") === "relieve");
  }
  init();

  return { onSelect() { $("#btnRelieve").disabled = !current; $("#imgLuz").removeAttribute("src"); $("#imgProf").removeAttribute("src"); } };
})();
window.Relieve = Relieve;
