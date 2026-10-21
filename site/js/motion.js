// Arrival motion clips, rendered with Hyperframes (see motion/README.md). Three uses, all lazy and all optional:
//   loader    the title sheet (intro.webm / intro.mp4, poster intro.jpg) drawing itself while the data loads
//   wipes     a transparent WebM laid over the page while a long chapter jump happens underneath (ink, fold, cross)
//   pipeline  the 12 s scan-twin-simulate-dataset explainer in the Dataset chapter, played while it is on screen
// Nothing loads before it is needed: the pipeline clip waits until it is within 400 px of the viewport and the wipes warm up
// on the first hover or focus of the chapter nav. Reduced motion and Save-Data get posters only and plain scrolling. Every clip is decorative or explanatory; nothing on the page depends on it.
import { $, watchMedia } from './util.js';
import { readTheme } from './chrome.js';

const url = (f) => new URL(`../motion/${f}`, import.meta.url).href;
const saveData = () => !!(navigator.connection && navigator.connection.saveData);
// Safari does not render the alpha channel of VP9 WebM, so a wipe there would be an opaque slab.
const noAlpha = /^((?!chrome|android|crios|fxios).)*safari/i.test(navigator.userAgent);
const canWebm = () => { const v = document.createElement('video'); return !!v.canPlayType && v.canPlayType('video/webm; codecs="vp9"') !== ''; };

const WIPES = { ink: 'wipe-ink.webm', fold: 'wipe-fold.webm', cross: 'wipe-cross.webm' };
const COVER_AT = 0.5;                                  // seconds: the plate fully covers the page, swap the content now

export function initMotion({ reduced: reducedAtBoot, coarse }) {
  let reduced = reducedAtBoot;
  const m = {};

  const sources = (v, base) => {
    for (const [ext, type] of [['webm', 'video/webm'], ['mp4', 'video/mp4']]) {
      const s = document.createElement('source'); s.src = url(`${base}.${ext}`); s.type = type; v.appendChild(s);
    }
  };

  // ---------- loader intro ----------
  // The intro plays inside the loading sheet (see index.html, which adds the sources). Once the sheet has lifted, stop it and
  // let go of the decoded video, so it costs nothing while the reader scrolls.
  const lv = $('#loaderMotion');
  // Let the sheet draw long enough to be seen (the title and the first walls are down by 1.8 s), but never make the reader wait
  // for it: the hold ends if the video never started, and is capped at 3 s from the moment the data is ready.
  m.introHold = () => new Promise((resolve) => {
    if (!lv || reduced || !lv.childElementCount) return resolve();
    const t0 = performance.now();
    const tick = () => {
      const waited = performance.now() - t0;
      if (lv.currentTime >= 1.8 || lv.error || waited > 3000) return resolve();
      if (lv.currentTime === 0 && waited > 1200) return resolve();      // blocked or stalled: do not wait
      setTimeout(tick, 80);
    };
    tick();
  });
  m.loaderDone = () => {
    if (!lv) return;
    setTimeout(() => { lv.pause(); lv.innerHTML = ''; lv.removeAttribute('src'); lv.load(); }, 700);
  };

  // ---------- chapter wipes ----------
  const vids = {};
  let busy = false;
  const wipeVideo = (kind) => {
    if (vids[kind]) return vids[kind];
    const v = document.createElement('video');
    v.className = 'wipe'; v.muted = true; v.playsInline = true; v.preload = 'auto'; v.tabIndex = -1; v.setAttribute('aria-hidden', 'true');
    const s = document.createElement('source'); s.src = url(WIPES[kind]); s.type = 'video/webm'; v.appendChild(s);
    document.body.appendChild(v); v.load();
    return (vids[kind] = v);
  };
  const wipeAllowed = () => !reduced && !saveData() && !noAlpha && !readTheme().dark && canWebm();
  m.warm = () => { if (wipeAllowed()) Object.keys(WIPES).forEach(wipeVideo); };

  // Returns true when a wipe took over the jump (onCover then runs once, with the page hidden); false means do it yourself.
  m.wipe = (kind, onCover) => {
    if (busy || !WIPES[kind] || !wipeAllowed()) return false;
    busy = true;
    const v = wipeVideo(kind);
    let covered = false, finished = false, raf = 0;
    const cover = () => { if (covered) return; covered = true; onCover(); };
    const finish = () => {
      if (finished) return; finished = true; cancelAnimationFrame(raf); clearTimeout(guard);
      cover(); v.pause(); v.classList.remove('is-live'); busy = false;
    };
    const guard = setTimeout(finish, 2600);                            // never leave the page covered or the jump undone
    const watch = () => { if (v.currentTime >= COVER_AT) cover(); if (!finished) raf = requestAnimationFrame(watch); };
    v.addEventListener('ended', finish, { once: true }); v.addEventListener('error', finish, { once: true });
    try { v.currentTime = 0; } catch { /* not seekable yet: it starts at 0 anyway */ }
    v.classList.add('is-live');
    v.play().then(() => { raf = requestAnimationFrame(watch); }).catch(finish);
    return true;
  };

  // ---------- pipeline explainer ----------
  const pv = $('#pipelineClip'), toggle = $('#reelBtn'), reel = $('#reel');
  if (pv && reel) {
    let loaded = false, inView = false, userPaused = false, ended = false;
    const label = () => { toggle.textContent = ended ? 'Replay' : pv.paused ? 'Play' : 'Pause'; };
    const load = () => {
      if (loaded) return; loaded = true;
      pv.poster = url('pipeline.jpg'); sources(pv, 'pipeline'); pv.preload = 'metadata'; pv.load();
    };
    const sync = () => {
      if (!loaded) return;
      if (inView && !userPaused && !ended && !reduced && !saveData() && !document.hidden) pv.play().catch(() => {}); else pv.pause();
    };
    new IntersectionObserver(([e]) => { if (e.isIntersecting) load(); }, { rootMargin: '400px 0px' }).observe(reel);
    new IntersectionObserver(([e]) => { inView = e.isIntersecting; sync(); }, { threshold: 0.6 }).observe(pv);
    pv.addEventListener('canplay', sync);                          // sources arrive after the view check: start once playable
    pv.addEventListener('play', () => { ended = false; label(); }); pv.addEventListener('pause', label);
    pv.addEventListener('ended', () => { ended = true; label(); });
    toggle.addEventListener('click', () => {
      load();
      if (ended) { pv.currentTime = 0; userPaused = false; pv.play().catch(() => {}); }
      else if (pv.paused) { userPaused = false; pv.play().catch(() => {}); }
      else { userPaused = true; pv.pause(); }
    });
    document.addEventListener('visibilitychange', sync);
    label();
  }

  watchMedia('(prefers-reduced-motion: reduce)', (v) => { reduced = v; if (pv && v) pv.pause(); });
  return m;
}
