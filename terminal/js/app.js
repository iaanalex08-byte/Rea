import { $, $$, esc, fmtTime, status } from './util.js';

const VIEWS = {
  qmap: () => import('./views/qmap.js'),
  crypto: () => import('./views/crypto.js'),
  forex: () => import('./views/forex.js'),
  vol: () => import('./views/vol.js'),
  insiders: () => import('./views/insiders.js'),
  macro: () => import('./views/macro.js'),
};

const viewEl = $('#view');
let unmount = null;
let token = 0;

async function show(name) {
  if (!VIEWS[name]) name = 'qmap';
  $$('.tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === name)));
  const my = ++token;
  if (unmount) { try { unmount(); } catch (e) { console.error(e); } unmount = null; }
  viewEl.innerHTML = '';
  // Each view gets its own container: late async callbacks from a view the user already left
  // keep writing into their detached container instead of failing or touching the new view.
  const host = document.createElement('div');
  host.style.display = 'contents';
  viewEl.append(host);
  try {
    const mod = await VIEWS[name]();
    if (my !== token) return;
    const off = (await mod.mount(host)) ?? null;
    // The user may have switched tabs while an async mount was still connecting.
    if (my !== token) { off?.(); return; }
    unmount = off;
  } catch (e) {
    console.error(e);
    host.innerHTML = `<div class="panel"><div class="empty"><h3>No se pudo cargar esta herramienta</h3>${esc(e.message)}</div></div>`;
  }
}

$$('.tabs button').forEach((b) => b.addEventListener('click', () => { location.hash = b.dataset.view; }));
window.addEventListener('hashchange', () => show(location.hash.slice(1)));
show(location.hash.slice(1) || 'qmap');

// ---------- clocks & US cash-session state ----------
function sessionState(now) {
  const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: 'numeric', hour12: false }).formatToParts(now);
  const g = (t) => p.find((x) => x.type === t).value;
  const wd = g('weekday');
  const m = (+g('hour') % 24) * 60 + +g('minute');
  if (wd === 'Sat' || wd === 'Sun') return ['Mercado cerrado', 'closed'];
  if (m >= 570 && m < 960) return ['Sesión abierta', 'open'];
  if (m >= 240 && m < 570) return ['Pre-mercado', 'closed'];
  if (m >= 960 && m < 1200) return ['Post-mercado', 'closed'];
  return ['Mercado cerrado', 'closed'];
}
function tickClock() {
  const now = new Date();
  $('#clock-ny').textContent = fmtTime(now, 'America/New_York');
  $('#clock-mx').textContent = fmtTime(now, 'America/Mexico_City');
  const [txt, cls] = sessionState(now);
  const s = $('#session');
  s.textContent = txt; s.className = 'session ' + cls;
}
tickClock();
setInterval(tickClock, 1000);

const srcEl = $('#sources');
status.onChange(() => status.render(srcEl));
