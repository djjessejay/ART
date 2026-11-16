// Rendert .glb-Dateien mit three.js (GLTFLoader) in headless Chromium zu PNG-Vorschauen.
// Nutzung: node render_glb.js <out_dir> <a.glb> [b.glb ...]
// Erwartet three und playwright im NODE_PATH. Kamera: isometrische Schraegsicht, fester Winkel,
// damit Vorschauen reproduzierbar und vergleichbar bleiben.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

// three exportiert package.json nicht: Paketwurzel ueber den Haupteintrag ermitteln
const threeRoot = path.resolve(path.dirname(require.resolve('three')), '..');
const [outDir, ...files] = process.argv.slice(2);
const W = 1600, H = 900;

const page = `<!doctype html><html><body style="margin:0;background:#05060f">
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const r = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
r.setSize(${W}, ${H}); r.setClearColor(0x05060f); r.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(r.domElement);
window.renderGlb = async (url) => {
  const g = await new GLTFLoader().loadAsync(url);
  const scene = new THREE.Scene(); scene.add(g.scene);
  const box = new THREE.Box3().setFromObject(g.scene), size = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3()), d = Math.max(size.x, size.z);
  const cam = new THREE.PerspectiveCamera(30, ${W}/${H}, 0.1, d * 10);
  cam.position.set(c.x + d * 0.38, c.y + d * 0.68, c.z + d * 0.98); cam.lookAt(c);
  r.render(scene, cam);
  let tris = 0; g.scene.traverse(o => { if (o.isMesh) tris += o.geometry.index.count / 3; });
  return { tris, size: [size.x, size.y, size.z] };
};
window.ready = true;
</script></body></html>`;

const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url);
  let f;
  if (u === '/') { res.setHeader('content-type', 'text/html'); return res.end(page); }
  if (u.startsWith('/three/')) f = path.join(threeRoot, u.slice(7));
  else if (u.startsWith('/glb/')) f = files.find(x => path.basename(x) === u.slice(5));
  if (!f || !fs.existsSync(f)) { res.statusCode = 404; return res.end(); }
  res.setHeader('content-type', f.endsWith('.js') ? 'text/javascript' : 'model/gltf-binary');
  fs.createReadStream(f).pipe(res);
});

(async () => {
  await new Promise(ok => server.listen(0, '127.0.0.1', ok));
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => window.ready === true);
  fs.mkdirSync(outDir, { recursive: true });
  for (const f of files) {
    const info = await p.evaluate(u => window.renderGlb(u), `/glb/${path.basename(f)}`);
    const out = path.join(outDir, path.basename(f, '.glb') + '.png');
    await p.locator('canvas').screenshot({ path: out });
    console.log(`${path.basename(out)}  tris=${info.tris}  size=${info.size.map(v => v.toFixed(1)).join('x')}`);
  }
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
