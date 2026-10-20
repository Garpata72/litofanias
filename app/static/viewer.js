/* Litofanías — visor 3D de STL y 3MF. three.js va incluido en /vendor: no necesita internet.
   Dos luces: «Relieve» (luz frontal, se ve la superficie) y «Contraluz» (simula la pieza encendida:
   la luz que pasa decae con el grosor, medido como altura sobre la cara trasera). */
import * as THREE from "three";
import { OrbitControls } from "/vendor/three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "/vendor/three/examples/jsm/loaders/STLLoader.js";
import { ThreeMFLoader } from "/vendor/three/examples/jsm/loaders/3MFLoader.js";

const $ = (s) => document.querySelector(s);
const ABSORB = 1.1;   // por mm, el mismo valor que la vista previa 2D

const box = $("#v3d");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
box.append(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 5000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xf4f1ea, 0x30343a, 1.1));
const key = new THREE.DirectionalLight(0xffffff, 1.6);
scene.add(camera);
key.position.set(-0.6, 0.8, 1);
camera.add(key);   // la luz frontal sigue a la cámara

const reliefMat = new THREE.MeshStandardMaterial({ color: 0xece6da, roughness: 0.75, metalness: 0, side: THREE.DoubleSide });
const litMat = new THREE.ShaderMaterial({
  side: THREE.DoubleSide,
  uniforms: { zBack: { value: 0 }, tMin: { value: 0.8 }, absorb: { value: ABSORB } },
  vertexShader: `
    varying vec3 vPos; varying vec3 vNormal;
    void main() {
      vec4 w = modelMatrix * vec4(position, 1.0);
      vPos = w.xyz;
      vNormal = normalize(mat3(modelMatrix) * normal);
      gl_Position = projectionMatrix * viewMatrix * w;
    }`,
  fragmentShader: `
    uniform float zBack; uniform float tMin; uniform float absorb;
    varying vec3 vPos; varying vec3 vNormal;
    void main() {
      vec3 warm = vec3(1.0, 0.87, 0.66);
      float front = gl_FrontFacing ? vNormal.z : -vNormal.z;
      if (front < 0.3) { gl_FragColor = vec4(warm * 0.06, 1.0); return; }   // cantos y trasera
      float t = max(vPos.z - zBack, 0.0);
      float light = exp(-absorb * (t - tMin));
      gl_FragColor = vec4(warm * clamp(light, 0.0, 1.0), 1.0);
    }`,
});

let root = null;
let mode = "relief";
let current = null;

function resize() {
  const w = box.clientWidth, h = box.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(box);

function loop() {
  if ($("#lb").hidden) return;
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

function setMode(m) {
  mode = m;
  $("#mRelief").setAttribute("aria-pressed", m === "relief");
  $("#mLit").setAttribute("aria-pressed", m === "lit");
  scene.background = new THREE.Color(m === "lit" ? 0x07090b : 0x1a1f26);
  root?.traverse((o) => { if (o.isMesh) o.material = m === "lit" ? litMat : reliefMat; });
}

function fit() {
  if (!root) return;
  const b = new THREE.Box3().setFromObject(root);
  const size = b.getSize(new THREE.Vector3());
  const dist = (Math.max(size.x, size.y) / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.25 + size.z;
  camera.near = dist / 100;
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
  camera.position.set(0, -dist * 0.25, dist);
  controls.update();
}

function clear() {
  if (!root) return;
  scene.remove(root);
  root.traverse((o) => o.geometry?.dispose());
  root = null;
}

/* Centra la pieza, deja la cara trasera en su sitio y calcula el grosor mínimo de la cara iluminada. */
function place(obj) {
  obj.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(obj);
  const c = b.getCenter(new THREE.Vector3());
  obj.position.sub(c);
  obj.updateMatrixWorld(true);
  const zBack = b.min.z - c.z;

  let tMin = Infinity;
  const p = new THREE.Vector3(), n = new THREE.Vector3(), nm = new THREE.Matrix3();
  let triangles = 0;
  obj.traverse((o) => {
    if (!o.isMesh) return;
    let g = o.geometry;
    if (g.index) {   // 3MF: vértices compartidos; se separan para que las caras planas se vean planas
      g = o.geometry = g.toNonIndexed();
      g.computeVertexNormals();
    } else if (!g.attributes.normal) g.computeVertexNormals();
    triangles += g.attributes.position.count / 3;
    nm.getNormalMatrix(o.matrixWorld);
    const pos = g.attributes.position, nor = g.attributes.normal;
    const step = Math.max(1, Math.floor(pos.count / 400000));
    for (let i = 0; i < pos.count; i += step) {
      n.fromBufferAttribute(nor, i).applyMatrix3(nm).normalize();
      if (n.z < 0.5) continue;
      p.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      tMin = Math.min(tMin, p.z - zBack);
    }
  });
  litMat.uniforms.zBack.value = zBack;
  litMat.uniforms.tMin.value = Number.isFinite(tMin) ? tMin : 0.8;
  return { size: b.getSize(new THREE.Vector3()), triangles };
}

async function load({ url, file }) {
  const isMF = (file?.name || url).toLowerCase().includes(".3mf");
  const data = file ? await file.arrayBuffer() : await (await fetch(url)).arrayBuffer();
  if (isMF) return new ThreeMFLoader().parse(data);
  return new THREE.Mesh(new STLLoader().parse(data), reliefMat);
}

async function open(opts) {
  current = opts;
  $("#lb").hidden = false;
  $("#lbName").textContent = opts.name || "Modelo 3D";
  $("#lbInfo").textContent = opts.details || "";
  const dl = $("#lbDownload");
  dl.hidden = !opts.download;
  if (opts.download) dl.href = opts.download;
  $("#lbMsg").hidden = false;
  $("#lbMsg").textContent = "Cargando el modelo…";
  clear();
  resize();
  requestAnimationFrame(loop);
  try {
    const obj = await load(opts);
    if (current !== opts) return;   // se abrió otro mientras cargaba
    root = obj;
    scene.add(root);
    const { size, triangles } = place(root);
    if (!opts.details) {
      const f = (v) => v.toLocaleString("es-ES", { maximumFractionDigits: 1 });
      $("#lbInfo").textContent = `${f(size.x)} × ${f(size.y)} × ${f(size.z)} mm · ${Math.round(triangles).toLocaleString("es-ES")} triángulos`;
    }
    setMode(opts.download ? "lit" : mode);
    fit();
    $("#lbMsg").hidden = true;
  } catch (e) {
    console.error(e);
    $("#lbMsg").textContent = "No se ha podido abrir el modelo. ¿Es un STL o 3MF válido?";
  }
}

function close() {
  $("#lb").hidden = true;
  current = null;
  clear();
}

$("#mRelief").addEventListener("click", () => setMode("relief"));
$("#mLit").addEventListener("click", () => setMode("lit"));
$("#lbFit").addEventListener("click", fit);
$("#lbClose").addEventListener("click", close);
addEventListener("keydown", (e) => {
  if ($("#lb").hidden || e.target.matches("input, select")) return;
  if (e.key === "Escape") close();
  else if (e.key === "r" || e.key === "R") setMode("relief");
  else if (e.key === "l" || e.key === "L") setMode("lit");
  else if (e.key === "f" || e.key === "F") fit();
});

setMode("relief");
window.Visor = { open, close };
