// Shared helpers: formatting, DOM, fetch with timeout, chart defaults, data-source status.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function h(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

const nf = (d) => new Intl.NumberFormat('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d });
const cache = {};
export function num(v, d = 2) {
  if (v == null || !Number.isFinite(v)) return '—';
  return (cache[d] ??= nf(d)).format(v);
}
export function price(v) {
  if (v == null || !Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  return num(v, a >= 1000 ? 2 : a >= 1 ? 2 : a >= 0.01 ? 4 : 6);
}
export function pct(v, d = 2) {
  if (v == null || !Number.isFinite(v)) return '—';
  return (v > 0 ? '+' : '') + num(v, d) + '%';
}
export function compact(v, d = 1) {
  if (v == null || !Number.isFinite(v)) return '—';
  const a = Math.abs(v), s = v < 0 ? '-' : '';
  if (a >= 1e12) return s + num(a / 1e12, d) + ' T';
  if (a >= 1e9) return s + num(a / 1e9, d) + ' B';
  if (a >= 1e6) return s + num(a / 1e6, d) + ' M';
  if (a >= 1e3) return s + num(a / 1e3, d) + ' K';
  return s + num(a, d);
}
export const signCls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : 'muted');

export async function getJSON(url, { timeout = 15000, text = false } = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctl.signal, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return text ? await r.text() : await r.json();
  } finally {
    clearTimeout(t);
  }
}

export function fmtTime(ts, tz = 'America/New_York', withSec = true) {
  return new Intl.DateTimeFormat('es-MX', {
    timeZone: tz, hour: '2-digit', minute: '2-digit', ...(withSec ? { second: '2-digit' } : {}), hour12: false,
  }).format(ts);
}
export function fmtDate(d) {
  const dt = typeof d === 'string' ? new Date(d + (d.length === 10 ? 'T12:00:00' : '')) : d;
  return new Intl.DateTimeFormat('es-MX', { day: '2-digit', month: 'short', year: 'numeric' }).format(dt);
}

// ---------- chart defaults (Lightweight Charts) ----------
export const chartTheme = {
  layout: { background: { color: 'transparent' }, textColor: '#a7b0bb', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
  grid: { vertLines: { color: '#161d25' }, horzLines: { color: '#161d25' } },
  rightPriceScale: { borderColor: '#1f2731' },
  timeScale: { borderColor: '#1f2731', timeVisible: true, secondsVisible: false },
  crosshair: { mode: 0 },
  localization: { locale: 'es-MX' },
};
// Lightweight Charts renders UTC; show axis and crosshair times in a chosen time zone instead.
export function makeChart(el, opts = {}, tz = 'America/New_York') {
  // Intraday points are UTC timestamps; daily points arrive as 'YYYY-MM-DD' strings or
  // {year, month, day} objects and must stay on their calendar day (format them in UTC).
  const tf = (t, o) => {
    if (typeof t === 'number') return new Intl.DateTimeFormat('es-MX', { timeZone: tz, hour12: false, ...o }).format(t * 1000);
    const ms = typeof t === 'string' ? Date.parse(t + 'T00:00:00Z') : Date.UTC(t.year, t.month - 1, t.day);
    const { hour, minute, ...dateOnly } = o;
    return new Intl.DateTimeFormat('es-MX', { timeZone: 'UTC', ...(Object.keys(dateOnly).length ? dateOnly : { day: '2-digit', month: 'short' }), year: '2-digit' }).format(ms);
  };
  const chart = LightweightCharts.createChart(el, {
    ...chartTheme,
    localization: { locale: 'es-MX', timeFormatter: (t) => tf(t, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) },
    ...opts,
    timeScale: {
      ...chartTheme.timeScale,
      tickMarkFormatter: (t, type) => (type < 3 ? tf(t, { day: '2-digit', month: 'short' }) : tf(t, { hour: '2-digit', minute: '2-digit' })),
      ...(opts.timeScale ?? {}),
    },
    autoSize: true,
  });
  return chart;
}
export const candleStyle = {
  upColor: '#22ab94', downColor: '#f23645', borderUpColor: '#22ab94', borderDownColor: '#f23645',
  wickUpColor: '#22ab94', wickDownColor: '#f23645',
};

// ---------- canvas helper (HiDPI) ----------
export function fitCanvas(canvas, height) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  canvas.style.height = height + 'px';
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h: height };
}

// ---------- data-source status registry (rendered in the footer) ----------
const sources = new Map();
const listeners = new Set();
const KIND = { live: ['tag-live', 'EN VIVO'], sim: ['tag-sim', 'SIM'], daily: ['tag-daily', 'DIARIO'], annual: ['tag-daily', 'ANUAL'], off: ['tag-off', 'SIN CONFIGURAR'], err: ['tag-err', 'ERROR'], wait: ['tag-off', 'CONECTANDO'] };
export const status = {
  set(id, label, kind, detail = '') {
    sources.set(id, { label, kind, detail });
    listeners.forEach((f) => f());
  },
  clear(ids) { ids.forEach((i) => sources.delete(i)); listeners.forEach((f) => f()); },
  onChange(f) { listeners.add(f); },
  render(el) {
    el.innerHTML = [...sources.values()].map(({ label, kind, detail }) => {
      const [cls, txt] = KIND[kind] ?? KIND.off;
      return `<span title="${esc(detail)}"><span class="tag ${cls}">${txt}</span>${esc(label)}</span>`;
    }).join('');
  },
};
export const tag = (kind) => { const [cls, txt] = KIND[kind]; return `<span class="tag ${cls}">${txt}</span>`; };

// Seeded PRNG so simulated open interest is stable across reloads within a day.
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function hashStr(s) {
  let x = 2166136261;
  for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); }
  return x >>> 0;
}
export function gauss(r) {
  let u = 0, v = 0;
  while (u === 0) u = r();
  while (v === 0) v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
