// The WebGL stage: the kitchen twin, the recorded episode, the LiDAR scan, and the scroll-driven camera.
//
// Frames: all geometry lives under ROOT in MuJoCo coordinates (z up, metres). ROOT is rotated -90 deg about x once,
// so three's y-up camera and lights are the only things expressed in three coordinates.
//
// Ported from UltraUI (mechanics only, retuned):
//   scroll-3d-camera-path-journey / three-scroll-sync-camera : CatmullRom camera + look-at paths driven by one progress
//                                                              value, dwell at shots via eased segments, render on the shared ticker
//   scroll-product-explode-assembly                          : per-part explode vectors, staged out and back (fixtures, arm)
//   dither-shader / halftone                                 : Bayer 4x4 ordered dither used for the scan points, the build-up
//                                                              of the twin and distance fade (no alpha sorting needed)
//   three-mobile-fallback-strategy                           : DPR cap, adaptive resolution, WebGL-less fallback hook
//   compare (aceternity)                                     : scan versus twin as two scissor passes of the same camera
import * as THREE from 'three';
import { OrbitControls } from '../vendor/three/OrbitControls.js';
import { buildBody, disposeBody } from './geom.js';
import { clamp, lerp, damp, easeInOutCubic, smoothstep } from './util.js';

const mj = (x, y, z, o = new THREE.Vector3()) => o.set(x, z, -y);
const ROBOT = ['robot_base', 'link1', 'link2', 'link3', 'link4', 'link5', 'link6', 'link7', 'hand', 'finger_l', 'finger_r'];
const ROOM_H = 2.4;

// ---------- shader chunks ----------
const GLSL_COMMON = /* glsl */ `
float bayer4(vec2 p){
  int i = int(mod(p.x,4.0)) + int(mod(p.y,4.0))*4;
  const float m[16] = float[16](0.,8.,2.,10., 12.,4.,14.,6., 3.,11.,1.,9., 15.,7.,13.,5.);
  return (m[i]+0.5)/16.0;
}`;
const GLSL_HATCH = /* glsl */ `
float lines(float v, float w){
  float f = abs(fract(v)-0.5);
  float fw = fwidth(v);
  float aa = fw*0.75;
  return (1.0 - smoothstep(w-aa, w+aa, f)) * (1.0 - smoothstep(0.3, 0.6, fw));
}
float hatch(vec3 p, float m){
  if (m < 0.5) return 0.0;
  if (m < 1.5) return lines((p.x+p.z)*42.0, 0.06);          // wood: long grain
  if (m < 2.5) return lines((p.x-p.z)*64.0, 0.07);          // stone: diagonal hatch
  if (m < 3.5) return lines(p.x*14.0, 0.02);                // panel: board joints
  return 0.0;
}`;

// ---------- scan point cloud ----------
const POINT_VS = /* glsl */ `
attribute vec3 aScatter; attribute float aRand; attribute float aSt; attribute float aDist; attribute vec3 aCol;
uniform float uSettle, uPx, uSize, uFront, uMaxR;
varying float vLum; varying float vBand; varying float vDepth;
void main(){
  float k = clamp((uSettle - aRand*0.5)/0.5, 0.0, 1.0);
  float e = 1.0 - pow(1.0-k, 3.0);
  vec3 p = position + aScatter*(1.0-e);
  vec4 mv = modelViewMatrix*vec4(p,1.0);
  gl_Position = projectionMatrix*mv;
  float d = max(-mv.z, 0.4);
  gl_PointSize = clamp(uSize*uPx/d*(0.8+0.5*aRand), 2.0*uPx, 5.0*uPx);
  vLum = dot(aCol, vec3(0.299,0.587,0.114));
  float local = uFront - aSt;
  float ring = abs(aDist/uMaxR - local);
  vBand = (local > -0.02 && local < 1.12) ? (1.0 - smoothstep(0.0, 0.07, ring)) : 0.0;
  vDepth = d;
}`;
const POINT_FS = /* glsl */ `
uniform vec3 uInk, uSignal; uniform float uAlpha;
varying float vLum; varying float vBand; varying float vDepth;
${GLSL_COMMON}
void main(){
  vec2 c = gl_PointCoord-0.5;
  if (dot(c,c) > 0.25) discard;
  float a = uAlpha * (1.0 - 0.5*smoothstep(10.0, 22.0, vDepth));
  if (a < bayer4(gl_FragCoord.xy)) discard;
  vec3 col = mix(uInk*(0.62+0.38*vLum), uSignal, vBand);
  gl_FragColor = vec4(col,1.0);
  #include <colorspace_fragment>
}`;

function mulberry(a) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ---------- highlight overlay for hover/selection ----------
class Highlight {
  constructor(opacity, edgeOpacity) {
    this.fill = new THREE.Mesh(undefined, new THREE.MeshBasicMaterial({ transparent: true, opacity, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }));
    this.edge = new THREE.LineSegments(undefined, new THREE.LineBasicMaterial({ transparent: true, opacity: edgeOpacity, depthTest: false }));
    this.fill.layers.set(2); this.edge.layers.set(2);
    this.fill.renderOrder = 5; this.edge.renderOrder = 6;
    this.name = null;
  }
  setColor(c) { this.fill.material.color.copy(c); this.edge.material.color.copy(c); }
  attach(entry) {
    if (!entry || !entry.geo) return this.detach();
    this.name = entry.name;
    this.fill.geometry = entry.geo.solid; this.edge.geometry = entry.geo.edges;
    entry.group.add(this.fill); entry.group.add(this.edge);
  }
  detach() { this.name = null; this.fill.removeFromParent(); this.edge.removeFromParent(); }
}

export class Stage {
  constructor({ canvas, wrap, data, reduced = false, coarse = false }) {
    this.canvas = canvas; this.wrap = wrap; this.data = data; this.reduced = reduced; this.coarse = coarse;
    const gl2 = canvas.getContext('webgl2', { antialias: true });
    if (!gl2) throw new Error('webgl2 unavailable');
    this.renderer = new THREE.WebGLRenderer({ canvas, context: gl2, antialias: true });
    this.prCap = Math.min(window.devicePixelRatio || 1, coarse ? 1.5 : 2);
    this.pr = this.prCap;
    this.renderer.setPixelRatio(this.pr);
    this.renderer.toneMapping = THREE.NoToneMapping;

    this.scene = new THREE.Scene();
    this.root = new THREE.Group(); this.root.rotation.x = -Math.PI / 2; this.scene.add(this.root);
    this.camera = new THREE.PerspectiveCamera(36, 1.6, 0.05, 60);
    this.camera.layers.enableAll();
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.12;
    this.controls.maxPolarAngle = Math.PI * 0.495; this.controls.minDistance = 0.6; this.controls.maxDistance = 14;
    this.controls.zoomSpeed = 0.8;
    // tour mode: a mouse drag on the canvas hands the camera to the reader; touch and wheel keep scrolling the page
    // The camera belongs to the scroll until the twin has been built; before that a drag would freeze the tour.
    this.controls.enabled = false; this.controls.enableZoom = false; this._orbitable = false;
    canvas.style.touchAction = 'pan-y';
    this.controls.addEventListener('start', () => { if (this.mode === 'tour') { this.controls.target.copy(this._look); this._pendingExplore = true; } });
    this.controls.addEventListener('change', () => { if (this._pendingExplore && this.mode === 'tour') { this._pendingExplore = false; this._enterExplore(); } });
    this.controls.addEventListener('end', () => { this._pendingExplore = false; });

    // journey state written by scroll.js, read here
    this.J = { shotU: 0, front: 0, build: 0, scanA: 1, wire: 0, dims: 0, exF: 0, exA: 0, compare: 0, robot: false, people: false, feeds: 0, autoplay: false };
    this.user = { solid: true, wire: false, scan: false, people: true };
    this.cmpX = 0.5;
    this.mode = 'tour'; this.blend = 1; this.lost = false; this._camReady = false; this._feedDirty = true;
    this.visible = true;
    this.u = 0;
    this.par = { x: 0, y: 0, tx: 0, ty: 0 };
    this.cb = {};
    this.theme = null;

    this.time = 0; this.playing = false; this.speed = 1; this.hold = 0; this.autoplayed = false;
    this.poseDirty = true;
    this.dyn = []; this.exploders = []; this.bodies = new Map(); this.personBodies = new Map(); this.camNodes = new Map();
    this.pickables = [];
    this.settle = reduced ? 1 : 0;
    this.frameState = { f: 0, t: 0, dur: 1, n: 1, joints: new Float32Array(8), live: 0, livePair: '' };
    this._acc = 0; this._cbAcc = 0; this._perfN = 0; this._perfT = 0; this._perfBad = 0; this._perfGood = 0;

    this._v = new THREE.Vector3(); this._v2 = new THREE.Vector3(); this._look = new THREE.Vector3(); this._pos = new THREE.Vector3();
    this._retPos = new THREE.Vector3(); this._retLook = new THREE.Vector3();
    this._q0 = new THREE.Quaternion(); this._q1 = new THREE.Quaternion();
    this._ndc = new THREE.Vector2(); this.ray = new THREE.Raycaster();
    this._focus = null;

    this._initMaterials();
    this._buildTwin();
    this._buildScan();
    this._buildDims();
    this._buildLights();
    this.hover = new Highlight(0.14, 0.7); this.select = new Highlight(0.3, 1);
    this.trail = this._buildTrail();
    this.clear = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ transparent: true, opacity: 1, depthTest: false }));
    this.clear.layers.set(2); this.clear.renderOrder = 7; this.clear.visible = false; this.clear.frustumCulled = false; this.root.add(this.clear);

    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(wrap);
    this.resize();
  }

  // ---------- materials ----------
  _initMaterials() {
    const sh = this.sh = {
      uPaper: { value: new THREE.Color() }, uMix: { value: 0.42 }, uHatch: { value: 0.15 }, uBuild: { value: 0 },
    };
    const patch = (m) => {
      m.onBeforeCompile = (s) => {
        s.uniforms.uPaper = sh.uPaper; s.uniforms.uMix = sh.uMix; s.uniforms.uHatch = sh.uHatch; s.uniforms.uBuild = sh.uBuild;
        s.vertexShader = s.vertexShader
          .replace('#include <common>', '#include <common>\nattribute float aMat; varying float vMat; varying vec3 vHP;')
          .replace('#include <begin_vertex>', '#include <begin_vertex>\nvMat = aMat; vHP = (modelMatrix*vec4(transformed,1.0)).xyz;');
        s.fragmentShader = s.fragmentShader
          .replace('#include <common>', `#include <common>\nuniform vec3 uPaper; uniform float uMix, uHatch, uBuild; varying float vMat; varying vec3 vHP;\n${GLSL_COMMON}\n${GLSL_HATCH}`)
          .replace('#include <color_fragment>', `#include <color_fragment>
            float edgeB = uBuild*1.12 - vHP.y/${ROOM_H.toFixed(1)};
            if (edgeB < 0.0) discard;
            if (edgeB < 0.07 && bayer4(gl_FragCoord.xy) > edgeB/0.07) discard;
            diffuseColor.rgb = mix(diffuseColor.rgb, uPaper, uMix);
            diffuseColor.rgb *= 1.0 - uHatch*hatch(vHP, vMat);`);
      };
      m.customProgramCacheKey = () => 'plan-lambert';
      return m;
    };
    this.matSolid = patch(new THREE.MeshLambertMaterial({ vertexColors: true }));
    const ink = (o) => new THREE.LineBasicMaterial({ transparent: true, opacity: o, depthWrite: false });
    this.matEdges = ink(0.62);
    // edge lines share the solid's height build-up
    this.matEdges.onBeforeCompile = (s) => {
      s.uniforms.uBuild = sh.uBuild;
      s.vertexShader = s.vertexShader.replace('#include <common>', '#include <common>\nvarying float vHy;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvHy = (modelMatrix*vec4(transformed,1.0)).y;');
      s.fragmentShader = s.fragmentShader.replace('#include <common>', '#include <common>\nuniform float uBuild; varying float vHy;').replace('void main() {', `void main() {\n if (vHy/${ROOM_H.toFixed(1)} > uBuild*1.12) discard;`);
    };
    this.matEdges.customProgramCacheKey = () => 'plan-edges';
    this.matWire = ink(0.5);
    this.matDims = new THREE.LineBasicMaterial({ transparent: true, opacity: 1, depthWrite: false });
    this.matTrail = new THREE.LineBasicMaterial({ transparent: true, opacity: 1, depthTest: false });
    this.matFloorGrid = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.16, depthWrite: false });
    this.matFloorMajor = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.34, depthWrite: false });
  }

  // a patched material without vertex colours, so material.color is the surface colour
  _plainClone(src) {
    const m = src.clone();
    m.onBeforeCompile = src.onBeforeCompile; m.customProgramCacheKey = src.customProgramCacheKey;
    if ('vertexColors' in m) m.vertexColors = false;
    return m;
  }
  _planeWithMat(w, h) {
    const g = new THREE.PlaneGeometry(w, h);
    g.setAttribute('aMat', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count), 1));
    return g;
  }

  // ---------- twin ----------
  _buildTwin() {
    const { rooms, geoms } = this.data;
    this.rooms = rooms;
    const [bx0, by0] = rooms.bounds.min, [bx1, by1] = rooms.bounds.max;
    // floor + grid (0.25 m minor, 1 m major) drawn as the plan sheet
    const floor = new THREE.Mesh(this._planeWithMat(bx1 - bx0, by1 - by0), this._plainClone(this.matSolid));
    floor.position.set((bx0 + bx1) / 2, (by0 + by1) / 2, 0.0005);
    this.floor = floor; this.root.add(floor);
    const minor = [], major = [];
    for (let x = bx0; x <= bx1 + 1e-6; x += 0.25) (Math.abs(x % 1) < 1e-6 ? major : minor).push(x, by0, 0.002, x, by1, 0.002);
    for (let y = by0; y <= by1 + 1e-6; y += 0.25) (Math.abs(y % 1) < 1e-6 ? major : minor).push(bx0, y, 0.002, bx1, y, 0.002);
    const lg = (a) => new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(a, 3));
    this.gridMinor = new THREE.LineSegments(lg(minor), this.matFloorGrid);
    this.gridMajor = new THREE.LineSegments(lg(major), this.matFloorMajor);
    this.root.add(this.gridMinor, this.gridMajor);

    // walls: individual meshes so the walls facing away from the camera can ghost out
    this.walls = [];
    const cx = (bx0 + bx1) / 2, cy = (by0 + by1) / 2;
    for (const g of geoms.bodies.world.geoms) {
      if (g.type !== 'box') continue;
      const geo = buildBody([g]);
      const mat = this._plainClone(this.matSolid); mat.transparent = true;
      const em = this._plainClone(this.matEdges);
      const mesh = new THREE.Mesh(geo.solid, mat), lines = new THREE.LineSegments(geo.edges, em);
      // inward normal in the xy plane, pointing at the room centre
      const wx = g.pos[0], wy = g.pos[1];
      const n = new THREE.Vector2(cx - wx, cy - wy);
      if (Math.abs(n.x) > Math.abs(n.y)) n.set(Math.sign(n.x), 0); else n.set(0, Math.sign(n.y));
      this.walls.push({ mesh, lines, mat, em, mid: new THREE.Vector2(wx, wy), inward: n, a: 1 });
      this.root.add(mesh, lines);
    }

    // every other body: one merged solid + edges + wireframe, parented to a group posed from the episode
    for (const [name, spec] of Object.entries(geoms.bodies)) {
      if (name === 'world') continue;
      this._makeBody(name, spec.geoms, false);
    }
    // cameras
    for (const [cname, c] of Object.entries(geoms.cameras)) {
      const cam = new THREE.PerspectiveCamera(c.fovy, 1, 0.02, 30);
      cam.layers.set(0); cam.name = c.node;
      this.root.add(cam); this.camNodes.set(c.node, cam);
    }
    // overview camera is a world-fixed viewpoint exposed as a preset
    this.overviewCam = this.camNodes.get('cam:overview');

    // explode vectors (fixtures and articulated parts pull apart; objects lift; arm stacks per link)
    this._buildExploders();
  }

  _makeBody(name, geoms, person) {
    const geo = buildBody(geoms);
    const group = new THREE.Group(); group.name = name;
    const entry = { name, group, geo, person, solid: null, isRobot: ROBOT.includes(name) };
    if (geo) {
      const solid = new THREE.Mesh(geo.solid, this.matSolid); solid.userData.body = name;
      const edges = new THREE.LineSegments(geo.edges, this.matEdges);
      const wire = new THREE.LineSegments(geo.wire, this.matWire); wire.visible = false;
      group.add(solid, edges, wire);
      entry.solid = solid; entry.edges = edges; entry.wire = wire;
    }
    (person ? this.personBodies : this.bodies).set(name, entry);
    this.root.add(group);
    return entry;
  }

  _buildExploders() {
    const { rooms } = this.data;
    const list = this.exploders = [];
    const fxById = new Map(rooms.fixtures.map((f) => [f.id, f]));
    const cx = (rooms.bounds.min[0] + rooms.bounds.max[0]) / 2;
    let fi = 0;
    for (const f of rooms.fixtures) {
      const e = this.bodies.get(f.id);
      const side = Math.sign(f.position[0] - cx) || -1;
      if (f.type === 'sink') { fi++; continue; }
      if (e) list.push({ entry: e, kind: 'fx', vec: new THREE.Vector3(side * (0.18 + Math.abs(f.position[0] - cx) * 0.22), 0, 0.04 * fi) });
      fi++;
    }
    let pi = 0;
    for (const p of rooms.parts) {
      const f = fxById.get(p.fixture); if (!f) continue;
      const fx = Math.sin(f.yaw), fy = Math.cos(f.yaw);
      const key = (n) => n === p.joint || n.startsWith(p.joint + '_') || (p.joint.endsWith('faucet') && n === p.joint + '_lever');
      for (const [n, e] of this.bodies) if (key(n)) {
        const side = Math.sign(f.position[0] - cx) || -1;
        const lift = p.joint.includes('upper') ? 0.32 : p.joint.includes('drawer') ? 0.05 : 0.0;
        list.push({ entry: e, kind: 'fx', vec: new THREE.Vector3(side * (0.18 + Math.abs(f.position[0] - cx) * 0.22) - fx * 0.55, fy * 0.55, 0.04 * (fxById.size) + lift + 0.03 * (pi % 3)) });
      }
      pi++;
    }
    for (const o of rooms.objects) {
      const e = this.bodies.get(o.id); if (e) list.push({ entry: e, kind: 'fx', vec: new THREE.Vector3(0, 0, 0.6) });
    }
    // sink and its faucet rise out of the counter
    const sinkLever = this.bodies.get('sink_1_faucet_lever');
    if (sinkLever && !list.find((l) => l.entry === sinkLever)) list.push({ entry: sinkLever, kind: 'fx', vec: new THREE.Vector3(0, 0, 0.5) });
    ROBOT.forEach((n, i) => { const e = this.bodies.get(n); if (e) list.push({ entry: e, kind: 'arm', vec: new THREE.Vector3(0, 0, Math.min(i, 9) * 0.17) }); });
  }

  // ---------- scan ----------
  _buildScan() {
    const s = this.data.scan, n = s.n, st = s.meta.stations;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(s.pos, 3));
    const col = new Float32Array(n * 3), scat = new Float32Array(n * 3), rnd = new Float32Array(n), sti = new Float32Array(n), dist = new Float32Array(n);
    const rand = mulberry(7);
    let maxR = 1;
    for (let i = 0; i < n; i++) {
      col[i * 3] = s.col[i * 3] / 255; col[i * 3 + 1] = s.col[i * 3 + 1] / 255; col[i * 3 + 2] = s.col[i * 3 + 2] / 255;
      const th = rand() * Math.PI * 2, ph = Math.acos(2 * rand() - 1), r = 0.5 + rand() * 1.6;
      scat[i * 3] = Math.sin(ph) * Math.cos(th) * r; scat[i * 3 + 1] = Math.sin(ph) * Math.sin(th) * r; scat[i * 3 + 2] = Math.abs(Math.cos(ph)) * r * 0.8 + 0.3;
      rnd[i] = rand();
      let bi = 0, bd = 1e9;
      for (let k = 0; k < st.length; k++) {
        const dx = s.pos[i * 3] - st[k][0], dy = s.pos[i * 3 + 1] - st[k][1], dz = s.pos[i * 3 + 2] - st[k][2];
        const d = Math.hypot(dx, dy, dz); if (d < bd) { bd = d; bi = k; }
      }
      sti[i] = bi; dist[i] = bd; if (bd > maxR) maxR = bd;
    }
    geo.setAttribute('aCol', new THREE.BufferAttribute(col, 3));
    geo.setAttribute('aScatter', new THREE.BufferAttribute(scat, 3));
    geo.setAttribute('aRand', new THREE.BufferAttribute(rnd, 1));
    geo.setAttribute('aSt', new THREE.BufferAttribute(sti, 1));
    geo.setAttribute('aDist', new THREE.BufferAttribute(dist, 1));
    this.scanMat = new THREE.ShaderMaterial({
      vertexShader: POINT_VS, fragmentShader: POINT_FS,
      uniforms: {
        uSettle: { value: this.reduced ? 1 : 0 }, uPx: { value: this.pr }, uSize: { value: 5.5 }, uFront: { value: 0 }, uMaxR: { value: maxR },
        uInk: { value: new THREE.Color() }, uSignal: { value: new THREE.Color() }, uAlpha: { value: 1 },
      },
    });
    this.scanPts = new THREE.Points(geo, this.scanMat);
    this.scanPts.frustumCulled = false; this.scanPts.layers.set(1);
    this.root.add(this.scanPts);
    this.scanA = 1;
    // station markers: tiny crosses at 1.3 m
    const m = [];
    for (const p of st) m.push(p[0] - 0.08, p[1], 0.0, p[0] + 0.08, p[1], 0.0, p[0], p[1] - 0.08, 0.0, p[0], p[1] + 0.08, 0.0);
    this.stationLines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(m, 3)), new THREE.LineBasicMaterial({ transparent: true }));
    this.stationLines.layers.set(1);
    this.root.add(this.stationLines);
  }

  // ---------- dimension lines and labels ----------
  _buildDims() {
    const { rooms } = this.data;
    const pts = []; this.labels = []; this.labelHost = document.getElementById('dims');
    const seg = (a, b) => pts.push(a[0], a[1], a[2], b[0], b[1], b[2]);
    const norm = (v) => { const l = Math.hypot(...v) || 1; return v.map((x) => x / l); };
    const add = (a, b, off, text, opts = {}) => {
      const A = [a[0] + off[0], a[1] + off[1], a[2] + off[2]], B = [b[0] + off[0], b[1] + off[1], b[2] + off[2]];
      const d = norm([B[0] - A[0], B[1] - A[1], B[2] - A[2]]);
      const perp = opts.perp || [0, 0, 1];
      const s = norm([d[0] + perp[0], d[1] + perp[1], d[2] + perp[2]]).map((x) => x * 0.075);
      const o = norm(off).map((x) => x * 0.06);
      seg(A, B);
      seg([a[0] + o[0], a[1] + o[1], a[2] + o[2]], [A[0] + o[0], A[1] + o[1], A[2] + o[2]]);
      seg([b[0] + o[0], b[1] + o[1], b[2] + o[2]], [B[0] + o[0], B[1] + o[1], B[2] + o[2]]);
      for (const P of [A, B]) seg([P[0] - s[0], P[1] - s[1], P[2] - s[2]], [P[0] + s[0], P[1] + s[1], P[2] + s[2]]);
      if (text) this._label(text, mj((A[0] + B[0]) / 2, (A[1] + B[1]) / 2, (A[2] + B[2]) / 2), 'dim', 'twin');
    };
    const [x0, y0] = rooms.bounds.min, [x1, y1, z1] = rooms.bounds.max;
    const f2 = (v) => v.toFixed(2) + ' m';
    add([x0, y1, 0], [x1, y1, 0], [0, 0.5, 0], f2(x1 - x0));
    add([x1, y0, 0], [x1, y1, 0], [0.5, 0, 0], f2(y1 - y0));
    add([x1, y1, 0], [x1, y1, z1], [0.5, 0.5, 0], f2(z1), { perp: [1, 1, 0] });
    for (const f of rooms.fixtures) {
      if (f.type === 'sink' || Math.abs(f.yaw || 0) > 1e-3) continue;   // the front edge below assumes yaw 0
      const w = f.size[0], d = f.size[1], front = f.position[1] + d / 2;
      add([f.position[0] - w / 2, front, 0], [f.position[0] + w / 2, front, 0], [0, 0.3 + (f.type.startsWith('fridge') ? 0.0 : 0.0), 0], f2(w));
      if (f.type.startsWith('fridge')) add([f.position[0] + w / 2, front, 0], [f.position[0] + w / 2, front, f.size[2]], [0.32, 0.0, 0], f2(f.size[2]), { perp: [1, 0, 0] });
    }
    // 1 m scale bar with 0.25 m ticks
    const sb = [x0, y1 + 0.95, 0];
    seg(sb, [sb[0] + 1, sb[1], 0]);
    for (let i = 0; i <= 4; i++) seg([sb[0] + i * 0.25, sb[1] - 0.04, 0], [sb[0] + i * 0.25, sb[1] + 0.04, 0]);
    this._label('1 m', mj(sb[0] + 0.5, sb[1], 0), 'dim', 'twin');
    this.dimGeo = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    this.dimLines = new THREE.LineSegments(this.dimGeo, this.matDims);
    this.dimLines.layers.set(2); this.dimLines.visible = false;
    this.root.add(this.dimLines);
    // articulated-part annotations follow the (exploded) part
    const notes = [['counter_a_drawer0', 'slide'], ['counter_a_door', 'hinge'], ['fridge_1_door', 'hinge'], ['stove_1_oven_door', 'hinge'], ['counter_b_drawer1', 'slide'], ['sink_1_faucet', 'hinge']];
    for (const [j, kind] of notes) {
      const part = rooms.parts.find((p) => p.joint === j); if (!part) continue;
      const body = this.bodies.get(j) || this.bodies.get(j + '_lever'); if (!body) continue;
      const txt = kind === 'slide' ? `slide ${part.open.toFixed(2)} m` : `hinge ${part.open.toFixed(2)} rad`;
      this._label(`${j.replace(/_/g, ' ')} · ${txt}`, new THREE.Vector3(), 'note', 'parts', body.group);
    }
  }

  _label(text, pos, cls, group, follow) {
    const el = document.createElement('span');
    el.className = `dim dim--${cls}`; el.textContent = text; el.setAttribute('aria-hidden', 'true');
    this.labelHost.appendChild(el);
    this.labels.push({ el, pos: pos.clone(), group, follow, shown: false, x: -1e9, y: -1e9 });
  }

  _buildLights() {
    this.hemi = new THREE.HemisphereLight(0xffffff, 0xcfc6b4, 1.5);
    this.key = new THREE.DirectionalLight(0xffffff, 2.0);
    this.fill = new THREE.DirectionalLight(0xffffff, 0.5);
    // aim both at the room centre; the default target is the room corner, which skews the shading
    const [x0, y0] = this.data.rooms.bounds.min, [x1, y1] = this.data.rooms.bounds.max;
    mj((x0 + x1) / 2, (y0 + y1) / 2, 0.9, this.key.target.position); this.fill.target.position.copy(this.key.target.position);
    this.scene.add(this.hemi, this.key, this.fill, this.key.target, this.fill.target);
  }

  _buildTrail() {
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
    const l = new THREE.Line(g, this.matTrail); l.layers.set(2); l.frustumCulled = false; l.renderOrder = 4; l.visible = false;
    this.root.add(l); return l;
  }

  // ---------- theme ----------
  setTheme(t) {
    this.theme = t;
    const c = (s) => new THREE.Color(s);
    const paper = c(t.paper), ink = c(t.ink), signal = c(t.signal);
    this.paper = paper; this.inkC = ink; this.signalC = signal;
    this.renderer.setClearColor(paper, 1);
    this.sh.uPaper.value.copy(paper);
    this.sh.uMix.value = t.dark ? 0.62 : 0.42;
    this.sh.uHatch.value = t.dark ? 0.22 : 0.15;
    this.matEdges.color.copy(ink); this.matWire.color.copy(ink); this.matDims.color.copy(ink);
    this.matFloorGrid.color.copy(ink); this.matFloorMajor.color.copy(ink);
    this.matTrail.color.copy(signal);
    this.stationLines.material.color.copy(signal);
    this.scanMat.uniforms.uInk.value.copy(ink); this.scanMat.uniforms.uSignal.value.copy(signal);
    this.hover.setColor(signal); this.select.setColor(signal); this.clear.material.color.copy(signal);
    const floorC = c(this.rooms.floor_colour || '#ad9c87').lerp(paper, t.dark ? 0.7 : 0.55);
    this.floor.material.color.copy(floorC);
    const wallC = c(this.rooms.wall_colour || '#ede8db').lerp(paper, t.dark ? 0.68 : 0.35);
    for (const w of this.walls) { w.mat.color.copy(wallC); w.em.color.copy(ink); }
    this.hemi.color.set(t.dark ? 0xc9d2dd : 0xffffff); this.hemi.groundColor.set(t.dark ? 0x3b342b : 0xcfc6b4);
    this.hemi.intensity = t.dark ? 1.1 : 1.5;
    this._lightScale = t.dark ? 0.75 : 1;
    this._applyLights();
  }

  _applyLights() {
    const ep = this.ep; if (!ep) return;
    const k = ep.lights.find((l) => l.name === 'key'), f = ep.lights.find((l) => l.name === 'fill');
    const lum = (d) => (d[0] + d[1] + d[2]) / 3;
    if (k) { this.key.intensity = (0.9 + lum(k.diffuse) * 2.4) * (this._lightScale || 1); mj(k.pos[0], k.pos[1], k.pos[2], this.key.position); }
    if (f) { this.fill.intensity = (0.2 + lum(f.diffuse) * 1.2) * (this._lightScale || 1); mj(f.pos[0], f.pos[1], f.pos[2], this.fill.position); }
    this.key.position.y = Math.max(this.key.position.y, 2);
  }

  // ---------- episode ----------
  setEpisode(ep) {
    this.ep = ep;
    // drop the previous people
    for (const e of this.personBodies.values()) { e.group.removeFromParent(); disposeBody(e.geo); }
    this.personBodies.clear();
    for (const [name, spec] of Object.entries(ep.person_geoms)) this._makeBody(name, spec.geoms, true);
    // node -> object, dynamic list
    const nodeObj = (n) => this.bodies.get(n)?.group || this.personBodies.get(n)?.group || this.camNodes.get(n);
    this.dyn = [];
    ep.nodes.dynamic.forEach((n, k) => { const o = nodeObj(n); if (o) this.dyn.push({ o, k, name: n }); });
    for (const [n, p] of Object.entries(ep.nodes.static)) {
      const o = nodeObj(n); if (!o) continue;
      o.position.set(p[0], p[1], p[2]); o.quaternion.set(p[4], p[5], p[6], p[3]);
    }
    // base positions for static exploders
    const dynSet = new Set(ep.nodes.dynamic);
    this.exploders.forEach((x) => { x.base = dynSet.has(x.entry.name) ? null : x.entry.group.position.clone(); });
    // pickables
    this.pickables = [];
    for (const e of [...this.bodies.values(), ...this.personBodies.values()]) if (e.solid) this.pickables.push(e);
    this.robotEntries = ROBOT.map((n) => this.bodies.get(n)).filter(Boolean);
    this.personEntries = [...this.personBodies.values()];
    this.handObj = nodeObj('hand');
    this.personNodes = this.dyn.filter((d) => d.name.startsWith('person_')).map((d) => d.o);
    // trajectory of the hand over the whole episode (drawn progressively with the playhead)
    const hi = ep.nodes.dynamic.indexOf('hand');
    const pos = new Float32Array(ep.n * 3);
    for (let i = 0; i < ep.n; i++) { const o = i * ep.stride + hi * 7; pos[i * 3] = ep.flat[o]; pos[i * 3 + 1] = ep.flat[o + 1]; pos[i * 3 + 2] = ep.flat[o + 2]; }
    this.trail.geometry.dispose(); this.trail.geometry = new THREE.BufferGeometry();
    this.trail.geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    this.trail.geometry.setDrawRange(0, 0);
    this.duration = (ep.n - 1) / ep.fps;
    this.frameState.n = ep.n; this.frameState.dur = this.duration;
    this.time = 0; this.hold = 0; this.poseDirty = true;
    this._buildShots();
    // the arm shots move with the task's base: ease from where the camera is now instead of snapping to the new path
    if (this._camReady && this.mode === 'tour') { this._retPos.copy(this.camera.position); this._retLook.copy(this._look); this.blend = 0; }
    this._applyLights();
    this.select.detach(); this.hover.detach();
    this.setTheme(this.theme || { paper: '#EFE9DC', ink: '#16130F', signal: '#E04A1F', dark: false });
    this._pose(0);
    this.cb.episode?.(ep);
  }

  // closest approach marker position in seconds, from the recorded control step (20 Hz)
  get closestApproachT() { const s = this.ep?.safety?.min_distance_step; return s == null ? null : s / this.ep.source_control_hz; }

  // ---------- camera shots ----------
  _buildShots() {
    const ep = this.ep, rb = ep.nodes.static.robot_base || [1.4, 1.4, 0.75];
    const fx = rb[0], fy = rb[1] - 0.45, sd = fx > 2 ? -1 : 1;   // view the arm from the open side of the room
    // the base differs per task, so keep the two arm shots inside the room (open_drawer would put shot 9 at x = 4.4 m)
    const [bx0, by0] = this.rooms.bounds.min, [bx1, by1] = this.rooms.bounds.max;
    const inX = (v) => clamp(v, bx0 + 0.3, bx1 - 0.3), inY = (v) => clamp(v, by0 + 0.3, by1 - 0.3);
    const S = [
      { p: [2.0, 6.8, 6.8], l: [2.0, 2.6, 0.3], f: 36 },            // 0 hero: plan view from the south
      { p: [1.12, 1.8, 1.3], l: [2.9, 0.1, 1.0], f: 66 },           // 1 scan station 1
      { p: [2.88, 1.8, 1.3], l: [1.0, 0.1, 1.0], f: 66 },           // 2 scan station 2
      { p: [2.0, 2.64, 1.3], l: [2.0, 0.0, 1.0], f: 66 },           // 3 scan station 3
      { p: [3.9, 6.2, 3.7], l: [1.9, 1.1, 0.6], f: 36 },            // 4 twin overview
      { p: [2.0, 6.0, 3.3], l: [2.0, 1.2, 0.8], f: 36 },            // 5 compare, front-on
      { p: [4.8, 5.4, 3.8], l: [2.0, 1.0, 1.0], f: 40 },            // 6 explode
      { p: [-0.6, 5.2, 3.6], l: [2.0, 1.0, 1.1], f: 40 },           // 7 explode, other side
      { p: [inX(fx + sd * 2.3), inY(fy + 0.3), 1.6], l: [fx, fy - 0.2, 1.0], f: 40 },   // 8 simulate: close on the arm
      { p: [inX(fx + sd * 3.3), inY(fy + 1.4), 2.2], l: [fx - sd * 0.2, fy - 0.1, 0.95], f: 40 }, // 9 workbench
    ];
    this.shots = S;
    const pts = (k) => S.map((s) => mj(s[k][0], s[k][1], s[k][2]));
    this.posCurve = new THREE.CatmullRomCurve3(pts('p'), false, 'centripetal', 0.5);
    this.lookCurve = new THREE.CatmullRomCurve3(pts('l'), false, 'centripetal', 0.5);
    this.focusMJ = new THREE.Vector3(fx, fy, 1.0);
  }

  // ---------- playback ----------
  play() { this.playing = true; this.cb.play?.(true); }
  pause() { this.playing = false; this.cb.play?.(false); }
  toggle() { this.playing ? this.pause() : this.play(); }
  seekFrame(f) { this.time = clamp(f, 0, this.ep.n - 1) / this.ep.fps; this.hold = 0; this.poseDirty = true; }
  get frame() { return this.time * this.ep.fps; }

  _pose(f) {
    const ep = this.ep, n = ep.n, flat = ep.flat, st = ep.stride;
    f = clamp(f, 0, n - 1);
    const i0 = Math.floor(f), i1 = Math.min(i0 + 1, n - 1), a = f - i0;
    const b0 = i0 * st, b1 = i1 * st;
    for (let j = 0; j < this.dyn.length; j++) {
      const d = this.dyn[j], o = d.k * 7, p0 = b0 + o, p1 = b1 + o, ob = d.o;
      ob.position.set(flat[p0] + (flat[p1] - flat[p0]) * a, flat[p0 + 1] + (flat[p1 + 1] - flat[p0 + 1]) * a, flat[p0 + 2] + (flat[p1 + 2] - flat[p0 + 2]) * a);
      let w0 = flat[p0 + 3], x0 = flat[p0 + 4], y0 = flat[p0 + 5], z0 = flat[p0 + 6];
      const w1 = flat[p1 + 3], x1 = flat[p1 + 4], y1 = flat[p1 + 5], z1 = flat[p1 + 6];
      const s = w0 * w1 + x0 * x1 + y0 * y1 + z0 * z1 < 0 ? -1 : 1;
      let w = w0 + (s * w1 - w0) * a, x = x0 + (s * x1 - x0) * a, y = y0 + (s * y1 - y0) * a, z = z0 + (s * z1 - z0) * a;
      const l = Math.hypot(w, x, y, z) || 1;
      ob.quaternion.set(x / l, y / l, z / l, w / l);
    }
    // explode offsets
    const J = this.J;
    for (let i = 0; i < this.exploders.length; i++) {
      const x = this.exploders[i], e = x.kind === 'fx' ? J.exF : J.exA, g = x.entry.group;
      if (x.base) g.position.copy(x.base);
      if (e > 0.0005) g.position.addScaledVector(x.vec, e);
    }
    // joints and live clearance
    const jt = this.frameState.joints;
    for (let k = 0; k < 8; k++) jt[k] = ep.joints[i0 * 8 + k] * (1 - a) + ep.joints[i1 * 8 + k] * a;
    this.frameState.f = f; this.frameState.t = f / ep.fps;
    if (this.handObj && this.personNodes.length && J.exF < 0.01 && J.exA < 0.01) {
      let best = 1e9, bi = 0;
      for (let k = 0; k < this.personNodes.length; k++) { const d = this.handObj.position.distanceToSquared(this.personNodes[k].position); if (d < best) { best = d; bi = k; } }
      this.frameState.live = Math.sqrt(best); this._nearest = this.personNodes[bi];
    } else { this.frameState.live = NaN; this._nearest = null; }
    this.trail.geometry.setDrawRange(0, Math.min(n, Math.floor(f) + 2));
    this.poseDirty = false;
  }

  // ---------- modes and picking ----------
  _enterExplore() {
    this.mode = 'explore'; this.controls.enableZoom = true; this.controls.enabled = true;
    this.canvas.style.touchAction = 'none'; this.canvas.setAttribute('data-lenis-prevent', '');   // wheel zooms here, it must not scroll the page too
    this.cb.mode?.('explore');
  }
  setMode(m) {
    if (m === this.mode) return;
    if (m === 'explore') {
      this.controls.target.copy(this._look); this.controls.update();
      this._enterExplore();
    } else {
      this._retPos.copy(this.camera.position); this._retLook.copy(this.controls.target);
      this.mode = 'tour'; this.blend = 0; this.controls.enableZoom = false; this.controls.enabled = this._orbitable;
      this.canvas.style.touchAction = 'pan-y'; this.canvas.removeAttribute('data-lenis-prevent'); this._focus = null;
      this.cb.mode?.('tour');
    }
  }
  setPointerParallax(x, y) { this.par.tx = x; this.par.ty = y; }

  pick(cx, cy) {
    const r = this.canvas.getBoundingClientRect();
    this._ndc.set(((cx - r.left) / r.width) * 2 - 1, -(((cy - r.top) / r.height) * 2 - 1));
    this.ray.setFromCamera(this._ndc, this.camera);
    const list = [];
    for (const e of this.pickables) if (e.group.visible && e.solid.visible) list.push(e.solid);
    const hit = this.ray.intersectObjects(list, false)[0];
    return hit ? hit.object.userData.body : null;
  }
  entry(name) { return this.bodies.get(name) || this.personBodies.get(name); }
  setHover(name) { if (name === this.hover.name) return; this.hover.attach(name && name !== this.select.name ? this.entry(name) : null); }
  setSelect(name) { this.select.attach(name ? this.entry(name) : null); if (name) this.hover.detach(); }
  focusOn(name) {
    const e = this.entry(name); if (!e) return;
    e.group.getWorldPosition(this._v);
    this._focus = { to: this._v.clone(), t: 0 };
    if (this.mode !== 'explore') this.setMode('explore');
  }
  bodyWorldMJ(name, out) { const e = this.entry(name); if (!e) return null; return out.copy(e.group.position); }

  // ---------- layout ----------
  resize() {
    const w = this.wrap.clientWidth, h = this.wrap.clientHeight;
    if (!w || !h) return;
    this.w = w; this.h = h;
    this.renderer.setPixelRatio(this.pr);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this._aspectFov = clamp(Math.sqrt(1.55 / this.camera.aspect), 1, 1.9);
    this.camera.updateProjectionMatrix();
    this.scanMat.uniforms.uPx.value = this.pr;
  }
  setFeeds(egoEl, wristEl) {
    this.feedEls = [[egoEl, this.camNodes.get('cam:ego_view')], [wristEl, this.camNodes.get('cam:wrist')]];
    // feed rectangles are measured only when something that can move them changed, not every frame
    const dirty = () => { this._feedDirty = true; };
    const ro = new ResizeObserver(dirty); ro.observe(egoEl); ro.observe(wristEl); ro.observe(this.canvas);
    const rd = document.getElementById('readout'); if (rd) ro.observe(rd);   // a taller readout pushes the feeds down
    egoEl.closest('.side')?.addEventListener('scroll', dirty, { passive: true });
    addEventListener('resize', dirty);
  }

  // ---------- the frame ----------
  tick(dt) {
    if (!this.ep || this.lost) return;
    dt = Math.min(dt, 0.1);
    const J = this.J, ep = this.ep;
    // the reader can take the camera once the twin is built (not on touch: there the page keeps scrolling)
    const orbitable = !this.coarse && J.build >= 0.5;
    if (orbitable !== this._orbitable) {
      this._orbitable = orbitable; this.wrap.classList.toggle('is-orbitable', orbitable);
      if (this.mode === 'tour') this.controls.enabled = orbitable;
    }
    // performance guard: drop resolution if frames run long
    if (this.visible) {
      this._perfT += dt; this._perfN++;
      if (this._perfN >= 90) {
        const avg = this._perfT / this._perfN;
        if (avg > 0.024 && this.pr > 1) { this._perfBad++; this._perfGood = 0; if (this._perfBad >= 2) { this.pr = Math.max(1, this.pr - 0.25); this.resize(); this._perfBad = 0; } }
        else {
          this._perfBad = 0;
          // recover: a few comfortably fast windows in a row bring resolution back up (a transient stall should not cost it for good)
          if (avg < 0.019 && this.pr < this.prCap) { if (++this._perfGood >= 4) { this.pr = Math.min(this.prCap, this.pr + 0.25); this.resize(); this._perfGood = 0; } } else this._perfGood = 0;
        }
        this._perfN = 0; this._perfT = 0;
      }
    }
    if (!this.visible) return;

    // autoplay once when the simulate chapter starts (never if the reader paused or reduced motion is on)
    if (J.autoplay && !this.autoplayed && !this.reduced) { this.autoplayed = true; this.play(); }

    if (this.playing) {
      if (this.hold > 0) { this.hold -= dt; if (this.hold <= 0) { this.time = 0; this.poseDirty = true; } }
      else {
        this.time += dt * this.speed;
        if (this.time >= this.duration) { this.time = this.duration; this.hold = 0.9; }
        this.poseDirty = true;
      }
    }
    if (J.exF !== this._lastExF || J.exA !== this._lastExA) { this._lastExF = J.exF; this._lastExA = J.exA; this.poseDirty = true; }
    if (this.poseDirty) this._pose(this.time * ep.fps);

    // layers
    const showTwin = J.build > 0.001;
    const solidOn = this.user.solid && showTwin;
    for (const e of this.bodies.values()) {
      if (!e.solid) continue;
      const vis = e.isRobot ? J.robot : true;
      e.group.visible = vis;
      e.solid.visible = solidOn; e.edges.visible = solidOn;
      e.wire.visible = (this.user.wire || J.wire > 0.5) && vis;
    }
    for (const e of this.personBodies.values()) {
      if (!e.solid) continue;
      const vis = J.people && this.user.people;
      e.group.visible = vis; e.solid.visible = solidOn; e.edges.visible = solidOn;
      e.wire.visible = (this.user.wire || J.wire > 0.5) && vis;
    }
    this.sh.uBuild.value = J.build;
    this.floor.visible = showTwin && this.user.solid; this.floor.material.opacity = 1;
    this.gridMinor.visible = this.gridMajor.visible = true;

    // scan
    const cmpOn = J.compare > 0.5;
    const scanTarget = cmpOn ? 1 : Math.max(J.scanA, this.user.scan ? 1 : 0);
    this.scanA = this.reduced ? scanTarget : damp(this.scanA, scanTarget, 7, dt);
    this.scanPts.visible = this.scanA > 0.01;
    this.stationLines.visible = this.scanPts.visible;
    this.scanMat.uniforms.uAlpha.value = this.scanA;
    this.scanMat.uniforms.uFront.value = J.front;
    this.stationLines.material.opacity = clamp(this.scanA, 0, 1);
    if (this.settle < 1) { this.settle = Math.min(1, this.settle + dt / 2.6); }
    this.scanMat.uniforms.uSettle.value = this.settle;

    // walls facing away from the camera ghost out
    const cam = this.camera;
    const cmx = cam.position.x, cmy = -cam.position.z;
    for (const w of this.walls) {
      const s = (cmx - w.mid.x) * w.inward.x + (cmy - w.mid.y) * w.inward.y;
      const target = s < -0.05 ? 0.07 : 1;
      w.a = this.reduced ? target : damp(w.a, target, 8, dt);
      w.mat.opacity = w.a; w.mat.depthWrite = w.a > 0.9; w.em.opacity = 0.62 * (0.25 + 0.75 * w.a);
      w.mesh.visible = w.lines.visible = showTwin && this.user.solid;
    }

    // dims
    this.dimLines.visible = J.dims > 0.01;
    this.matDims.opacity = J.dims;
    this.trail.visible = J.robot && J.exA < 0.01 && this.frame > 0.5;

    // camera
    this._updateCamera(dt);

    // clearance line from the hand to the nearest person node
    const cl = this.clear;
    if (this._nearest && J.people && this.user.people && J.robot && this.handObj) {
      const a = cl.geometry.attributes.position;
      a.setXYZ(0, this.handObj.position.x, this.handObj.position.y, this.handObj.position.z);
      a.setXYZ(1, this._nearest.position.x, this._nearest.position.y, this._nearest.position.z);
      a.needsUpdate = true; cl.visible = this.mode === 'explore' || J.feeds > 0.5;
    } else cl.visible = false;

    // render
    this._render();
    this._labels();

    // throttled callback for the HUD (15 Hz)
    this._cbAcc += dt;
    if (this._cbAcc > 0.066) { this._cbAcc = 0; this.cb.frame?.(this.frameState); }
  }

  _updateCamera(dt) {
    const J = this.J, cam = this.camera, N = this.shots.length;
    this.u = this.reduced ? J.shotU : damp(this.u, J.shotU, 9, dt);
    const u = clamp(this.u, 0, N - 1), t = u / (N - 1);
    this.posCurve.getPoint(t, this._pos); this.lookCurve.getPoint(t, this._look);
    const i = Math.min(Math.floor(u), N - 2), a = u - i;
    const fov = lerp(this.shots[i].f, this.shots[i + 1].f, easeInOutCubic(a)) * this._aspectFov;
    if (Math.abs(cam.fov - fov) > 0.01) { cam.fov = fov; cam.updateProjectionMatrix(); }
    if (this.mode === 'explore') {
      if (this._focus) {
        const f = this._focus; f.t = Math.min(1, f.t + dt / 0.6);
        const e = easeInOutCubic(f.t);
        this.controls.target.lerp(f.to, e * 0.25 + 0.02);
        if (f.t >= 1) this._focus = null;
      }
      this.controls.update();
      this._look.copy(this.controls.target);
      return;
    }
    // tour: ease back from wherever the reader left the camera
    if (this.blend < 1) {
      this.blend = Math.min(1, this.blend + dt / 0.8);
      const e = easeInOutCubic(this.blend);
      this._pos.lerpVectors(this._retPos, this._pos, e); this._look.lerpVectors(this._retLook, this._look, e);
    }
    const p = this.par; p.x = damp(p.x, p.tx, 5, dt); p.y = damp(p.y, p.ty, 5, dt);
    cam.position.copy(this._pos); cam.lookAt(this._look); this._camReady = true;
    if (!this.reduced) { const k = this._pos.distanceTo(this._look) * 0.018; cam.translateX(p.x * k); cam.translateY(p.y * k); }
  }

  _render() {
    const r = this.renderer, cam = this.camera, W = this.w, H = this.h, J = this.J;
    // reads first (feed rects), then draw
    let feedRects = null;
    if (J.feeds > 0.5 && this.feedEls) {
      feedRects = this._feedRects || (this._feedRects = [{}, {}]);
      if (this._feedDirty) {
        this._feedDirty = false;
        const cr = this.canvas.getBoundingClientRect();
        for (let i = 0; i < 2; i++) {
          const b = this.feedEls[i][0].getBoundingClientRect(), o = feedRects[i];
          o.x = b.left - cr.left; o.y = H - (b.bottom - cr.top); o.w = b.width; o.h = b.height; o.cam = this.feedEls[i][1];
        }
      }
    }
    r.setScissorTest(false); r.setViewport(0, 0, W, H);
    if (J.compare > 0.5) {
      const x = Math.round(W * this.cmpX);
      r.setScissorTest(true);
      r.setScissor(0, 0, x, H); cam.layers.set(1); cam.layers.enable(2); r.render(this.scene, cam);
      r.setScissor(x, 0, W - x, H); cam.layers.set(0); cam.layers.enable(2); r.render(this.scene, cam);
      r.setScissorTest(false); cam.layers.enableAll();
    } else r.render(this.scene, cam);
    if (feedRects) {
      // the robot cameras see real walls: undo the ghosting that the orbit camera applied (tick re-applies it next frame)
      for (const w of this.walls) { w.mat.opacity = 1; w.mat.depthWrite = true; w.em.opacity = 0.62; }
      r.autoClear = true; r.setScissorTest(true);
      for (let i = 0; i < 2; i++) {
        const o = feedRects[i]; if (o.w < 8) continue;
        r.setViewport(o.x, o.y, o.w, o.h); r.setScissor(o.x, o.y, o.w, o.h);
        o.cam.layers.set(0);
        r.render(this.scene, o.cam);
      }
      r.setScissorTest(false); r.setViewport(0, 0, W, H);
    }
  }

  _labels() {
    const J = this.J, W = this.w, H = this.h, cam = this.camera, v = this._v2;
    for (const L of this.labels) {
      let show = L.group === 'twin' ? J.dims > 0.15 : (J.exF > 0.5 && J.exA < 0.01);
      if (show) {
        if (L.follow) { L.follow.getWorldPosition(v); v.y += 0.05; } else v.copy(L.pos);
        v.project(cam);
        if (v.z > 1 || v.z < -1) show = false;
        else {
          const x = (v.x * 0.5 + 0.5) * W, y = (-v.y * 0.5 + 0.5) * H;
          if (Math.abs(x - L.x) > 0.1 || Math.abs(y - L.y) > 0.1) { L.x = x; L.y = y; L.el.style.transform = `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0) translate(-50%,-135%)`; }
        }
      }
      if (show !== L.shown) { L.shown = show; L.el.classList.toggle('is-on', show); }
    }
  }
}
