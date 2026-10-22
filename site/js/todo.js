// The revision schedule in chapter 05: every item left to build, grouped by what it needs. All of it is read from data/todo.json,
// which is built from the merged and open PRs and the README to-do. Nothing is marked done unless its PR is merged on main.
const REPO = 'https://github.com/AvnehSBhatia/ExeaLabsNvidiaHacks';
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// status -> filter chip, mark and spoken word
const STATUS = {
  done: { word: 'Shipped', filter: 'done' },
  review: { word: 'In review', filter: 'review' },
  todo: { word: 'Next', filter: 'todo' },
  blocked: { word: 'Blocked', filter: 'blocked' },
};
const FILTERS = [['all', 'All'], ['done', 'Shipped'], ['review', 'In review'], ['todo', 'Next'], ['blocked', 'Blocked']];
const SIZE = { S: 'under half a day', M: 'about a day', L: 'several days' };

// one diamond per status, drawn in the same language as the rest of the sheet: filled, half, hollow, cross-hatched
const D = 'M8 1.5 14.5 8 8 14.5 1.5 8Z';
const MARKS = {
  done: `<path d="${D}" class="m-fill"/>`,
  review: `<path d="M8 1.5 1.5 8 8 14.5Z" class="m-sig"/><path d="${D}" class="m-line"/>`,
  todo: `<path d="${D}" class="m-line"/>`,
  blocked: `<path d="M5.2 5.2 10.8 10.8M8 2.9 13.1 8M2.9 8 8 13.1M10.8 5.2 5.2 10.8M8 2.9 2.9 8M13.1 8 8 13.1" class="m-hatch"/><path d="${D}" class="m-line"/>`,
};
const mark = (s) => `<svg class="sched__mark" viewBox="0 0 16 16" aria-hidden="true" focusable="false">${MARKS[s]}</svg>`;

const prLink = (n) => `<a class="sched__chip sched__chip--link" href="${REPO}/pull/${n}" target="_blank" rel="noopener noreferrer" aria-label="Pull request ${n}, opens in a new tab">#${n}</a>`;
const issueLink = (n) => `<a class="sched__chip sched__chip--link sched__chip--issue" href="${REPO}/issues/${n}" target="_blank" rel="noopener noreferrer" aria-label="Issue ${n}, opens in a new tab">issue #${n}</a>`;

function rowHTML(it) {
  const prs = [].concat(it.pr || []);
  const size = it.size ? `<span class="sched__chip" title="${esc(SIZE[it.size] || it.size)}"><span class="sr-only">Size </span>${esc(it.size)}</span>` : '';
  const prio = it.priority ? `<span class="sched__prio sched__prio--${esc(it.priority)}">${esc(it.priority)}</span>` : '';
  const note = it.note ? `<small class="sched__note">${esc(it.note)}</small>` : '';
  const who = (it.authors || []).length ? `<span class="sched__chip" title="Worked on by"><span class="sr-only">Worked on by </span>${it.authors.map(esc).join(', ')}</span>` : '';
  const links = prs.map(prLink).join('') + (it.issue && !prs.length ? issueLink(it.issue) : '');
  return `<li class="sched__row" data-status="${esc(it.status)}">
    <span class="sched__st">${mark(it.status)}<span class="sr-only">${STATUS[it.status].word}: </span></span>
    <span class="sched__id mono">${esc(it.id)}</span>
    <span class="sched__title">${esc(it.title)}${note}</span>
    <span class="sched__meta">${prio}${size}${who}${links}</span>
  </li>`;
}

function groupHTML(g, i, open) {
  const bodyId = `schedBody${i}`, btnId = `schedBtn${i}`;
  return `<section class="sched__group" data-group="${esc(g.id)}">
    <h4 class="sched__gh"><button type="button" class="sched__toggle" id="${btnId}" aria-expanded="${open}" aria-controls="${bodyId}">
      <i class="sched__tick" aria-hidden="true"></i>
      <span class="sched__gname">${esc(g.title)}</span>
      <span class="sched__gblurb">${esc(g.blurb)}</span>
      <span class="sched__gcount mono" data-total="${g.items.length}">${g.items.length}</span>
    </button></h4>
    <div class="sched__body${open ? ' is-open' : ''}" id="${bodyId}" role="region" aria-labelledby="${btnId}"><div class="sched__inner"><ol class="sched__list">${g.items.map(rowHTML).join('')}</ol></div></div>
  </section>`;
}

export function renderTodo(todo) {
  const wrap = document.getElementById('schedWrap');
  if (!wrap) return;
  if (!todo || !Array.isArray(todo.groups)) { wrap.hidden = true; return; }   // the schedule is optional: the chapter reads fine without it
  const c = todo.counts, prs = todo.prs;
  const asOf = new Date(todo.as_of + 'T12:00:00');
  const asOfText = isNaN(asOf) ? todo.as_of : asOf.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  document.getElementById('schedAsOf').textContent = `as of ${asOfText}`;

  // progress rule: one hairline split by status, with ticks, so the count can be read at a glance
  const seg = (k) => `<i class="sched__seg sched__seg--${k}" style="flex-grow:${c[k]}"></i>`;
  document.getElementById('schedSum').innerHTML =
    `<p class="sched__line"><b>${c.done}</b> shipped, <b>${c.review}</b> in review, <b>${c.todo}</b> next, <b>${c.blocked}</b> blocked, of <b>${c.total}</b> items. ${prs.merged} pull requests merged, ${prs.open} open.</p>
     <div class="sched__rule" aria-hidden="true">${['done', 'review', 'todo', 'blocked'].map(seg).join('')}</div>`;

  const groupsEl = document.getElementById('schedGroups');
  groupsEl.innerHTML = todo.groups.map((g, i) => groupHTML(g, i, i < 2)).join('');

  const chipsEl = document.getElementById('schedChips');
  const count = (f) => (f === 'all' ? c.total : c[f]);
  chipsEl.innerHTML = FILTERS.map(([f, label]) => `<button type="button" class="chip" data-f="${f}" aria-pressed="${f === 'all'}"><span>${label}</span><span class="sched__n">${count(f)}</span></button>`).join('');
  const shown = document.getElementById('schedShown');

  const refresh = () => { window.ScrollTrigger?.refresh(); window.arrival?.scroll?.lenis?.resize?.(); };
  let filter = 'all';

  const apply = () => {
    let visible = 0;
    groupsEl.querySelectorAll('.sched__group').forEach((sec) => {
      const rows = sec.querySelectorAll('.sched__row');
      let n = 0;
      rows.forEach((r) => { const on = filter === 'all' || r.dataset.status === filter; r.hidden = !on; if (on) n++; });
      sec.hidden = n === 0;
      visible += n;
      const cnt = sec.querySelector('.sched__gcount');
      cnt.textContent = filter === 'all' ? cnt.dataset.total : `${n} of ${cnt.dataset.total}`;
      if (filter !== 'all' && n) setOpen(sec, true);                       // a filter opens every group that has a match
    });
    shown.textContent = filter === 'all' ? '' : `Showing ${visible} of ${c.total} items.`;
    refresh();
  };

  function setOpen(sec, open) {
    const btn = sec.querySelector('.sched__toggle'), body = sec.querySelector('.sched__body');
    btn.setAttribute('aria-expanded', String(open));
    body.classList.toggle('is-open', open);
  }

  chipsEl.addEventListener('click', (e) => {
    const b = e.target.closest('.chip'); if (!b) return;
    filter = b.dataset.f;
    chipsEl.querySelectorAll('.chip').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    apply();
  });
  groupsEl.addEventListener('click', (e) => {
    const b = e.target.closest('.sched__toggle'); if (!b) return;
    setOpen(b.closest('.sched__group'), b.getAttribute('aria-expanded') !== 'true');
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) refresh();   // no transition to wait for
  });
  // the section height changes while it animates; recompute scroll offsets once it has settled
  groupsEl.addEventListener('transitionend', (e) => { if (e.target.classList?.contains('sched__body') && e.propertyName === 'grid-template-rows') refresh(); });

  wrap.hidden = false;
}
