// Boot: load the exported data, build the stage, wire the UI and the scroll layer, then lift the loading sheet.
import { loadCore } from './data.js';
import { bindData, renderEvaluate, renderFallback } from './sections.js';
import { initTilt } from './tilt.js';
import { prefersReducedMotion, isCoarse, $ } from './util.js';

const TOTAL_STEPS = 8;
let done = 0;
const loaderFill = $('#loaderFill'), loaderMsg = $('#loaderMsg'), loader = $('#loader'), status = $('#status');
const step = () => { done++; loaderFill.style.transform = `scaleX(${Math.min(done / TOTAL_STEPS, 1)})`; loaderMsg.textContent = `Opening survey data ${Math.min(done, TOTAL_STEPS)} / ${TOTAL_STEPS}`; };
const announce = (() => { let t = 0; return (msg) => { clearTimeout(t); t = setTimeout(() => { status.textContent = msg; }, 250); }; })();

async function boot() {
  const reduced = prefersReducedMotion(), coarse = isCoarse();
  const fonts = Promise.race([Promise.all([document.fonts.load('300 48px Fraunces'), document.fonts.load('400 12px "DM Mono"')]), new Promise((r) => setTimeout(r, 1500))]).then(step);
  const data = await loadCore(step);
  await fonts;
  const first = 'open_drawer';
  await data.loadEpisode(first); step();

  bindData(data);
  renderEvaluate(data.stats);
  initTilt(document, { reduced, coarse });

  let stage;
  try {
    const { Stage } = await import('./stage.js');
    stage = new Stage({ canvas: $('#gl'), wrap: $('#stage'), data, reduced, coarse });
  } catch (err) {
    console.warn('WebGL stage unavailable, showing the recorded frames instead:', err);
    document.documentElement.classList.add('no-webgl');
    $('#fallback').hidden = false; renderFallback(data.stats);
    $('#journey').style.height = 'auto';
    loaderFill.style.transform = 'scaleX(1)'; loader.classList.add('is-done');
    return;
  }
  step();
  const { initUI } = await import('./ui.js');
  const { initCompare } = await import('./compare.js');
  const { initScroll } = await import('./scroll.js');
  const ui = initUI({ stage, data, announce });
  await ui.selectTask(first, { silent: true });
  const compare = initCompare({ stage, reduced });
  const scroll = initScroll({ stage, ui, reduced, coarse, announce, compare });
  window.arrival = { stage, ui, scroll, data };      // handle for debugging and automated checks

  // first frame, then lift the loading sheet
  stage.resize(); stage.tick(0.016);
  step();
  requestAnimationFrame(() => { loader.classList.add('is-done'); });
  stage.canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); document.documentElement.classList.add('no-webgl'); $('#fallback').hidden = false; renderFallback(data.stats); });
}

boot().catch((err) => { console.error(err); loaderMsg.textContent = 'Could not open the survey data. Run: make site'; });
