// Pointer-driven 3D tilt with a glare that follows the pointer.
// Ported from UltraUI's aceternity 3d-card (rotate toward the pointer, children lifted on Z) and glare-card (radial highlight),
// rebuilt on critically damped springs (apple-design [3][4]): the card can be grabbed and re-aimed at any instant and never overshoots.
import { Spring, clamp } from './util.js';

const MAX = 8; // degrees

export function initTilt(root, { reduced, coarse }) {
  const els = Array.from(root.querySelectorAll('.tilt'));
  for (const el of els) attach(el, reduced || coarse);
}

function attach(el, flat) {
  const rx = new Spring(0, 0.3), ry = new Spring(0, 0.3), sc = new Spring(1, 0.22), ga = new Spring(0, 0.35), gx = new Spring(50, 0.2), gy = new Spring(50, 0.2);
  const all = [rx, ry, sc, ga, gx, gy];
  let raf = 0, last = 0, hot = false;

  const frame = (t) => {
    const dt = Math.min((t - last) / 1000, 1 / 30); last = t;
    for (const s of all) s.step(dt);
    el.style.setProperty('--rx', rx.x.toFixed(3) + 'deg'); el.style.setProperty('--ry', ry.x.toFixed(3) + 'deg');
    el.style.setProperty('--sc', sc.x.toFixed(4)); el.style.setProperty('--ga', clamp(ga.x).toFixed(3));
    el.style.setProperty('--gx', gx.x.toFixed(1) + '%'); el.style.setProperty('--gy', gy.x.toFixed(1) + '%');
    if (hot || !all.every((s) => s.settled)) raf = requestAnimationFrame(frame); else raf = 0;
  };
  const kick = () => { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };

  const aim = (e) => {
    const r = el.getBoundingClientRect();
    const px = clamp((e.clientX - r.left) / r.width), py = clamp((e.clientY - r.top) / r.height);
    ry.target = (px - 0.5) * 2 * MAX; rx.target = -(py - 0.5) * 2 * MAX;
    gx.target = px * 100; gy.target = py * 100; ga.target = 1;
    kick();
  };
  el.addEventListener('pointerdown', () => { sc.target = 0.985; kick(); });          // respond on press, not release [1]
  const up = () => { sc.target = hot ? 1.01 : 1; kick(); };
  el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
  if (flat) return;
  el.addEventListener('pointerenter', (e) => { if (e.pointerType === 'touch') return; hot = true; sc.target = 1.01; aim(e); });
  el.addEventListener('pointermove', (e) => { if (e.pointerType === 'touch') return; aim(e); });
  el.addEventListener('pointerleave', () => { hot = false; rx.target = ry.target = 0; sc.target = 1; ga.target = 0; kick(); });
}
