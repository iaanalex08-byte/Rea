// Insiders (SEC Form 4 open-market buys/sells) and congressional trades. Data is produced by
// the scheduled GitHub Action (terminal/tools/fetch-insiders.mjs) into terminal/data/.

import { h, $, $$, esc, num, compact, getJSON, status, tag, fmtDate } from '../util.js';

const MIN_VALUES = [0, 50_000, 250_000, 1_000_000];

export async function mount(root) {
  let side = 'all', minValue = 50_000, query = '';

  root.append(h(`
    <div class="grid" style="gap:12px">
      <section class="panel">
        <div class="panel-head"><h2>Insiders · compras y ventas en mercado abierto</h2><span id="i-tag">${tag('wait')}</span><span class="spacer"></span><span class="note" id="i-upd"></span></div>
        <div class="stats" id="i-stats" style="border-width:0 0 1px;border-radius:0"></div>
        <div class="panel-head" style="border-bottom:1px solid var(--line)">
          <div class="seg" id="i-side"><button data-s="all" aria-pressed="true">Todo</button><button data-s="P">Compras</button><button data-s="S">Ventas</button></div>
          <select id="i-min" aria-label="Valor mínimo">${MIN_VALUES.map((v) => `<option value="${v}"${v === minValue ? ' selected' : ''}>${v ? '≥ $' + compact(v, 0) : 'Cualquier monto'}</option>`).join('')}</select>
          <input id="i-q" type="search" placeholder="Buscar ticker, empresa o persona" aria-label="Buscar" style="background:var(--panel-2);border:1px solid var(--line-2);border-radius:7px;color:var(--ink);padding:5px 9px;font:inherit;font-size:12px;min-width:0;flex:0 1 260px">
        </div>
        <div class="table-wrap" id="i-table"></div>
      </section>
      <div class="grid g-side">
        <section class="panel">
          <div class="panel-head"><h2>Congreso de EE. UU.</h2><span id="g-tag">${tag('wait')}</span><span class="spacer"></span><span class="note" id="g-upd"></span></div>
          <div class="table-wrap" id="g-table"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Compras en grupo</h2></div>
          <div class="panel-body"><p class="note" style="margin-bottom:10px">Empresas donde dos o más insiders distintos compraron en los últimos 30 días: la señal de insiders más seguida.</p><div id="i-cluster"></div></div>
        </section>
      </div>
    </div>`));

  // ---------- insiders ----------
  let ins = { rows: [] };
  try {
    ins = await getJSON('data/insiders.json');
  } catch (e) { console.warn(e); }
  const rows = ins.rows ?? [];

  function renderInsiders() {
    const q = query.trim().toLowerCase();
    const list = rows.filter((r) => (side === 'all' || r.code === side) && (r.value ?? 0) >= minValue
      && (!q || [r.ticker, r.company, r.insider].some((x) => (x || '').toLowerCase().includes(q))))
      .sort((a, b) => (b.date || '').localeCompare(a.date || '') || (b.value ?? 0) - (a.value ?? 0));
    if (!rows.length) {
      $('#i-table', root).innerHTML = `<div class="empty"><h3>Todavía no hay datos de insiders</h3>
        Los descarga la GitHub Action <code>Datos de la terminal</code> desde la SEC. Para activarla, en tu repositorio ve a
        <b>Settings → Secrets and variables → Actions → Variables</b> y crea <code>SEC_USER_AGENT</code> con un nombre y tu correo,<br>
        por ejemplo <code>ORBE Terminal tu-correo@dominio.com</code> (la SEC lo exige para identificar a quien descarga). Luego ejecútala desde la pestaña Actions.</div>`;
      return;
    }
    if (!list.length) { $('#i-table', root).innerHTML = '<div class="empty">Ninguna operación con esos filtros.</div>'; return; }
    $('#i-table', root).innerHTML = `<table><thead><tr><th>Fecha</th><th>Ticker</th><th>Empresa</th><th>Insider</th><th>Cargo</th><th>Tipo</th><th class="num">Acciones</th><th class="num">Precio</th><th class="num">Valor</th><th class="num">Tenencia después</th><th></th></tr></thead><tbody>${
      list.slice(0, 400).map((r) => `<tr>
        <td>${r.date ? fmtDate(r.date) : '—'}</td><td><b>${esc(r.ticker || '—')}</b></td>
        <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis" title="${esc(r.company)}">${esc(r.company)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis" title="${esc(r.insider)}">${esc(r.insider)}</td>
        <td class="muted" style="max-width:180px;overflow:hidden;text-overflow:ellipsis" title="${esc(r.roles)}">${esc(r.roles)}</td>
        <td class="${r.code === 'P' ? 'up' : 'down'}">${r.code === 'P' ? 'Compra' : 'Venta'}</td>
        <td class="num">${num(r.shares, 0)}</td><td class="num">${r.price != null ? '$' + num(r.price) : '—'}</td>
        <td class="num ${r.code === 'P' ? 'up' : 'down'}">${r.value != null ? '$' + compact(r.value) : '—'}</td>
        <td class="num">${num(r.after, 0)}</td>
        <td><a href="${esc(r.url)}" target="_blank" rel="noopener">SEC ↗</a></td></tr>`).join('')}</tbody></table>`;
  }

  function renderStats() {
    const cutoff = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
    const recent = rows.filter((r) => (r.date || '') >= cutoff);
    const buys = recent.filter((r) => r.code === 'P'), sells = recent.filter((r) => r.code === 'S');
    const bv = buys.reduce((a, r) => a + (r.value ?? 0), 0), sv = sells.reduce((a, r) => a + (r.value ?? 0), 0);
    $('#i-stats', root).innerHTML = [
      ['Compras · 30 d', `<span class="up">$${compact(bv)}</span>`, `${num(buys.length, 0)} ${buys.length === 1 ? 'operación' : 'operaciones'}`],
      ['Ventas · 30 d', `<span class="down">$${compact(sv)}</span>`, `${num(sells.length, 0)} ${sells.length === 1 ? 'operación' : 'operaciones'}`],
      ['Compras / ventas', bv + sv ? num(bv / Math.max(1, sv), 2) : '—', 'por monto'],
      ['Empresas', num(new Set(recent.map((r) => r.ticker)).size, 0), 'con actividad'],
    ].map(([k, v, s]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');

    const byT = new Map();
    for (const r of buys) {
      const t = byT.get(r.ticker) ?? { ticker: r.ticker, company: r.company, people: new Set(), value: 0, last: '' };
      t.people.add(r.insider); t.value += r.value ?? 0; if ((r.date || '') > t.last) t.last = r.date;
      byT.set(r.ticker, t);
    }
    const clusters = [...byT.values()].filter((t) => t.people.size >= 2).sort((a, b) => b.people.size - a.people.size || b.value - a.value);
    $('#i-cluster', root).innerHTML = clusters.length
      ? `<table><thead><tr><th>Ticker</th><th class="num">Insiders</th><th class="num">Monto</th><th>Última</th></tr></thead><tbody>${clusters.slice(0, 15).map((t) =>
        `<tr data-symbol="${esc(t.ticker)}"><td><b>${esc(t.ticker)}</b> <span class="muted">${esc((t.company || '').slice(0, 22))}</span></td><td class="num">${t.people.size}</td><td class="num up">$${compact(t.value)}</td><td>${fmtDate(t.last)}</td></tr>`).join('')}</tbody></table>`
      : `<div class="empty" style="padding:12px">${rows.length ? 'Sin compras en grupo en los últimos 30 días.' : 'Aparecerán cuando haya datos de insiders.'}</div>`;
  }

  $('#i-cluster', root).addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-symbol]');
    if (!tr) return;
    query = tr.dataset.symbol; $('#i-q', root).value = query; side = 'P';
    $$('#i-side button', root).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.s === 'P')));
    renderInsiders();
  });
  $$('#i-side button', root).forEach((b) => b.addEventListener('click', () => {
    side = b.dataset.s; $$('#i-side button', root).forEach((x) => x.setAttribute('aria-pressed', String(x === b))); renderInsiders();
  }));
  $('#i-min', root).addEventListener('change', (e) => { minValue = +e.target.value; renderInsiders(); });
  $('#i-q', root).addEventListener('input', (e) => { query = e.target.value; renderInsiders(); });

  if (rows.length) {
    $('#i-tag', root).innerHTML = tag('daily');
    $('#i-upd', root).textContent = 'Actualizado ' + new Date(ins.updated).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
    status.set('ins', 'Insiders: SEC EDGAR Form 4 (cada 30 min en horario de mercado)', 'daily');
  } else {
    $('#i-tag', root).innerHTML = tag('off');
    status.set('ins', 'Insiders: falta configurar SEC_USER_AGENT', 'off');
  }
  renderStats();
  renderInsiders();

  // ---------- congress ----------
  let cg = { configured: false, rows: [] };
  try { cg = await getJSON('data/congress.json'); } catch (e) { console.warn(e); }
  if (!cg.configured) {
    $('#g-tag', root).innerHTML = tag('off');
    $('#g-table', root).innerHTML = `<div class="empty"><h3>Requiere un proveedor de datos</h3>
      Ya no hay una fuente gratuita y estable de las declaraciones del Congreso. La terminal está lista para
      <b>Quiver Quantitative</b>: crea el secreto <code>QUIVER_API_KEY</code> en <b>Settings → Secrets and variables → Actions → Secrets</b>
      y la próxima ejecución de la Action llenará esta tabla.</div>`;
    status.set('cg', 'Congreso: falta QUIVER_API_KEY', 'off');
  } else {
    $('#g-tag', root).innerHTML = tag('daily');
    $('#g-upd', root).textContent = 'Actualizado ' + new Date(cg.updated).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
    const list = cg.rows.slice().sort((a, b) => (b.reported || '').localeCompare(a.reported || ''));
    $('#g-table', root).innerHTML = `<table><thead><tr><th>Declarado</th><th>Operado</th><th>Legislador</th><th>Cámara</th><th>Ticker</th><th>Tipo</th><th>Rango</th></tr></thead><tbody>${
      list.slice(0, 300).map((r) => {
        const buy = /purchase|buy/i.test(r.type || '');
        return `<tr><td>${r.reported ? fmtDate(r.reported) : '—'}</td><td>${r.traded ? fmtDate(r.traded) : '—'}</td><td><b>${esc(r.member)}</b> <span class="muted">${esc(r.party || '')}</span></td><td>${esc(r.chamber === 'Senate' ? 'Senado' : r.chamber === 'Representatives' ? 'Cámara' : r.chamber || '')}</td><td><b>${esc(r.ticker)}</b></td><td class="${buy ? 'up' : 'down'}">${buy ? 'Compra' : 'Venta'}</td><td class="muted">${esc(r.range || '')}</td></tr>`;
      }).join('')}</tbody></table>`;
    status.set('cg', 'Congreso: Quiver Quantitative', 'daily');
  }

  return () => status.clear(['ins', 'cg']);
}
