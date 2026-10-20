// Scroll layer: Lenis smooth scroll wired to GSAP ScrollTrigger, the chapter choreography that drives the stage,
// the tracing beam, the sticky-scroll-reveal of the pipeline steps, and the reading highlight in the chapter notes.
// GSAP is isolated here on purpose (its licence is free-to-use but not MIT; see vendor/README.md).
//
// Ported from UltraUI (mechanics only):
//   scroll-lenis-gsap-integration-harness : Lenis driven by gsap.ticker, ScrollTrigger.update on scroll, lagSmoothing(0),
//                                           Lenis off for reduced motion and coarse pointers, debounced refresh on resize
//   scroll-chapter-pinned-story           : one pinned stage, chapter windows from a vh budget table, notes keyed to windows
//   container-scroll-animation            : the stage panel starts in perspective (rotateX 18, scaled, pushed down) and flattens to
//                                           full bleed while the hero text lifts away
//   scroll-progress-indicators / tracing-beam : a margin line drawn with the page, chapter ticks, active chapter label
//   sticky-scroll-reveal                  : pipeline steps scroll on the left, the sticky spec sheet on the right follows the active step
//                                           (now in chrome.js, so it also works without WebGL)
//   scroll-text-highlight-reading         : words of the active note's lead brighten as you read through its window
import { clamp, lerp, smoothstep, smootherstep, easeInOutCubic, $, $$ } from './util.js';

const { gsap, ScrollTrigger, Lenis } = window;

// vh budget per phase. Camera, build-up, explode and HUD are all functions of the position inside a phase.
const PHASES = [['hero', 100], ['scan', 150], ['twin', 100], ['compare', 90], ['explode', 130], ['simulate', 120], ['bench', 100]];
const TOTAL = PHASES.reduce((a, p) => a + p[1], 0);
const NOTE_OF = { scan: 'scan', twin: 'twin', compare: 'compare', explode: 'explode', simulate: 'simulate', bench: 'bench' };
const STRIP = { hero: ['Sheet A-01', 'Cover'], scan: ['Sheet A-01', '01 Scan'], twin: ['Sheet A-02', '02 Twin'], compare: ['Sheet A-02', '02 Twin'], explode: ['Sheet A-02', '02 Twin'], simulate: ['Sheet A-03', '03 Simulate'], bench: ['Sheet A-03', '03 Simulate'] };
const e3 = easeInOutCubic;

export function initScroll({ stage, ui, reduced, coarse, announce, compare, motion }) {
  gsap.registerPlugin(ScrollTrigger);
  ScrollTrigger.config({ ignoreMobileResize: true });      // a collapsing mobile toolbar must not rebuild the journey
  const J = stage.J;
  const journey = $('#journey'), pin = $('#pin'), stageEl = $('#stage'), hero = $('#hero');
  journey.style.height = `${100 + TOTAL}svh`;

  // ---------- Lenis on the GSAP ticker ----------
  let lenis = null;
  if (!reduced && !coarse && Lenis) {
    lenis = new Lenis({ lerp: 0.1, smoothWheel: true, wheelMultiplier: 1 });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
  }
  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add((time, dtMs) => { compare.update(Math.min(dtMs / 1000, 0.1)); stage.tick(dtMs / 1000); });
  stage.lenis = lenis;

  // ---------- phase table ----------
  let acc = 0;
  const ph = PHASES.map(([id, vh]) => { const o = { id, a: acc / TOTAL, b: (acc + vh) / TOTAL, vh }; acc += vh; return o; });
  const phaseAt = (P) => { for (let i = ph.length - 1; i >= 0; i--) if (P >= ph[i].a) return i; return 0; };

  // ---------- notes ----------
  const notes = {}; $$('.note').forEach((n) => { notes[n.dataset.note] = n; });
  // split the lead into words for the reading highlight; the text-only copy for assistive tech is built first
  const sr = $('#srNotes');
  $$('.note').forEach((n) => { const c = document.createElement('article'); c.innerHTML = n.innerHTML; sr.appendChild(c); });
  const leadWords = {};
  for (const [k, n] of Object.entries(notes)) {
    const lead = $('.note__lead', n), words = lead.textContent.trim().split(/\s+/);
    lead.innerHTML = words.map((w) => `<span class="w">${w}</span>`).join(' ');
    leadWords[k] = { els: $$('.w', lead), on: 0 };
  }
  let curPhase = -1, lastWords = '';

  const strip = { sheet: $('#stripSheet'), name: $('#stripName') };
  const hud = { top: $('#hudTop'), layers: $('#hudLayers'), side: $('#side'), dock: $('#dock'), feeds: $('#feeds') };
  let trayOpened = false;

  function setPhase(i) {
    curPhase = i; const id = ph[i].id;
    for (let k = 0; k < ph.length; k++) {
      const n = notes[NOTE_OF[ph[k].id]]; if (!n) continue;
      n.classList.toggle('is-on', k === i); n.classList.toggle('is-before', k > i); n.classList.toggle('is-after', k < i);
    }
    const s = STRIP[id]; strip.sheet.textContent = s[0]; strip.name.textContent = s[1];
    stageEl.classList.toggle('is-sim', id === 'simulate' || id === 'bench');
    if (stage.mode === 'explore') stage.setMode('tour');       // the camera goes back to the scroll when the chapter changes
    if (id !== 'hero') announce(`${s[1]}.`);
  }

  // ---------- the journey ----------
  function journeyUpdate(P) {
    const i = phaseAt(P), p = ph[i], t = clamp((P - p.a) / (p.b - p.a));
    if (i !== curPhase) setPhase(i);

    // defaults for later phases; earlier phases overwrite below
    let k = 1, shotU = 0, front = 3, build = 1.7, scanA = 0, wire = 0, dims = 0, exF = 0, exA = 0, cmp = 0, robot = false, people = false, auto = false, feeds = 0;
    let hTop = true, hLayers = true, hSide = false;

    switch (p.id) {
      case 'hero': k = smootherstep(0, 0.88, t); shotU = e3(t); front = 0; build = 0; scanA = 1; hTop = k > 0.9; hLayers = false; break;
      case 'scan': shotU = t < 0.5 ? 1 + e3(t * 2) : 2 + e3((t - 0.5) * 2); front = 3 * smootherstep(0.04, 0.96, t); build = 0; scanA = 1; hLayers = false; break;
      case 'twin': shotU = 3 + e3(t); front = 3; build = 1.7 * smoothstep(0.02, 0.8, t); wire = t < 0.8 ? 1 : 0; scanA = 1 - smoothstep(0.55, 0.95, t); dims = smoothstep(0.55, 0.95, t); break;
      case 'compare': shotU = 4 + e3(t); front = 3; dims = 1; cmp = t > 0.08 ? 1 : 0; scanA = cmp; break;
      case 'explode': shotU = 5 + 2 * e3(t); exF = smootherstep(0, 0.42, t) - smootherstep(0.6, 0.96, t); dims = 1 - smoothstep(0.02, 0.28, t); break;
      case 'simulate': shotU = 7 + e3(t); exA = 1 - smootherstep(0.08, 0.6, t); robot = t > 0.02; people = t > 0.5; auto = t > 0.55; hSide = t > 0.5; feeds = t > 0.82 ? 1 : 0; break;
      default: shotU = 8 + e3(clamp(t * 1.25)); robot = people = auto = hSide = true; feeds = 1; exA = 0;
    }
    Object.assign(J, { shotU, front, build, scanA, wire, dims, exF: Math.max(0, exF), exA, compare: cmp, robot, people, autoplay: auto || J.autoplay, feeds });
    if (p.id === 'bench' && !trayOpened) { trayOpened = true; if (innerWidth >= 720) ui.setTray(true); }

    // container-scroll: perspective panel flattens to full bleed while the hero lifts away
    const H = pin.clientHeight;
    if (reduced) {
      const x = p.id === 'hero' ? smoothstep(0.25, 0.6, t) : 1;
      stageEl.style.opacity = x; hero.style.opacity = 1 - x; hero.style.pointerEvents = x > 0.5 ? 'none' : '';
      stageEl.style.setProperty('--k', 1); stageEl.classList.remove('is-tilted');
    } else {
      const ty = (1 - k) * H * (innerWidth < 720 ? 0.72 : 0.55), rx = (1 - k) * 18, sc = lerp(0.84, 1, k);
      stageEl.style.transform = k >= 0.999 ? 'none' : `translate3d(0,${ty.toFixed(1)}px,0) rotateX(${rx.toFixed(2)}deg) scale(${sc.toFixed(4)})`;
      stageEl.style.setProperty('--k', k.toFixed(4));
      stageEl.classList.toggle('is-tilted', k < 0.96);
      hero.style.transform = `translate3d(0,${(-k * 90).toFixed(1)}px,0)`;
      hero.style.opacity = String(1 - smoothstep(0.35, 0.95, k));
      hero.style.pointerEvents = k > 0.5 ? 'none' : '';
    }
    hud.top.classList.toggle('is-on', hTop); hud.layers.classList.toggle('is-on', hLayers);
    hud.side.classList.toggle('is-on', hSide); hud.dock.classList.toggle('is-on', hSide); hud.feeds.classList.toggle('is-on', feeds > 0);

    // reading highlight inside the active note
    const key = NOTE_OF[p.id];
    if (key) {
      const lw = leadWords[key], n = Math.ceil(smoothstep(0.04, 0.6, t) * lw.els.length * 1.05);
      if (reduced || n !== lw.on) { const to = reduced ? lw.els.length : n; for (let w = 0; w < lw.els.length; w++) lw.els[w].classList.toggle('on', w < to); lw.on = n; }
    }
  }

  const journeyST = ScrollTrigger.create({ trigger: journey, start: 'top top', end: 'bottom bottom', onUpdate: (s) => journeyUpdate(s.progress), onRefresh: (s) => journeyUpdate(s.progress) });
  journeyUpdate(0);
  // scroll position of a progress value, read from the trigger's own range so svh, dvh and a collapsing toolbar cannot skew it
  const journeyY = (P) => journeyST.start + P * (journeyST.end - journeyST.start);

  // ---------- pause rendering off screen ----------
  new IntersectionObserver(([e]) => { stage.visible = e.isIntersecting; }, { rootMargin: '10% 0px' }).observe(journey);
  addEventListener('pointermove', (e) => { if (curPhase >= 0 && !coarse) stage.setPointerParallax((e.clientX / innerWidth - 0.5) * 2, (e.clientY / innerHeight - 0.5) * 2); }, { passive: true });

  // ---------- tracing beam ----------
  const beamSvg = $('#beamSvg'), beamBase = $('#beamBase'), beamFill = $('#beamFill'), beamList = $('#beamList'), beam = $('#beam');
  const chapters = [['scan', () => journeyY(ph[1].a)], ['twin', () => journeyY(ph[2].a)], ['simulate', () => journeyY(ph[5].a)], ['dataset', () => $('#dataset').offsetTop], ['evaluate', () => $('#evaluate').offsetTop], ['close', () => $('#close').offsetTop]];
  let beamLen = 1, chapterY = [], docMax = 1, beamLinks = [], beamActive = -2;
  function buildBeam() {
    const h = beam.clientHeight; if (!h) return;
    docMax = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    chapterY = chapters.map(([, f]) => f());
    let d = 'M6 0';
    chapterY.forEach((y) => { const yy = clamp(y / docMax) * h; d += ` L6 ${(yy - 9).toFixed(1)} L12 ${(yy - 3).toFixed(1)} L12 ${(yy + 3).toFixed(1)} L6 ${(yy + 9).toFixed(1)}`; });
    d += ` L6 ${h}`;
    beamBase.setAttribute('d', d); beamFill.setAttribute('d', d);
    beamSvg.setAttribute('viewBox', `0 0 20 ${h}`);
    beamLen = beamFill.getTotalLength(); beamFill.style.strokeDasharray = beamLen;
    $$('li', beamList).forEach((li, i) => { li.style.top = `${clamp(chapterY[i] / docMax) * h}px`; li.style.left = '14px'; });
    beamLinks = $$('a', beamList); beamActive = -2;
    beamUpdate();
  }
  function beamUpdate() {
    const y = (lenis ? lenis.scroll : scrollY), prog = clamp(y / docMax);
    beamFill.style.strokeDashoffset = beamLen * (1 - prog);
    let active = -1; for (let i = 0; i < chapterY.length; i++) if (y + innerHeight * 0.4 >= chapterY[i]) active = i;
    if (active !== beamActive) { beamActive = active; beamLinks.forEach((a, i) => a.classList.toggle('is-on', i === active)); }
  }
  ScrollTrigger.create({ trigger: document.documentElement, start: 'top top', end: 'bottom bottom', onUpdate: beamUpdate });
  ScrollTrigger.addEventListener('refresh', buildBeam);

  // ---------- anchors ----------
  const jumpNow = (y) => { if (lenis) lenis.scrollTo(y, { immediate: true, force: true }); else scrollTo({ top: y, behavior: 'instant' }); };
  const slide = (y) => { if (lenis) lenis.scrollTo(y, { duration: 1.4, easing: (t) => 1 - Math.pow(1 - t, 4) }); else scrollTo({ top: y, behavior: reduced ? 'auto' : 'smooth' }); };
  // A long jump between chapters hides behind a Hyperframes wipe (the page moves while the plate covers it); a short one slides.
  const goTo = (y, kind) => {
    const far = Math.abs(y - (lenis ? lenis.scroll : scrollY)) > innerHeight * 1.2;
    if (kind && far && motion?.wipe(kind, () => jumpNow(y))) return;
    slide(y);
  };
  const targetY = { scan: () => chapterY[0] + 4, twin: () => chapterY[1] + 4, simulate: () => chapterY[2] + 4 };
  const WIPE = { scan: 'ink', twin: 'ink', simulate: 'ink', dataset: 'fold', evaluate: 'fold', close: 'cross', top: 'cross' };
  // keyboard and screen reader users land where the page went: move focus to the destination (not just the scroll position)
  const focusTo = (el) => { if (!el) return; if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1'); el.focus({ preventScroll: true }); };
  $$('a[href^="#"]').forEach((a) => a.addEventListener('click', (e) => {
    const id = a.getAttribute('href').slice(1), ch = a.dataset.chapter;
    let y = null, dest = null;
    if (targetY[ch]) { y = targetY[ch](); dest = stageEl; }
    else if (id === 'top') { y = 0; dest = $('#top'); }
    else { dest = document.getElementById(id); if (dest) y = dest.getBoundingClientRect().top + scrollY; }
    if (y == null) return; e.preventDefault();
    if (a.classList.contains('skip')) jumpNow(y); else goTo(y, WIPE[ch || id]);
    focusTo(dest);
  }));
  const warm = () => motion?.warm();
  $('#beam').addEventListener('pointerover', warm, { once: true }); $('#beam').addEventListener('focusin', warm, { once: true });
  $('.brand')?.addEventListener('pointerover', warm, { once: true });

  // ---------- small reveals ----------
  if (!reduced) {
    // the lift is a CSS variable folded into the .tilt transform, so the reveal never overwrites the tilt's own transform
    $$('.plate').forEach((el, i) => { gsap.set(el, { opacity: 0, '--ty': 14 }); ScrollTrigger.create({ trigger: el, start: 'top 90%', once: true, onEnter: () => gsap.to(el, { opacity: 1, '--ty': 0, duration: 0.7, delay: i * 0.05, ease: 'power3.out', clearProps: 'opacity,--ty' }) }); });
    ScrollTrigger.create({ trigger: '#eval', start: 'top 75%', once: true, onEnter: () => {
      $$('.axis__ci').forEach((el, i) => gsap.fromTo(el, { '--grow': 0 }, { '--grow': 1, duration: 0.9, delay: 0.1 + i * 0.07, ease: 'power3.out' }));
      $$('.axis__pt').forEach((el, i) => gsap.from(el, { opacity: 0, duration: 0.4, delay: 0.7 + i * 0.07 }));
    } });
    $$('.axis__ci').forEach((el) => el.style.setProperty('--grow', 0));
  }

  // ---------- refresh ----------
  // ScrollTrigger and Lenis already listen for resize; a second listener here only doubled the work. What neither can see is
  // late layout: web fonts and images finishing after boot move every offset, so refresh once they are in.
  const late = () => { lenis?.resize(); ScrollTrigger.refresh(); };
  document.fonts?.ready.then(late);
  if (document.readyState === 'complete') setTimeout(late, 0); else addEventListener('load', late, { once: true });
  ScrollTrigger.refresh();
  buildBeam();

  return { goTo, journeyUpdate, lenis, TOTAL, PHASES: ph, setP(P) { goTo(journeyY(P)); } };
}
