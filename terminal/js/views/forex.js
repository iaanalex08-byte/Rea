// Forex: currency strength, cross-rate change matrix and pair history from ECB reference
// rates (Frankfurter API, published once per business day around 16:00 CET).

import { h, $, $$, esc, num, pct, signCls, makeChart, getJSON, status, tag, fmtDate } from '../util.js';

const CCY = ['USD', 'EUR', 'JPY', 'GBP', 'CHF', 'CAD', 'AUD', 'NZD', 'MXN', 'CNY'];
const NAMES = { USD: 'Dólar EE. UU.', EUR: 'Euro', JPY: 'Yen', GBP: 'Libra', CHF: 'Franco suizo', CAD: 'Dólar canadiense', AUD: 'Dólar australiano', NZD: 'Dólar neozelandés', MXN: 'Peso mexicano', CNY: 'Yuan' };
const PERIODS = { '1D': 1, '1S': 5, '1M': 21, '3M': 63, '1A': 250 };

export async function mount(root) {
  let period = '1S';
  let base = 'USD', quote = 'MXN';

  root.append(h(`
    <div class="grid" style="gap:12px">
      <section class="panel">
        <div class="panel-head"><h2>Fuerza relativa de divisas</h2><span id="fx-tag">${tag('wait')}</span><span class="spacer"></span>
          <div class="seg" id="fx-period">${Object.keys(PERIODS).map((k) => `<button data-p="${k}" aria-pressed="${k === period}">${k}</button>`).join('')}</div>
        </div>
        <div class="panel-body"><div class="bars" id="fx-strength"></div>
          <p class="note" style="margin-top:12px" id="fx-note">Cada divisa contra el promedio de las demás. Tipos de referencia del Banco Central Europeo (diarios, no intradía).</p></div>
      </section>
      <div class="grid g-side">
        <section class="panel">
          <div class="panel-head"><h2 id="fx-pair-title">USD/MXN</h2><span class="spacer"></span>
            <select id="fx-base" aria-label="Divisa base">${CCY.map((c) => `<option${c === base ? ' selected' : ''}>${c}</option>`).join('')}</select>
            <span class="muted">/</span>
            <select id="fx-quote" aria-label="Divisa cotizada">${CCY.map((c) => `<option${c === quote ? ' selected' : ''}>${c}</option>`).join('')}</select>
          </div>
          <div class="panel-body flush"><div class="chart" id="fx-chart"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Cotizaciones</h2></div>
          <div class="table-wrap"><table><thead><tr><th>Divisa</th><th class="num">Por 1 USD</th><th class="num" id="fx-chg-h">Cambio</th></tr></thead><tbody id="fx-table"></tbody></table></div>
        </section>
      </div>
      <section class="panel">
        <div class="panel-head"><h2>Matriz de cruces</h2><span class="note">Variación de la fila contra la columna en el periodo elegido. Clic en una celda para graficar el par.</span></div>
        <div class="table-wrap" style="max-height:none"><table id="fx-matrix"></table></div>
      </section>
    </div>`));

  const chart = makeChart($('#fx-chart', root), { timeScale: { timeVisible: false } });
  const line = chart.addAreaSeries({ lineColor: '#0bc4a5', topColor: 'rgba(11,196,165,.25)', bottomColor: 'rgba(11,196,165,0)', lineWidth: 2, priceFormat: { type: 'price', precision: 4, minMove: 0.0001 } });

  let dates = [], rates = {};
  try {
    const start = new Date(Date.now() - 400 * 864e5).toISOString().slice(0, 10);
    const d = await getJSON(`https://api.frankfurter.dev/v1/${start}..?from=USD&to=${CCY.filter((c) => c !== 'USD').join(',')}`);
    rates = d.rates;
    dates = Object.keys(rates).sort();
    for (const k of dates) rates[k].USD = 1;
    $('#fx-tag', root).innerHTML = tag('daily');
    status.set('fx', `Forex: BCE vía Frankfurter (último ${fmtDate(dates.at(-1))})`, 'daily');
  } catch (e) {
    $('#fx-tag', root).innerHTML = tag('err');
    $('#fx-strength', root).innerHTML = `<div class="empty"><h3>No se pudieron cargar los tipos de cambio</h3>${esc(e.message)}</div>`;
    status.set('fx', 'Forex: Frankfurter', 'err', e.message);
    return () => { chart.remove(); status.clear(['fx']); };
  }

  // Value of 1 unit of currency c in USD on date index i.
  const usdValue = (c, i) => 1 / rates[dates[i]][c];
  const ret = (c, i0, i1) => usdValue(c, i1) / usdValue(c, i0) - 1;
  const cross = (a, b, i0, i1) => ((1 + ret(a, i0, i1)) / (1 + ret(b, i0, i1)) - 1) * 100;

  function render() {
    const i1 = dates.length - 1;
    const i0 = Math.max(0, i1 - PERIODS[period]);
    const strength = CCY.map((c) => [c, CCY.filter((o) => o !== c).reduce((a, o) => a + cross(c, o, i0, i1), 0) / (CCY.length - 1)]).sort((a, b) => b[1] - a[1]);
    const max = Math.max(0.01, ...strength.map(([, v]) => Math.abs(v)));
    $('#fx-strength', root).innerHTML = strength.map(([c, v]) => {
      const w = (Math.abs(v) / max) * 50;
      return `<div class="bar-row" title="${esc(NAMES[c])}"><span><b>${c}</b></span><div class="track"><div class="fill" style="${v >= 0 ? `left:50%` : `left:${50 - w}%`};width:${w}%;background:${v >= 0 ? 'var(--up)' : 'var(--down)'}"></div><div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--line-2)"></div></div><span class="val ${signCls(v)}">${pct(v)}</span></div>`;
    }).join('');
    $('#fx-note', root).textContent = `Cada divisa contra el promedio de las demás, del ${fmtDate(dates[i0])} al ${fmtDate(dates[i1])}. Tipos de referencia del Banco Central Europeo (diarios, no intradía).`;

    $('#fx-chg-h', root).textContent = 'Cambio ' + period;
    $('#fx-table', root).innerHTML = CCY.filter((c) => c !== 'USD').map((c) => {
      const chg = (rates[dates[i1]][c] / rates[dates[i0]][c] - 1) * 100;
      return `<tr><td><b>${c}</b> <span class="muted">${esc(NAMES[c])}</span></td><td class="num">${num(rates[dates[i1]][c], 4)}</td><td class="num ${signCls(-chg)}" title="Subida = el dólar se fortalece">${pct(chg)}</td></tr>`;
    }).join('');

    const head = `<thead><tr><th></th>${CCY.map((c) => `<th class="num">${c}</th>`).join('')}</tr></thead>`;
    const body = CCY.map((a) => `<tr><td><b>${a}</b></td>${CCY.map((b) => {
      if (a === b) return '<td class="num muted">—</td>';
      const v = cross(a, b, i0, i1);
      const alpha = Math.min(0.85, Math.abs(v) / (max * 2.2) + 0.06);
      const bg = v >= 0 ? `rgba(34,171,148,${alpha})` : `rgba(242,54,69,${alpha})`;
      return `<td class="num" style="background:${bg};cursor:pointer" data-a="${a}" data-b="${b}">${num(v)}</td>`;
    }).join('')}</tr>`).join('');
    $('#fx-matrix', root).innerHTML = head + `<tbody>${body}</tbody>`;
  }

  function drawPair() {
    $('#fx-pair-title', root).textContent = `${base}/${quote}`;
    if (base === quote) { line.setData([]); return; }
    line.setData(dates.map((d) => ({ time: d, value: rates[d][quote] / rates[d][base] })));
    chart.timeScale().fitContent();
  }

  $$('#fx-period button', root).forEach((b) => b.addEventListener('click', () => {
    period = b.dataset.p;
    $$('#fx-period button', root).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    render();
  }));
  $('#fx-base', root).addEventListener('change', (e) => { base = e.target.value; drawPair(); });
  $('#fx-quote', root).addEventListener('change', (e) => { quote = e.target.value; drawPair(); });
  $('#fx-matrix', root).addEventListener('click', (e) => {
    const td = e.target.closest('td[data-a]');
    if (!td) return;
    base = td.dataset.a; quote = td.dataset.b;
    $('#fx-base', root).value = base; $('#fx-quote', root).value = quote;
    drawPair();
    $('#fx-chart', root).scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  render();
  drawPair();
  return () => { chart.remove(); status.clear(['fx']); };
}
