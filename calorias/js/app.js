import * as S from './store.js';
import { searchBase } from './foods.js';
import { searchProducts, byBarcode } from './api.js';
import { scanBarcode } from './scanner.js';

// ---------- helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 0) => (Number.isFinite(v) ? v.toLocaleString('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—');
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const ICON = {
  left: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  right: '<svg viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  scan: '<svg viewBox="0 0 24 24"><path d="M4 7V5a1 1 0 0 1 1-1h2M17 4h2a1 1 0 0 1 1 1v2M20 17v2a1 1 0 0 1-1 1h-2M7 20H5a1 1 0 0 1-1-1v-2M8 8v8M11 8v8M14 8v8M17 8v8"/></svg>',
};
const SRC = { base: 'Básico', off: 'Producto', custom: 'Mío', receta: 'Receta' };

let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}

function dayTitle(key) {
  const today = S.dateKey();
  if (key === today) return 'Hoy';
  if (key === S.shiftDate(today, -1)) return 'Ayer';
  const d = new Date(key + 'T12:00:00');
  const s = d.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'short' });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function qtyLabel(food, grams) {
  const sv = food.serving;
  if (sv && sv.g > 0) {
    const n = grams / sv.g;
    const r = Math.round(n * 4) / 4;
    if (r > 0 && Math.abs(n - r) < 0.01) return `${+r.toFixed(2)} × ${sv.label} · ${fmt(grams)} g`;
  }
  return `${fmt(grams)} g`;
}

// ---------- theme ----------
function applyTheme() {
  let t = 'auto';
  try { t = localStorage.getItem('orbe.cal.theme') || 'auto'; } catch { /* storage blocked */ }
  if (t === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', t);
}
applyTheme();

// ---------- router ----------
let currentDate = S.dateKey();
let progressRange = 7;
const view = $('#view');

function route() {
  let tab = location.hash.slice(1) || 'hoy';
  if (!['hoy', 'progreso', 'perfil'].includes(tab)) tab = 'hoy';
  if (!S.get().profile && tab !== 'perfil') { location.replace('#perfil'); return; }
  $$('.tabbar a').forEach((a) => (a.dataset.tab === tab ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  $('#fab').hidden = !S.get().profile;
  if (tab === 'hoy') renderHoy();
  else if (tab === 'progreso') renderProgreso();
  else renderPerfil();
}
window.addEventListener('hashchange', route);
// Re-render on every data change, except while the user is typing in a field of the view.
S.onChange(() => {
  const a = document.activeElement;
  const typing = a && view.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) && a.type !== 'file';
  if (!typing) route();
});
$('#fab').addEventListener('click', () => openAdd({ meal: guessMeal() }));

function guessMeal() {
  const h = new Date().getHours();
  return h < 11 ? 'desayuno' : h < 17 ? 'comida' : h < 21 ? 'cena' : 'snacks';
}

// =====================================================================================
// HOY
// =====================================================================================
function renderHoy() {
  const g = S.goals();
  const d = S.day(currentDate);
  const t = S.totals(d.entries);
  const today = S.dateKey();
  const left = g.kcal - t.kcal;
  const R = 56, C = 2 * Math.PI * R;
  const pct = clamp(t.kcal / g.kcal, 0, 1);
  const macro = (k, label, color) => {
    const v = t[k], goal = g[k];
    return `<div class="macro"><div class="lab"><span>${label}</span><span><b class="num">${fmt(v)}</b> / ${fmt(goal)} g</span></div>
      <div class="track"><i style="width:${clamp((v / goal) * 100, 0, 100)}%;background:${color}"></i></div></div>`;
  };
  const glasses = Math.max(1, Math.round(g.water / 250));
  const full = Math.floor((d.water || 0) / 250);
  const yesterday = S.day(S.shiftDate(currentDate, -1));

  view.innerHTML = `
    <div class="datebar">
      <button class="icon-btn" id="prev" aria-label="Día anterior">${ICON.left}</button>
      <h1>${esc(dayTitle(currentDate))}</h1>
      <button class="icon-btn" id="next" aria-label="Día siguiente" ${currentDate >= today ? 'disabled' : ''}>${ICON.right}</button>
    </div>

    <section class="card">
      <div class="kcal-line">
        <div><b class="num">${fmt(g.kcal)}</b><span>Meta</span></div>
        <div><b class="num">${fmt(t.kcal)}</b><span>Consumidas</span></div>
        <div><b class="num" style="color:${left < 0 ? 'var(--danger)' : 'var(--accent)'}">${fmt(Math.abs(left))}</b><span>${left < 0 ? 'Excedidas' : 'Restantes'}</span></div>
      </div>
      <div class="summary">
        <div class="ring ${left < 0 ? 'over' : ''}" role="img" aria-label="${fmt(t.kcal)} de ${fmt(g.kcal)} kilocalorías">
          <svg viewBox="0 0 132 132"><circle class="track" cx="66" cy="66" r="${R}" fill="none" stroke-width="12"/>
          <circle class="bar" cx="66" cy="66" r="${R}" fill="none" stroke-width="12" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}"/></svg>
          <div class="ring-label"><b class="num">${fmt(Math.abs(left))}</b><span>${left < 0 ? 'kcal de más' : 'kcal restantes'}</span></div>
        </div>
        <div>${macro('p', 'Proteína', 'var(--p)')}${macro('c', 'Carbohidratos', 'var(--c)')}${macro('f', 'Grasa', 'var(--f)')}</div>
      </div>
    </section>

    <section class="card">
      <div class="row between"><h2>Agua</h2><span class="sub small num">${fmt((d.water || 0) / 1000, 2)} / ${fmt(g.water / 1000, 1)} L</span></div>
      <div class="water" style="margin-top:10px">
        <div class="glasses" aria-hidden="true">${Array.from({ length: Math.max(glasses, full) }, (_, i) => `<span class="glass ${i < full ? 'full' : ''}"></span>`).join('')}</div>
        <button class="pill-btn" id="w-minus" aria-label="Quitar un vaso" ${d.water ? '' : 'disabled'}>−</button>
        <button class="pill-btn primary" id="w-plus">+ 250 ml</button>
      </div>
    </section>

    ${S.MEALS.map(([id, label]) => {
      const items = d.entries.filter((e) => e.meal === id);
      const mt = S.totals(items);
      const canCopy = !items.length && yesterday.entries.some((e) => e.meal === id);
      return `<section class="card">
        <div class="meal-head"><h2>${label}</h2><span class="kc num">${items.length ? fmt(mt.kcal) + ' kcal' : ''}</span></div>
        ${items.length ? `<ul class="items">${items.map((e) => {
          const s = S.scale(e.food, e.grams);
          return `<li data-entry="${e.id}"><div class="name"><b>${esc(e.food.name)}</b><span>${esc(qtyLabel(e.food, e.grams))}${e.food.brand ? ' · ' + esc(e.food.brand) : ''}</span></div><span class="k num">${fmt(s.kcal)}</span></li>`;
        }).join('')}</ul>` : ''}
        <div class="meal-actions">
          <button class="link-btn" data-add="${id}">+ Agregar</button>
          ${canCopy ? `<button class="link-btn" data-copy="${id}">Copiar de ayer</button>` : ''}
        </div>
      </section>`;
    }).join('')}
    ${!S.storageOk ? '<p class="warn">Este navegador no está guardando datos (modo privado o almacenamiento bloqueado). Lo que registres se perderá al cerrar.</p>' : ''}
  `;

  $('#prev').onclick = () => { currentDate = S.shiftDate(currentDate, -1); renderHoy(); };
  $('#next').onclick = () => { if (currentDate < today) { currentDate = S.shiftDate(currentDate, 1); renderHoy(); } };
  $('#w-plus').onclick = () => S.addWater(currentDate, 250);
  $('#w-minus').onclick = () => S.addWater(currentDate, -250);
  $$('[data-add]', view).forEach((b) => (b.onclick = () => openAdd({ meal: b.dataset.add })));
  $$('[data-copy]', view).forEach((b) => (b.onclick = () => {
    const n = S.copyMeal(S.shiftDate(currentDate, -1), currentDate, b.dataset.copy);
    toast(`${n} ${n === 1 ? 'alimento copiado' : 'alimentos copiados'}`);
  }));
  $$('[data-entry]', view).forEach((li) => (li.onclick = () => {
    const e = S.day(currentDate).entries.find((x) => x.id === li.dataset.entry);
    if (e) openPortion({ food: e.food, entry: e });
  }));
}

// =====================================================================================
// AGREGAR (buscador)
// =====================================================================================
const addDlg = $('#add');
let addState = null;

// pick: optional callback(food, grams) used by the recipe builder instead of logging a meal.
function openAdd({ meal = 'snacks', pick = null } = {}) {
  // Re-open so the sheet sits on top of any other open sheet (e.g. the recipe form).
  if (addDlg.open) addDlg.close();
  addState = { meal, pick, tab: 'buscar', q: '', seq: 0, remote: null, loading: false, error: null };
  addDlg.innerHTML = `
    <div class="sheet-head">
      <button class="icon-btn" data-close aria-label="Cerrar">${ICON.close}</button>
      <h2>${pick ? 'Agregar ingrediente' : 'Agregar a'}</h2>
      ${pick ? '' : `<select id="a-meal" aria-label="Comida" style="width:auto">${S.MEALS.map(([id, l]) => `<option value="${id}"${id === meal ? ' selected' : ''}>${l}</option>`).join('')}</select>`}
    </div>
    <div class="sheet-body">
      <div class="search">
        <input type="search" id="a-q" placeholder="Buscar alimento o producto" autocomplete="off" enterkeyhint="search">
        <button class="icon-btn" id="a-scan" aria-label="Escanear código de barras" style="width:44px;height:44px;border-radius:12px">${ICON.scan}</button>
      </div>
      <div class="seg" id="a-tabs">
        <button data-t="buscar" aria-pressed="true">Buscar</button>
        <button data-t="recientes">Recientes</button>
        <button data-t="favoritos">Favoritos</button>
        <button data-t="mios">Mis alimentos</button>
      </div>
      <div id="a-list"></div>
    </div>
    <div class="sheet-foot">
      <button class="btn" id="a-new">Crear alimento</button>
      ${pick ? '' : '<button class="btn" id="a-recipe">Crear receta</button>'}
    </div>`;
  addDlg.showModal();
  if (matchMedia('(pointer: fine)').matches) $('#a-q').focus();

  $('[data-close]', addDlg).onclick = () => addDlg.close();
  $('#a-meal')?.addEventListener('change', (e) => { addState.meal = e.target.value; });
  let deb;
  $('#a-q').addEventListener('input', (e) => {
    addState.q = e.target.value;
    addState.tab = 'buscar';
    syncTabs();
    renderList();
    clearTimeout(deb);
    deb = setTimeout(remoteSearch, 700);
  });
  $('#a-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(deb); remoteSearch(); e.target.blur(); } });
  $$('#a-tabs button').forEach((b) => (b.onclick = () => { addState.tab = b.dataset.t; syncTabs(); renderList(); }));
  $('#a-scan').onclick = scanFlow;
  $('#a-new').onclick = () => openFoodForm({ onSaved: (f) => openPortion({ food: f, meal: addState.meal, pick: addState.pick }) });
  $('#a-recipe')?.addEventListener('click', () => openRecipe());
  renderList();
}

function syncTabs() { $$('#a-tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.t === addState.tab))); }

function foodRow(f) {
  const sv = f.serving;
  const perServ = sv ? S.scale(f, sv.g).kcal : null;
  return `<li data-food="${esc(f.id)}"><div class="name"><b>${esc(f.name)}</b><span>${f.brand ? esc(f.brand) + ' · ' : ''}${sv ? esc(sv.label) + ' · ' : ''}${fmt(f.kcal)} kcal/100 g<span class="badge">${SRC[f.src] ?? ''}</span></span></div>
    <div class="k num"><b>${fmt(perServ ?? f.kcal)}</b>kcal</div></li>`;
}

function renderList() {
  const st = addState, el = $('#a-list');
  const pool = new Map();
  const list = (arr, label) => {
    arr.forEach((f) => pool.set(f.id, f));
    return (label ? `<p class="section-label">${label}</p>` : '') + `<ul class="results">${arr.map(foodRow).join('')}</ul>`;
  };
  const s = S.get();
  let html = '';
  if (st.tab === 'buscar') {
    const q = st.q.trim();
    if (!q) {
      html = s.recents.length ? list(s.recents.slice(0, 12), 'Recientes') : `<div class="empty">Busca un alimento ("pollo", "tortilla", "yogur") o escanea el código de barras de un producto.</div>`;
    } else {
      const qn = q.toLowerCase();
      const mine = s.custom.filter((f) => f.name.toLowerCase().includes(qn));
      const base = searchBase(q);
      if (mine.length) html += list(mine, 'Mis alimentos y recetas');
      if (base.length) html += list(base, 'Alimentos básicos');
      if (q.length >= 3) {
        if (st.loading) html += `<p class="section-label">Productos <span class="spinner"></span></p>`;
        else if (st.error) html += `<p class="section-label">Productos</p><div class="empty small">Open Food Facts no respondió (a veces se satura).<br><button class="pill-btn" id="a-retry" style="margin-top:8px">Reintentar</button></div>`;
        else if (st.remote && st.remoteQ === q) html += st.remote.length ? list(st.remote, 'Productos (Open Food Facts)') : `<p class="section-label">Productos</p><div class="empty small">Sin productos con ese nombre.</div>`;
      }
      if (!mine.length && !base.length && q.length < 3) html = `<div class="empty">Escribe al menos 3 letras para buscar productos.</div>`;
    }
  } else if (st.tab === 'recientes') {
    html = s.recents.length ? list(s.recents) : '<div class="empty">Aquí aparecen los alimentos que registres.</div>';
  } else if (st.tab === 'favoritos') {
    html = s.favorites.length ? list(s.favorites) : '<div class="empty">Marca alimentos con ★ al agregarlos para tenerlos a la mano.</div>';
  } else {
    html = s.custom.length ? list(s.custom) : '<div class="empty">Crea alimentos con tus propios datos o recetas con varios ingredientes.</div>';
  }
  el.innerHTML = html;
  $('#a-retry', el)?.addEventListener('click', remoteSearch);
  $$('[data-food]', el).forEach((li) => (li.onclick = () => {
    const f = pool.get(li.dataset.food);
    if (f) openPortion({ food: f, meal: st.meal, pick: st.pick });
  }));
}

async function remoteSearch() {
  const st = addState;
  if (!st) return;
  const q = st.q.trim();
  if (q.length < 3) return;
  const my = ++st.seq;
  st.loading = true; st.error = null; renderList();
  try {
    const r = await searchProducts(q);
    if (my !== st.seq) return;
    st.remote = r; st.remoteQ = q;
  } catch (e) {
    if (my !== st.seq) return;
    st.error = e.message;
  }
  st.loading = false;
  if (addDlg.open) renderList();
}

async function scanFlow() {
  const code = await scanBarcode();
  if (!code) return;
  toast('Buscando ' + code + '…');
  try {
    const known = [...S.get().custom, ...S.get().recents].find((f) => f.code === code);
    const food = known || (await byBarcode(code));
    if (food) { openPortion({ food, meal: addState.meal, pick: addState.pick }); return; }
    toast('Producto no encontrado: puedes crearlo con los datos de la etiqueta');
    openFoodForm({ code, onSaved: (f) => openPortion({ food: f, meal: addState.meal, pick: addState.pick }) });
  } catch {
    toast('No se pudo consultar el código. Revisa tu conexión.');
  }
}

// =====================================================================================
// PORCIÓN (agregar / editar)
// =====================================================================================
const porDlg = $('#portion');

function openPortion({ food, meal = 'snacks', entry = null, pick = null }) {
  const sv = food.serving && food.serving.g > 0 ? food.serving : null;
  let unit = entry ? (sv && Math.abs(entry.grams / sv.g - Math.round(entry.grams / sv.g * 4) / 4) < 0.01 ? 'sv' : 'g') : sv ? 'sv' : 'g';
  let amount = entry ? (unit === 'sv' ? entry.grams / sv.g : entry.grams) : unit === 'sv' ? 1 : 100;
  let selMeal = entry ? entry.meal : meal;

  const grams = () => (unit === 'sv' ? amount * sv.g : amount);
  const chips = () => (unit === 'sv' ? [0.5, 1, 1.5, 2] : [50, 100, 150, 200]);

  porDlg.innerHTML = `
    <div class="sheet-head">
      <h2 style="font-size:16px">${esc(food.name)}</h2>
      <button class="icon-btn" data-close aria-label="Cerrar">${ICON.close}</button>
    </div>
    <div class="sheet-body">
      <p class="note">${food.brand ? esc(food.brand) + ' · ' : ''}${fmt(food.kcal)} kcal · P ${fmt(food.p, 1)} · C ${fmt(food.c, 1)} · G ${fmt(food.f, 1)} por 100 g<span class="badge">${SRC[food.src] ?? ''}</span></p>
      <div class="grid2">
        <label class="field">Cantidad<input type="number" id="p-amt" inputmode="decimal" min="0" step="any"></label>
        <label class="field">Unidad<select id="p-unit">${sv ? `<option value="sv">${esc(sv.label)} (${fmt(sv.g)} g)</option>` : ''}<option value="g">gramos (o ml)</option></select></label>
      </div>
      <div class="chips" id="p-chips"></div>
      <div class="nutri" id="p-nutri"></div>
      ${pick ? '' : `<label class="field">Comida<select id="p-meal">${S.MEALS.map(([id, l]) => `<option value="${id}"${id === selMeal ? ' selected' : ''}>${l}</option>`).join('')}</select></label>`}
    </div>
    <div class="sheet-foot">
      ${pick ? '' : `<button class="star" id="p-fav" aria-label="Favorito" aria-pressed="${S.isFav(food)}">★</button>`}
      ${entry ? '<button class="btn danger" id="p-del">Eliminar</button>' : ''}
      <button class="btn primary" id="p-ok">${pick ? 'Agregar ingrediente' : entry ? 'Guardar' : 'Agregar'}</button>
    </div>`;
  porDlg.showModal();

  const amt = $('#p-amt'), unitSel = $('#p-unit');
  amt.value = +amount.toFixed(2);
  unitSel.value = unit;
  const update = () => {
    const gr = grams();
    const s = S.scale(food, gr);
    $('#p-nutri').innerHTML = `<div><b class="num">${fmt(s.kcal)}</b><span>kcal</span></div><div><b class="num" style="color:var(--p)">${fmt(s.p, 1)}</b><span>proteína</span></div><div><b class="num" style="color:var(--c)">${fmt(s.c, 1)}</b><span>carbos</span></div><div><b class="num" style="color:var(--f)">${fmt(s.f, 1)}</b><span>grasa</span></div>`;
    $('#p-chips').innerHTML = chips().map((c) => `<button class="chip" data-c="${c}" aria-pressed="${Math.abs(c - amount) < 1e-9}">${unit === 'sv' ? fmt(c, c % 1 ? 1 : 0) + ' porc.' : c + ' g'}</button>`).join('');
    $$('#p-chips .chip').forEach((b) => (b.onclick = () => { amount = +b.dataset.c; amt.value = amount; update(); }));
    $('#p-ok').disabled = !(gr > 0);
  };
  amt.addEventListener('input', () => { amount = Math.max(0, +amt.value || 0); update(); });
  unitSel.addEventListener('change', () => {
    const gr = grams();
    unit = unitSel.value;
    amount = unit === 'sv' ? +(gr / sv.g).toFixed(2) : Math.round(gr);
    amt.value = amount;
    update();
  });
  $('#p-meal')?.addEventListener('change', (e) => { selMeal = e.target.value; });
  $('[data-close]', porDlg).onclick = () => porDlg.close();
  $('#p-fav')?.addEventListener('click', (e) => { S.toggleFav(food); e.currentTarget.setAttribute('aria-pressed', String(S.isFav(food))); });
  $('#p-del')?.addEventListener('click', () => { S.removeEntry(currentDate, entry.id); porDlg.close(); toast('Eliminado'); });
  $('#p-ok').onclick = () => {
    const gr = Math.round(grams() * 10) / 10;
    if (!(gr > 0)) return;
    if (pick) { pick(food, gr); porDlg.close(); addDlg.close(); return; }
    if (entry) { S.updateEntry(currentDate, entry.id, { grams: gr, meal: selMeal }); toast('Guardado'); }
    else { S.addEntry(currentDate, selMeal, food, gr); toast(`Agregado a ${S.MEALS.find(([id]) => id === selMeal)[1].toLowerCase()} · ${fmt(S.scale(food, gr).kcal)} kcal`); }
    porDlg.close();
    if (addDlg.open && addState && !addState.pick) renderList();
  };
  update();
  if (matchMedia('(pointer: fine)').matches) amt.select();
}

// =====================================================================================
// CREAR ALIMENTO
// =====================================================================================
const formDlg = $('#form');

function openFoodForm({ code = null, onSaved } = {}) {
  formDlg.innerHTML = `
    <div class="sheet-head"><h2>Crear alimento</h2><button class="icon-btn" data-close aria-label="Cerrar">${ICON.close}</button></div>
    <form class="sheet-body" id="ff">
      <label class="field">Nombre<input type="text" name="name" required maxlength="80" placeholder="Ej. Barra de granola"></label>
      <label class="field">Marca (opcional)<input type="text" name="brand" maxlength="60"></label>
      <div class="seg" id="ff-basis"><button type="button" data-b="100" aria-pressed="true">Por 100 g</button><button type="button" data-b="sv">Por porción</button></div>
      <div class="grid2" id="ff-sv" hidden>
        <label class="field">Porción (texto)<input type="text" name="svlabel" placeholder="1 barra" maxlength="40"></label>
        <label class="field">Gramos por porción<input type="number" name="svg" inputmode="decimal" min="0" step="any"></label>
      </div>
      <div class="grid4">
        <label class="field">kcal<input type="number" name="kcal" inputmode="decimal" min="0" step="any" required></label>
        <label class="field">Proteína<input type="number" name="p" inputmode="decimal" min="0" step="any" value="0"></label>
        <label class="field">Carbos<input type="number" name="c" inputmode="decimal" min="0" step="any" value="0"></label>
        <label class="field">Grasa<input type="number" name="f" inputmode="decimal" min="0" step="any" value="0"></label>
      </div>
      <p class="note">Copia los datos de la tabla nutrimental del empaque. Proteína, carbohidratos y grasa en gramos.${code ? ` Se guardará con el código ${esc(code)} para encontrarlo al escanear.` : ''}</p>
      <button class="btn primary" type="submit">Guardar alimento</button>
    </form>`;
  formDlg.showModal();
  let basis = '100';
  $('[data-close]', formDlg).onclick = () => formDlg.close();
  $$('#ff-basis button').forEach((b) => (b.onclick = () => {
    basis = b.dataset.b;
    $$('#ff-basis button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    $('#ff-sv').hidden = basis !== 'sv';
    $('[name=svg]').required = basis === 'sv';
  }));
  $('#ff').onsubmit = (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    const k = basis === 'sv' ? 100 / (+fd.svg || 100) : 1;
    const svG = +fd.svg;
    const food = S.addCustom({
      name: fd.name.trim(), brand: fd.brand.trim(), code,
      kcal: +(+fd.kcal * k).toFixed(1), p: +(+fd.p * k).toFixed(2), c: +(+fd.c * k).toFixed(2), f: +(+fd.f * k).toFixed(2),
      serving: basis === 'sv' && svG > 0 ? { label: fd.svlabel.trim() || '1 porción', g: svG } : null,
    });
    formDlg.close();
    toast('Alimento guardado');
    onSaved?.(food);
  };
}

// =====================================================================================
// RECETA
// =====================================================================================
function openRecipe() {
  const items = []; // {food, grams}
  // When started from the add sheet, return there afterwards (the sheet is reused for picking).
  const returnMeal = addDlg.open && addState && !addState.pick ? addState.meal : null;
  if (addDlg.open) addDlg.close();
  const backToAdd = (tab) => {
    if (!returnMeal) return;
    openAdd({ meal: returnMeal });
    if (tab) { addState.tab = tab; syncTabs(); renderList(); }
  };
  formDlg.innerHTML = `
    <div class="sheet-head"><h2>Crear receta</h2><button class="icon-btn" data-close aria-label="Cerrar">${ICON.close}</button></div>
    <div class="sheet-body">
      <div class="grid2">
        <label class="field">Nombre<input type="text" id="r-name" maxlength="80" placeholder="Ej. Licuado de plátano"></label>
        <label class="field">Porciones que rinde<input type="number" id="r-serv" inputmode="numeric" min="1" step="1" value="1"></label>
      </div>
      <p class="section-label">Ingredientes</p>
      <ul class="results" id="r-items"></ul>
      <button class="pill-btn" id="r-add" style="justify-self:start">+ Agregar ingrediente</button>
      <div class="nutri" id="r-tot"></div>
      <button class="btn primary" id="r-save" disabled>Guardar receta</button>
    </div>`;
  formDlg.showModal();
  $('[data-close]', formDlg).onclick = () => { formDlg.close(); backToAdd(); };
  const draw = () => {
    const serv = Math.max(1, Math.round(+$('#r-serv').value || 1));
    const t = items.reduce((a, it) => { const s = S.scale(it.food, it.grams); a.kcal += s.kcal; a.p += s.p; a.c += s.c; a.f += s.f; a.g += it.grams; return a; }, { kcal: 0, p: 0, c: 0, f: 0, g: 0 });
    $('#r-items').innerHTML = items.length ? items.map((it, i) => `<li><div class="name"><b>${esc(it.food.name)}</b><span>${fmt(it.grams)} g · ${fmt(S.scale(it.food, it.grams).kcal)} kcal</span></div><button class="icon-btn" data-rm="${i}" aria-label="Quitar">${ICON.close}</button></li>`).join('') : '<li class="muted small" style="cursor:default">Todavía no hay ingredientes.</li>';
    $$('[data-rm]', formDlg).forEach((b) => (b.onclick = () => { items.splice(+b.dataset.rm, 1); draw(); }));
    $('#r-tot').innerHTML = `<div><b class="num">${fmt(t.kcal / serv)}</b><span>kcal/porción</span></div><div><b class="num" style="color:var(--p)">${fmt(t.p / serv, 1)}</b><span>proteína</span></div><div><b class="num" style="color:var(--c)">${fmt(t.c / serv, 1)}</b><span>carbos</span></div><div><b class="num" style="color:var(--f)">${fmt(t.f / serv, 1)}</b><span>grasa</span></div>`;
    $('#r-save').disabled = !(items.length && $('#r-name').value.trim());
    return { t, serv };
  };
  $('#r-name').addEventListener('input', draw);
  $('#r-serv').addEventListener('input', draw);
  $('#r-add').onclick = () => openAdd({ pick: (food, grams) => { items.push({ food, grams }); draw(); } });
  $('#r-save').onclick = () => {
    const { t, serv } = draw();
    if (!(t.g > 0)) return;
    const k = 100 / t.g;
    S.addCustom({
      src: 'receta', name: $('#r-name').value.trim(),
      kcal: +(t.kcal * k).toFixed(1), p: +(t.p * k).toFixed(2), c: +(t.c * k).toFixed(2), f: +(t.f * k).toFixed(2),
      serving: { label: '1 porción', g: +(t.g / serv).toFixed(1) },
    });
    formDlg.close();
    if (addDlg.open) addDlg.close();
    toast('Receta guardada en Mis alimentos');
    backToAdd('mios');
  };
  draw();
}

// =====================================================================================
// PROGRESO
// =====================================================================================
function barChart(days, goal) {
  const W = 340, H = 170, pl = 34, pb = 20, pt = 8;
  const max = Math.max(goal * 1.25, ...days.map((d) => d.kcal), 100);
  const bw = (W - pl) / days.length;
  const y = (v) => pt + (H - pt - pb) * (1 - v / max);
  const ticks = [0, Math.round(max / 2 / 100) * 100, Math.round(max / 100) * 100];
  const every = days.length > 10 ? 5 : 1;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Calorías por día">
    ${ticks.map((t) => `<line class="grid" x1="${pl}" x2="${W}" y1="${y(t)}" y2="${y(t)}"/><text x="${pl - 6}" y="${y(t) + 3}" text-anchor="end">${fmt(t)}</text>`).join('')}
    ${days.map((d, i) => {
      const x = pl + i * bw + bw * 0.18, w = bw * 0.64;
      const over = d.kcal > goal * 1.05;
      return `${d.kcal > 0 ? `<rect x="${x}" y="${y(d.kcal)}" width="${w}" height="${Math.max(0, H - pb - y(d.kcal))}" rx="${Math.min(4, w / 2)}" fill="${over ? 'var(--danger)' : 'var(--accent)'}"><title>${d.label}: ${fmt(d.kcal)} kcal</title></rect>` : ''}
        ${i % every === 0 || i === days.length - 1 ? `<text x="${x + w / 2}" y="${H - 5}" text-anchor="middle">${d.short}</text>` : ''}`;
    }).join('')}
    <line class="goal" x1="${pl}" x2="${W}" y1="${y(goal)}" y2="${y(goal)}"/>
    <text x="${W}" y="${y(goal) - 4}" text-anchor="end">meta ${fmt(goal)}</text>
  </svg>`;
}

function lineChart(points) {
  const W = 340, H = 150, pl = 34, pb = 20, pt = 10;
  const vals = points.map((p) => p.kg);
  const lo = Math.floor(Math.min(...vals) - 1), hi = Math.ceil(Math.max(...vals) + 1);
  const t0 = new Date(points[0].date).getTime(), t1 = new Date(points.at(-1).date).getTime();
  const x = (d) => pl + (W - pl - 8) * (t1 === t0 ? 0.5 : (new Date(d).getTime() - t0) / (t1 - t0));
  const y = (v) => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo || 1));
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.date).toFixed(1)},${y(p.kg).toFixed(1)}`).join('');
  const short = (d) => new Date(d + 'T12:00:00').toLocaleDateString('es-MX', { day: 'numeric', month: 'short' });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Peso en el tiempo">
    ${[lo, (lo + hi) / 2, hi].map((t) => `<line class="grid" x1="${pl}" x2="${W}" y1="${y(t)}" y2="${y(t)}"/><text x="${pl - 6}" y="${y(t) + 3}" text-anchor="end">${fmt(t, t % 1 ? 1 : 0)}</text>`).join('')}
    <path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${points.map((p) => `<circle cx="${x(p.date)}" cy="${y(p.kg)}" r="3.5" fill="var(--card)" stroke="var(--accent)" stroke-width="2"><title>${short(p.date)}: ${fmt(p.kg, 1)} kg</title></circle>`).join('')}
    <text x="${pl}" y="${H - 5}">${short(points[0].date)}</text><text x="${W}" y="${H - 5}" text-anchor="end">${short(points.at(-1).date)}</text>
  </svg>`;
}

function renderProgreso() {
  const g = S.goals();
  const today = S.dateKey();
  const days = [];
  for (let i = progressRange - 1; i >= 0; i--) {
    const key = S.shiftDate(today, -i);
    const t = S.totals(S.day(key).entries);
    const d = new Date(key + 'T12:00:00');
    days.push({ key, ...t, label: d.toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric' }), short: progressRange === 7 ? d.toLocaleDateString('es-MX', { weekday: 'narrow' }) : String(d.getDate()) });
  }
  const logged = days.filter((d) => d.kcal > 0);
  const avg = (k) => (logged.length ? logged.reduce((a, d) => a + d[k], 0) / logged.length : 0);
  const inRange = logged.filter((d) => Math.abs(d.kcal - g.kcal) <= g.kcal * 0.1).length;
  const s = S.get();
  const w = s.weights;
  const first = w[0], last = w.at(-1);
  const pk = avg('p') * 4, ck = avg('c') * 4, fk = avg('f') * 9, mk = pk + ck + fk || 1;

  view.innerHTML = `
    <div class="datebar"><h1>Progreso</h1>
      <div class="seg" id="g-range" style="width:auto"><button data-r="7" aria-pressed="${progressRange === 7}">7 días</button><button data-r="30" aria-pressed="${progressRange === 30}">30 días</button></div>
    </div>
    <section class="card stack">
      <h2>Calorías por día</h2>
      ${barChart(days, g.kcal)}
      <div class="stats3">
        <div><b class="num">${fmt(avg('kcal'))}</b><span>promedio kcal</span></div>
        <div><b class="num">${logged.length}/${progressRange}</b><span>días registrados</span></div>
        <div><b class="num">${inRange}</b><span>días en meta ±10%</span></div>
      </div>
    </section>
    <section class="card stack">
      <h2>Macros promedio</h2>
      ${logged.length ? `
      <div class="track" style="height:12px;display:flex"><i style="width:${(pk / mk) * 100}%;background:var(--p);border-radius:0"></i><i style="width:${(ck / mk) * 100}%;background:var(--c);border-radius:0"></i><i style="width:${(fk / mk) * 100}%;background:var(--f);border-radius:0"></i></div>
      <div class="stats3">
        <div><b class="num" style="color:var(--p)">${fmt(avg('p'))} g</b><span>proteína · meta ${fmt(g.p)}</span></div>
        <div><b class="num" style="color:var(--c)">${fmt(avg('c'))} g</b><span>carbos · meta ${fmt(g.c)}</span></div>
        <div><b class="num" style="color:var(--f)">${fmt(avg('f'))} g</b><span>grasa · meta ${fmt(g.f)}</span></div>
      </div>` : '<p class="empty small">Registra comidas para ver tus promedios.</p>'}
    </section>
    <section class="card stack">
      <div class="row between"><h2>Peso</h2>${first && last && w.length > 1 ? `<span class="small ${last.kg <= first.kg ? '' : ''} num">${last.kg - first.kg > 0 ? '+' : ''}${fmt(last.kg - first.kg, 1)} kg desde ${new Date(first.date + 'T12:00:00').toLocaleDateString('es-MX', { day: 'numeric', month: 'short' })}</span>` : ''}</div>
      ${w.length >= 2 ? lineChart(w.slice(-60)) : '<p class="note">Registra tu peso una vez por semana, a la misma hora, para ver la tendencia.</p>'}
      <form class="row" id="w-form">
        <input type="number" name="kg" inputmode="decimal" step="0.1" min="20" max="400" placeholder="kg" required style="flex:1" aria-label="Peso en kg">
        <input type="date" name="date" value="${today}" max="${today}" style="flex:1" aria-label="Fecha">
        <button class="pill-btn primary" style="height:44px">Guardar</button>
      </form>
      ${w.length ? `<ul class="weights">${w.slice().reverse().slice(0, 20).map((x) => `<li><span class="spacer">${new Date(x.date + 'T12:00:00').toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</span><b class="num">${fmt(x.kg, 1)} kg</b><button class="icon-btn" data-wdel="${x.date}" aria-label="Borrar registro" style="width:32px;height:32px">${ICON.close}</button></li>`).join('')}</ul>` : ''}
    </section>`;
  $$('#g-range button').forEach((b) => (b.onclick = () => { progressRange = +b.dataset.r; renderProgreso(); }));
  $('#w-form').onsubmit = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    document.activeElement?.blur();
    S.addWeight(fd.get('date') || today, +fd.get('kg'));
    toast('Peso guardado');
  };
  $$('[data-wdel]').forEach((b) => (b.onclick = () => S.removeWeight(b.dataset.wdel)));
}

// =====================================================================================
// PERFIL
// =====================================================================================
function renderPerfil() {
  const s = S.get();
  const p = s.profile ?? { sex: 'm', age: 30, height: 165, weight: 70, activity: 1.375, goal: -275 };
  const g = S.goals();
  let theme = 'auto';
  try { theme = localStorage.getItem('orbe.cal.theme') || 'auto'; } catch { /* storage blocked */ }

  view.innerHTML = `
    ${!s.profile ? `<section class="card stack"><h1 style="font-size:21px">Bienvenido a ORBE Calorías</h1>
      <p class="note">Con estos datos calculamos tus calorías y macros diarios. Todo se guarda solo en este teléfono: no hay cuentas ni servidores.</p></section>` : '<div class="datebar"><h1>Perfil</h1></div>'}
    <form class="card stack" id="pf">
      <h2>Tus datos</h2>
      <div class="seg" id="pf-sex"><button type="button" data-s="m" aria-pressed="${p.sex === 'm'}">Mujer</button><button type="button" data-s="h" aria-pressed="${p.sex === 'h'}">Hombre</button></div>
      <div class="grid2">
        <label class="field">Edad<input type="number" name="age" inputmode="numeric" min="14" max="100" required value="${p.age}"></label>
        <label class="field">Estatura (cm)<input type="number" name="height" inputmode="numeric" min="120" max="230" required value="${p.height}"></label>
        <label class="field">Peso (kg)<input type="number" name="weight" inputmode="decimal" step="0.1" min="30" max="300" required value="${p.weight}"></label>
        <label class="field">Objetivo<select name="goal">${S.GOALS.map(([v, l]) => `<option value="${v}"${v === p.goal ? ' selected' : ''}>${l}</option>`).join('')}</select></label>
      </div>
      <label class="field">Actividad<select name="activity">${S.ACTIVITY.map(([v, l, d]) => `<option value="${v}"${v === p.activity ? ' selected' : ''}>${l}: ${d}</option>`).join('')}</select></label>
      <button class="btn primary" type="submit">${s.profile ? 'Actualizar' : 'Calcular mi plan'}</button>
    </form>

    ${g ? `<section class="card stack">
      <div class="row between"><h2>Tu meta diaria</h2>${g.custom ? '<span class="badge">personalizada</span>' : ''}</div>
      <div class="goal-table">
        <div><b class="num">${fmt(g.kcal)}</b><span>kcal</span></div>
        <div><b class="num" style="color:var(--p)">${fmt(g.p)} g</b><span>proteína</span></div>
        <div><b class="num" style="color:var(--c)">${fmt(g.c)} g</b><span>carbos</span></div>
        <div><b class="num" style="color:var(--f)">${fmt(g.f)} g</b><span>grasa</span></div>
      </div>
      <p class="note">Metabolismo en reposo: ${fmt(g.bmr)} kcal. Gasto diario estimado con tu actividad: ${fmt(g.tdee)} kcal. Agua sugerida: ${fmt(g.water / 1000, 1)} L.</p>
      ${g.floored && !g.custom ? `<p class="warn">Tu meta quedó en el mínimo recomendado sin supervisión (${fmt(g.kcal)} kcal). Para bajar más rápido, consulta a un profesional de la salud.</p>` : ''}
      <details ${g.custom ? 'open' : ''}><summary class="small sub" style="cursor:pointer">Ajustar metas manualmente</summary>
        <form class="stack" id="cg" style="margin-top:10px">
          <div class="grid4">
            <label class="field">kcal<input type="number" name="kcal" inputmode="numeric" min="800" max="6000" value="${g.kcal}"></label>
            <label class="field">Prot.<input type="number" name="p" inputmode="numeric" min="0" value="${g.p}"></label>
            <label class="field">Carbos<input type="number" name="c" inputmode="numeric" min="0" value="${g.c}"></label>
            <label class="field">Grasa<input type="number" name="f" inputmode="numeric" min="0" value="${g.f}"></label>
          </div>
          <div class="row"><button class="pill-btn primary">Guardar metas</button>${g.custom ? '<button type="button" class="pill-btn" id="cg-reset">Volver a las calculadas</button>' : ''}</div>
        </form>
      </details>
    </section>

    <section class="card stack">
      <h2>Apariencia</h2>
      <div class="seg" id="th"><button data-t="auto" aria-pressed="${theme === 'auto'}">Automática</button><button data-t="light" aria-pressed="${theme === 'light'}">Clara</button><button data-t="dark" aria-pressed="${theme === 'dark'}">Oscura</button></div>
    </section>

    <section class="card stack">
      <h2>Tus datos</h2>
      <p class="note">Se guardan solo en este navegador. Descarga un respaldo de vez en cuando, sobre todo antes de cambiar de teléfono.</p>
      <div class="row" style="flex-wrap:wrap">
        <button class="pill-btn" id="exp">Descargar respaldo</button>
        <label class="pill-btn" style="cursor:pointer">Restaurar respaldo<input type="file" id="imp" accept="application/json,.json" hidden></label>
        <button class="pill-btn" id="wipe" style="color:var(--danger)">Borrar todo</button>
      </div>
    </section>` : ''}

    <p class="note center">Las calorías son estimaciones. Esta app no sustituye la orientación de un médico o nutriólogo.<br>Productos: Open Food Facts (licencia ODbL).</p>`;

  let sex = p.sex;
  $$('#pf-sex button').forEach((b) => (b.onclick = () => { sex = b.dataset.s; $$('#pf-sex button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }));
  $('#pf').onsubmit = (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    const first = !s.profile;
    S.setProfile({ sex, age: +fd.age, height: +fd.height, weight: +fd.weight, activity: +fd.activity, goal: +fd.goal });
    toast(first ? 'Listo: ya puedes registrar tus comidas' : 'Perfil actualizado');
    if (first) location.hash = '#hoy';
  };
  $('#cg')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target));
    S.setCustomGoals({ kcal: +fd.kcal, p: +fd.p, c: +fd.c, f: +fd.f });
    toast('Metas guardadas');
  });
  $('#cg-reset')?.addEventListener('click', () => S.setCustomGoals(null));
  $$('#th button').forEach((b) => (b.onclick = () => {
    try { localStorage.setItem('orbe.cal.theme', b.dataset.t); } catch { /* storage blocked */ }
    applyTheme(); renderPerfil();
  }));
  $('#exp')?.addEventListener('click', () => {
    const blob = new Blob([S.exportData()], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `orbe-calorias-${S.dateKey()}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $('#imp')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!confirm('¿Reemplazar los datos de este teléfono con el respaldo?')) return;
    try { S.importData(await file.text()); toast('Respaldo restaurado'); } catch (err) { toast(err.message); }
  });
  $('#wipe')?.addEventListener('click', () => {
    if (confirm('¿Borrar todo tu registro, perfil y alimentos guardados? No se puede deshacer.')) { S.resetAll(); toast('Datos borrados'); }
  });
}

// ---------- start ----------
route();
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
// If the app stays open past midnight while showing "today", move to the new day.
let lastToday = S.dateKey();
setInterval(() => {
  const t = S.dateKey();
  if (t !== lastToday) {
    if (currentDate === lastToday) currentDate = t;
    lastToday = t;
    if ((location.hash.slice(1) || 'hoy') === 'hoy') route();
  }
}, 60000);
