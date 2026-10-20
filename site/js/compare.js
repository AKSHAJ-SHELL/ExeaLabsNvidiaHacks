// Scan versus twin divider. Mechanics from UltraUI's aceternity `compare` (drag to reveal), done as a scissor split in the
// stage so both halves are the same camera. Spring-smoothed, rubber-banded at the ends (apple-design [9]), keyboard operable.
import { Spring, clamp } from './util.js';

const rubber = (over, dim, c = 0.55) => (over * dim * c) / (dim + c * Math.abs(over));

export function initCompare({ stage, reduced }) {
  const root = document.getElementById('compare'), line = document.getElementById('compareLine'), handle = document.getElementById('compareHandle');
  const spring = new Spring(0.5, 0.28);
  let dragging = false, grab = 0, shown = false, invite = 0;
  const LO = 0.07, HI = 0.93;

  const width = () => root.clientWidth || 1;
  const setAria = () => {
    const v = Math.round(stage.cmpX * 100);
    handle.setAttribute('aria-valuenow', v);
    handle.setAttribute('aria-valuetext', v < 35 ? 'Mostly twin' : v > 65 ? 'Mostly scan' : 'Half scan, half twin');
  };

  handle.addEventListener('pointerdown', (e) => {
    handle.setPointerCapture(e.pointerId); dragging = true; root.classList.add('is-drag'); invite = 0;
    grab = e.clientX - (root.getBoundingClientRect().left + spring.x * width());   // keep the grab offset, no snap to centre
  });
  handle.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const w = width(), raw = (e.clientX - grab - root.getBoundingClientRect().left) / w;
    const t = raw < LO ? LO + rubber(raw - LO, 1) : raw > HI ? HI + rubber(raw - HI, 1) : raw;
    spring.target = clamp(t, -0.02, 1.02); spring.response = 0.12;                  // near 1:1 while dragging
  });
  const end = (e) => {
    if (!dragging) return; dragging = false; root.classList.remove('is-drag');
    spring.target = clamp(spring.target, LO, HI); spring.response = 0.3;            // settle back inside the bounds
    try { handle.releasePointerCapture(e.pointerId); } catch { /* already released */ }
  };
  handle.addEventListener('pointerup', end); handle.addEventListener('pointercancel', end);
  handle.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 0.2 : 0.05;
    if (e.key === 'ArrowLeft') spring.target = clamp(spring.target - step, LO, HI);
    else if (e.key === 'ArrowRight') spring.target = clamp(spring.target + step, LO, HI);
    else if (e.key === 'Home') spring.target = LO; else if (e.key === 'End') spring.target = HI; else return;
    spring.response = 0.28; invite = 0; e.preventDefault();
  });

  return {
    update(dt) {
      const on = stage.J.compare > 0.5;
      if (on && !shown) { shown = true; root.hidden = false; requestAnimationFrame(() => root.classList.add('is-on')); if (!reduced) invite = 1.6; }
      if (!on && shown) { shown = false; root.classList.remove('is-on'); setTimeout(() => { if (!shown) root.hidden = true; }, 260); }
      if (!shown) return;
      if (invite > 0 && !dragging) {                      // one gentle sweep to show the divider moves
        invite -= dt; const p = 1 - invite / 1.6;
        spring.target = 0.5 + Math.sin(p * Math.PI * 2) * 0.1 * (1 - p); spring.response = 0.5;
      }
      spring.step(dt);
      stage.cmpX = clamp(spring.x, 0, 1);
      line.style.transform = `translate3d(${(stage.cmpX * width()).toFixed(1)}px,0,0)`;
      if (Math.abs(stage.cmpX - (+handle.dataset.v || 0)) > 0.004) { handle.dataset.v = stage.cmpX; setAria(); }
    },
  };
}
