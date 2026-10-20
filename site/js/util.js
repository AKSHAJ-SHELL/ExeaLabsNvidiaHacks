// Small numeric helpers. No allocation inside any of these.
export const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const invLerp = (a, b, v) => (a === b ? 0 : clamp((v - a) / (b - a)));
export const smoothstep = (a, b, v) => { const t = invLerp(a, b, v); return t * t * (3 - 2 * t); };
export const smootherstep = (a, b, v) => { const t = invLerp(a, b, v); return t * t * t * (t * (t * 6 - 15) + 10); };
export const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
export const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
// Frame-rate independent exponential smoothing (critically damped feel, no overshoot).
export const damp = (cur, target, rate, dt) => lerp(cur, target, 1 - Math.exp(-rate * dt));

/**
 * Critically damped spring (Apple "damping 1.0"): value follows target, keeps velocity when the target moves,
 * so it can be grabbed and redirected at any moment. `response` is the settle time scale in seconds.
 */
export class Spring {
  constructor(value = 0, response = 0.3) { this.x = value; this.v = 0; this.target = value; this.response = response; }
  set(value) { this.x = this.target = value; this.v = 0; }
  step(dt) {
    const w = (2 * Math.PI) / this.response;
    const d = Math.min(dt, 1 / 30);
    // semi-implicit integration of x'' = -w^2 (x - target) - 2 w x'
    this.v += (-w * w * (this.x - this.target) - 2 * w * this.v) * d;
    this.x += this.v * d;
    return this.x;
  }
  get settled() { return Math.abs(this.x - this.target) < 1e-4 && Math.abs(this.v) < 1e-3; }
}

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

export const fmt = {
  n: (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }),
  m: (v, d = 2) => Number(v).toFixed(d),
  t: (s) => s.toFixed(2).padStart(5, '0'),
};

export const safeStorage = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage blocked: the page works without it */ } },
};

export const prefersReducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const isCoarse = () => matchMedia('(pointer: coarse)').matches;
