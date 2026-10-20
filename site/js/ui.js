// HUD wiring: tasks, playback, scrubber, layers, readouts, picking, index. (The theme toggle lives in chrome.js.)
import { FAMILIES, frameUrl } from './data.js';
import { familyLabel } from './sections.js';
import { fmt, clamp, $, $$ } from './util.js';

export function initUI({ stage, data, announce }) {
  const stageEl = $('#stage');
  const ui = { family: null };
  const J = stage.J;

  // ---------- tasks ----------
  const list = $('#taskList'), tray = $('#tray'), trayToggle = $('#trayToggle'), trayCur = $('#trayCur');
  const cards = {};
  for (const f of FAMILIES) {
    const s = data.stats.families[f];
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'task tilt'; b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', 'false'); b.dataset.family = f;
    b.innerHTML = `<img src="${frameUrl(f, 'ego_view', 'mid')}" width="64" height="64" alt="" decoding="async"><span class="task__t">${s.instruction}</span><span class="task__m mono"><span class="task__d">${s.duration_s.toFixed(1)} s</span><span class="task__f">${familyLabel(f)}</span></span>`;
    b.title = `${s.instruction} (${familyLabel(f)})`;
    b.addEventListener('click', () => selectTask(f));
    list.appendChild(b); cards[f] = b;
  }
  list.addEventListener('keydown', (e) => {                    // roving radio group
    const i = FAMILIES.indexOf(ui.want || ui.family);
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return; e.preventDefault();
    const nf = FAMILIES[(i + d + FAMILIES.length) % FAMILIES.length]; selectTask(nf); cards[nf].focus();
  });
  const setTray = (open) => { tray.classList.toggle('is-open', open); trayToggle.setAttribute('aria-expanded', String(open)); };
  trayToggle.addEventListener('click', () => setTray(!tray.classList.contains('is-open')));
  ui.setTray = setTray;

  const rd = { time: $('#rdTime'), frame: $('#rdFrame'), result: $('#rdResult'), min: $('#rdMin'), live: $('#rdLive') };
  const scrub = $('#scrub'), mark = $('#scrubMark'), timeRead = $('#timeRead'), playBtn = $('#playBtn');
  const cache = {};
  const put = (k, el, txt) => { if (cache[k] !== txt) { cache[k] = txt; el.textContent = txt; } };

  let seq = 0, userPaused = false;
  const markCards = (f) => { for (const k in cards) { cards[k].setAttribute('aria-checked', String(k === f)); cards[k].tabIndex = k === f ? 0 : -1; } };
  // Latest click wins: each call takes a token, and a slower earlier load that resolves late is dropped.
  async function selectTask(f, { silent = false } = {}) {
    if (f === ui.family && !ui.want) return;
    const my = ++seq; ui.want = f;
    markCards(f);                                              // respond on press, before the episode arrives
    const card = cards[f]; card.classList.add('is-loading'); card.setAttribute('aria-busy', 'true');
    let ep;
    try { ep = await data.loadEpisode(f); }
    catch (err) {
      console.warn('episode failed to load', f, err);
      card.classList.remove('is-loading'); card.removeAttribute('aria-busy');
      if (my === seq) { ui.want = null; markCards(ui.family); announce(`Could not load the ${familyLabel(f)} episode. Try again.`); }
      return;
    }
    card.classList.remove('is-loading'); card.removeAttribute('aria-busy');
    if (my !== seq) return;
    ui.want = null;
    if (f === ui.family) return;
    const wasPlaying = stage.playing;
    ui.family = f;
    stage.setEpisode(ep);
    const s = data.stats.families[f];
    trayCur.textContent = s.instruction;
    scrub.max = String(ep.n - 1); scrub.value = '0';
    $('.scrub').style.setProperty('--secs', String(Math.max(1, Math.round(stage.duration))));
    const t = stage.closestApproachT;
    if (t != null) { mark.hidden = false; mark.style.left = `calc(${(t / stage.duration) * 100}% )`; mark.title = `Recorded closest approach to a person: ${ep.min_human_distance_m.toFixed(3)} m at control step ${ep.safety.min_distance_step}`; } else mark.hidden = true;
    put('result', rd.result, ep.success ? (ep.human_contact ? 'success, contact' : 'success') : 'failed');
    put('min', rd.min, `${ep.min_human_distance_m.toFixed(2)}`);
    stage.seekFrame(0);
    if (wasPlaying || (J.autoplay && !stage.reduced && !userPaused)) stage.play();
    if (!silent) announce(`Task: ${s.instruction} ${ep.success ? 'Succeeded.' : 'Failed.'} Closest person ${ep.min_human_distance_m.toFixed(2)} metres.`);
    select(null);
  }
  ui.selectTask = selectTask;

  // ---------- playback ----------
  const setPlayState = (p) => { playBtn.dataset.state = p ? 'playing' : 'paused'; playBtn.setAttribute('aria-label', p ? 'Pause' : 'Play'); };
  stage.cb.play = setPlayState; setPlayState(stage.playing);
  const userToggle = () => { stage.toggle(); userPaused = !stage.playing; };
  playBtn.addEventListener('click', userToggle);
  playBtn.setAttribute('aria-keyshortcuts', 'K');

  let scrubbing = false;
  const scrubText = (v = +scrub.value) => {
    const f = Math.round(v), txt = `frame ${f} of ${stage.ep.n - 1}, ${(f / stage.ep.fps).toFixed(1)} seconds`;
    if (cache.vt !== txt) { cache.vt = txt; scrub.setAttribute('aria-valuetext', txt); }
  };
  scrub.addEventListener('pointerdown', () => { scrubbing = true; stageEl.classList.add('bench-seen'); });
  playBtn.addEventListener('click', () => stageEl.classList.add('bench-seen'));
  addEventListener('pointerup', () => { scrubbing = false; }); addEventListener('pointercancel', () => { scrubbing = false; });
  scrub.addEventListener('input', () => { stage.pause(); userPaused = true; stage.seekFrame(+scrub.value); scrubText(); });
  scrub.addEventListener('keydown', (e) => {
    const step = e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'PageUp' ? 15 : e.key === 'PageDown' ? -15 : 0;
    if (!step) return; e.preventDefault(); stage.pause(); userPaused = true;
    const f = clamp(Math.round(+scrub.value) + step, 0, stage.ep.n - 1); scrub.value = String(f); stage.seekFrame(f); scrubText();
  });
  addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (e.key === 'k' && !e.metaKey && !e.ctrlKey && tag !== 'input' && tag !== 'textarea' && J.autoplay) { userToggle(); }
    if (e.key === 'Escape') {
      if (!$('#indexPanel').hidden) { toggleIndex(false); return; }
      if (!$('#callout').hidden) { select(null); return; }
      if (stage.mode === 'explore') stage.setMode('tour');
    }
  });

  // ---------- readouts, throttled by the stage ----------
  stage.cb.frame = (s) => {
    put('time', rd.time, `${fmt.t(s.t)} / ${fmt.t(s.dur)} s`);
    put('frame', rd.frame, `${String(Math.round(s.f)).padStart(3, '0')} / ${String(s.n - 1).padStart(3, '0')}`);
    put('live', rd.live, Number.isFinite(s.live) ? `/ ${s.live.toFixed(2)} m` : '/ n/a');
    put('tr', timeRead, `${fmt.t(s.t)} s`);
    if (!scrubbing && document.activeElement !== scrub) scrub.value = String(s.f);
    scrubText(s.f);
    if (callout.name) refreshCallout();
  };

  // ---------- layers ----------
  $$('[data-layer]').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.layer, on = b.getAttribute('aria-pressed') !== 'true';
    stage.user[k] = on; b.setAttribute('aria-pressed', String(on));
  }));
  const modeBtn = $('#modeBtn');
  modeBtn.addEventListener('click', () => stage.setMode(stage.mode === 'explore' ? 'tour' : 'explore'));
  stage.cb.mode = (m) => { modeBtn.setAttribute('aria-pressed', String(m === 'explore')); modeBtn.textContent = m === 'explore' ? 'Back to tour' : 'Explore'; stageEl.classList.toggle('is-explore', m === 'explore'); if (m === 'explore') stageEl.classList.add('bench-seen'); announce(m === 'explore' ? 'Explore mode. Drag to orbit, wheel to zoom, Escape to return.' : 'Tour mode.'); };

  // ---------- picking, hover, callout ----------
  const callout = { el: $('#callout'), kind: $('#coKind'), name: null, nameEl: $('#coName'), rows: $('#coRows') };
  const canvas = $('#gl');
  let down = null, hoverRaf = 0, hx = 0, hy = 0;
  canvas.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down) return; const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y); down = null;
    if (moved > 6) return;
    if (J.build < 0.5) return;
    const name = stage.pick(e.clientX, e.clientY);
    select(name);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (e.buttons || e.pointerType === 'touch') return; hx = e.clientX; hy = e.clientY;
    if (!hoverRaf) hoverRaf = requestAnimationFrame(() => { hoverRaf = 0; if (J.build < 0.5) return; const n = stage.pick(hx, hy); stage.setHover(n); stageEl.classList.toggle('is-hover', !!n); });
  });
  canvas.addEventListener('pointerleave', () => { stage.setHover(null); stageEl.classList.remove('is-hover'); });
  $('#calloutX').addEventListener('click', () => select(null));

  function describe(name) {
    const { rooms, stats } = data, ep = stage.ep, e = stage.entry(name); if (!e) return null;
    const p = e.group.position, xyz = `${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)} m`;
    const fx = rooms.fixtures.find((f) => f.id === name);
    const part = rooms.parts.find((q) => name === q.joint || name === q.joint + '_lever');
    const obj = rooms.objects.find((o) => o.id === name);
    const rows = [];
    if (/^link[1-7]$/.test(name) || name === 'hand' || name.startsWith('finger') || name === 'robot_base') {
      const j = stage.frameState.joints;
      if (/^link[1-7]$/.test(name)) { const i = +name.slice(4); rows.push(['joint', `joint${i}, revolute`], ['angle now', `${j[i - 1].toFixed(3)} rad (${(j[i - 1] * 57.2958).toFixed(1)} deg)`]); }
      else if (name === 'robot_base') rows.push(['role', 'fixed base, placed for the task']);
      else rows.push(['role', name === 'hand' ? 'gripper body' : 'gripper finger, prismatic'], ['opening now', `${(j[7] * 1000).toFixed(1)} mm`]);
      rows.push(['arm', stats.sim.arm], ['position now', xyz]);
      return { kind: 'Robot', title: name, rows };
    }
    if (name.startsWith('person_')) {
      const limb = name.split('_').length > 2;
      rows.push(['model', stats.sim.people_model], [limb ? 'limb of' : 'position now', limb ? name.split('_').slice(0, 2).join('_') : xyz], ['closest to robot', `${ep.min_human_distance_m.toFixed(3)} m, recorded`]);
      return { kind: limb ? 'Person, limb' : 'Person', title: name, rows };
    }
    if (fx) {
      rows.push(['type', fx.type], ['category', fx.source_category], ['size', fx.size.map((v) => v.toFixed(2)).join(' x ') + ' m'], ['position', fx.position.map((v) => v.toFixed(2)).join(', ') + ' m'], ['yaw', `${(fx.yaw * 57.2958).toFixed(0)} deg`], ['island', String(fx.island)]);
      const kids = rooms.parts.filter((q) => q.fixture === fx.id).length; if (kids) rows.push(['moving parts', String(kids)]);
      return { kind: 'Fixture', title: fx.id, rows };
    }
    if (part) {
      const slide = part.kind === 'slide';
      rows.push(['joint', `${part.joint}, ${part.kind}`], ['fixture', part.fixture], ['range', slide ? `0 to ${part.open.toFixed(2)} m` : `0 to ${part.open.toFixed(2)} rad (${(part.open * 57.2958).toFixed(0)} deg)`], ['handle site', part.site]);
      if (ep.task?.joint === part.joint) { const q = ep.physics_detail?.qpos ?? ep.physics_detail?.drawer_qpos; rows.push(['this task', q != null ? `moves it to ${q.toFixed(3)} ${slide ? 'm' : 'rad'}` : 'moves it']); }
      return { kind: slide ? 'Part, slide' : 'Part, hinge', title: name, rows };
    }
    if (obj) {
      const c = rooms.object_catalogue[obj.catalog_id] || {};
      rows.push(['label', obj.label], ['size', obj.size.map((v) => v.toFixed(2)).join(' x ') + ' m'], ['mass', c.mass_kg != null ? `${c.mass_kg} kg` : 'n/a'], ['friction', c.friction ?? 'n/a'], ['start', obj.position.map((v) => v.toFixed(2)).join(', ') + ' m'], ['now', xyz]);
      return { kind: 'Object', title: obj.id, rows };
    }
    return { kind: 'Body', title: name, rows: [['position now', xyz]] };
  }
  function refreshCallout() {
    const d = describe(callout.name); if (!d) return;
    const sig = d.rows.map((r) => r.join('|')).join('\n');
    if (callout.sig === sig) return; callout.sig = sig;
    callout.kind.textContent = d.kind; callout.nameEl.textContent = d.title;
    callout.rows.innerHTML = '';
    for (const [k, v] of d.rows) { const r = document.createElement('div'); const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = k; dd.textContent = v; r.append(dt, dd); callout.rows.appendChild(r); }
  }
  function select(name, focus = false) {
    callout.name = name; callout.sig = null;
    stage.setSelect(name);
    callout.el.hidden = !name; $('#side').classList.toggle('has-callout', !!name);
    $$('#indexCols button').forEach((b) => b.setAttribute('aria-current', String(b.dataset.name === name)));
    if (name) { refreshCallout(); announce(`${callout.kind.textContent}: ${callout.nameEl.textContent}`); if (focus) stage.focusOn(name); }
  }
  ui.select = select;

  // ---------- keyboard index of everything pickable ----------
  const idxBtn = $('#indexBtn'), idxPanel = $('#indexPanel');
  function buildIndex() {
    const cols = $('#indexCols'); cols.innerHTML = '';
    const group = (title, names) => {
      names = names.filter((n) => stage.entry(n)); if (!names.length) return;
      const d = document.createElement('div'); d.innerHTML = `<h4>${title}</h4>`;
      for (const n of names) { const b = document.createElement('button'); b.type = 'button'; b.dataset.name = n; b.textContent = n; b.addEventListener('click', () => { select(n, true); toggleIndex(false); }); d.appendChild(b); }
      cols.appendChild(d);
    };
    const { rooms } = data;
    group('Fixtures', rooms.fixtures.map((f) => f.id));
    group('Parts', rooms.parts.map((p) => (stage.entry(p.joint) ? p.joint : p.joint + '_lever')));
    group('Objects', rooms.objects.map((o) => o.id));
    group('Robot', ['robot_base', 'link1', 'link2', 'link3', 'link4', 'link5', 'link6', 'link7', 'hand']);
    group('People', ['person_0', 'person_1']);
  }
  function toggleIndex(open) {
    idxPanel.hidden = !open; idxBtn.setAttribute('aria-expanded', String(open));
    if (open) { buildIndex(); idxPanel.querySelector('button')?.focus(); } else if (document.activeElement && idxPanel.contains(document.activeElement)) idxBtn.focus();
  }
  idxBtn.addEventListener('click', () => toggleIndex(idxPanel.hidden));

  stage.setFeeds($('#feedEgo'), $('#feedWrist'));
  setTray(false);
  return ui;
}
