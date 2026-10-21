// MuJoCo geoms -> merged three.js buffers, one set per body. Everything stays in the body's local MuJoCo frame
// (z up, metres); the scene root rotates once to three's y-up.
import * as THREE from 'three';

const MAT = { wood: 1, stone: 2, panel: 3, paint: 4, floor: 5 };
const primCache = new Map();

function primitive(g) {
  const key = `${g.type}:${g.size.join(',')}`;
  let p = primCache.get(key);
  if (p) return p;
  const [a, b, c] = g.size;
  let geo;
  switch (g.type) {
    case 'box': geo = new THREE.BoxGeometry(a * 2, b * 2, c * 2); break;
    case 'sphere': geo = new THREE.SphereGeometry(a, 12, 8); break;
    case 'capsule': geo = new THREE.CapsuleGeometry(a, b * 2, 3, 10); geo.rotateX(Math.PI / 2); break;
    case 'cylinder': geo = new THREE.CylinderGeometry(a, a, b * 2, 14, 1); geo.rotateX(Math.PI / 2); break;
    default: return null;
  }
  const edges = new THREE.EdgesGeometry(geo, 30);
  const wire = g.type === 'box' ? edges : new THREE.WireframeGeometry(geo);
  p = { geo, edges, wire };
  primCache.set(key, p);
  return p;
}

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(1, 1, 1);
const _v = new THREE.Vector3(), _c = new THREE.Color();

function pushLines(dst, src, m) {
  const pa = src.attributes.position;
  for (let i = 0; i < pa.count; i++) { _v.fromBufferAttribute(pa, i).applyMatrix4(m); dst.push(_v.x, _v.y, _v.z); }
}

/** Returns {solid, edges, wire, radius} BufferGeometries for a list of geoms, or null if nothing visible. */
export function buildBody(geoms) {
  const pos = [], nor = [], col = [], mat = [], idx = [], edges = [], wire = [];
  let vbase = 0;
  for (const g of geoms) {
    const p = primitive(g);
    if (!p) continue;
    _p.set(g.pos[0], g.pos[1], g.pos[2]);
    _q.set(g.quat[1], g.quat[2], g.quat[3], g.quat[0]); // wxyz -> xyzw
    _m.compose(_p, _q, _s);
    _c.setRGB(g.rgba[0], g.rgba[1], g.rgba[2], THREE.SRGBColorSpace);
    const m = MAT[g.material] || 0;
    const pa = p.geo.attributes.position, na = p.geo.attributes.normal, ia = p.geo.index;
    for (let i = 0; i < pa.count; i++) {
      _v.fromBufferAttribute(pa, i).applyMatrix4(_m); pos.push(_v.x, _v.y, _v.z);
      _v.fromBufferAttribute(na, i).transformDirection(_m); nor.push(_v.x, _v.y, _v.z);
      col.push(_c.r, _c.g, _c.b); mat.push(m);
    }
    for (let i = 0; i < ia.count; i++) idx.push(ia.getX(i) + vbase);
    vbase += pa.count;
    pushLines(edges, p.edges, _m);
    pushLines(wire, p.wire, _m);
  }
  if (!pos.length) return null;
  const solid = new THREE.BufferGeometry();
  solid.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  solid.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  solid.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  solid.setAttribute('aMat', new THREE.Float32BufferAttribute(mat, 1));
  solid.setIndex(idx);
  solid.computeBoundingSphere();
  const mk = (arr) => { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3)); return g; };
  return { solid, edges: mk(edges), wire: mk(wire) };
}

/** Disposes per-episode geometry (person bodies). Shared primitives live for the page lifetime. */
export function disposeBody(b) { if (!b) return; b.solid.dispose(); b.edges.dispose(); b.wire.dispose(); }
