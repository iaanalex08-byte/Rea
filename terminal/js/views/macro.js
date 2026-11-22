// Macro: US Treasury par yield curve (daily, home.treasury.gov) with 2s10s / 3m10y spreads,
// and G20 indicators from the World Bank API (annual).

import { h, $, esc, num, signCls, makeChart, getJSON, status, tag, fmtDate } from '../util.js';
import { loadPlotly, AXIS, LAYOUT, CONFIG } from '../plotly.js';

const TENORS = ['1 Mo', '2 Mo', '3 Mo', '4 Mo', '6 Mo', '1 Yr', '2 Yr', '3 Yr', '5 Yr', '7 Yr', '10 Yr', '20 Yr', '30 Yr'];
const TENOR_LABEL = { '1 Mo': '1M', '2 Mo': '2M', '3 Mo': '3M', '4 Mo': '4M', '6 Mo': '6M', '1 Yr': '1A', '2 Yr': '2A', '3 Yr': '3A', '5 Yr': '5A', '7 Yr': '7A', '10 Yr': '10A', '20 Yr': '20A', '30 Yr': '30A' };
const G20 = { ARG: 'Argentina', AUS: 'Australia', BRA: 'Brasil', CAN: 'Canadá', CHN: 'China', FRA: 'Francia', DEU: 'Alemania', IND: 'India', IDN: 'Indonesia', ITA: 'Italia', JPN: 'Japón', KOR: 'Corea del Sur', MEX: 'México', RUS: 'Rusia', SAU: 'Arabia Saudita', ZAF: 'Sudáfrica', TUR: 'Turquía', GBR: 'Reino Unido', USA: 'Estados Unidos' };
const INDICATORS = [
  ['NY.GDP.MKTP.KD.ZG', 'PIB real', '%'],
  ['FP.CPI.TOTL.ZG', 'Inflación', '%'],
  ['SL.UEM.TOTL.ZS', 'Desempleo', '%'],
  ['BN.CAB.XOKA.GD.ZS', 'Cuenta corriente / PIB', '%'],
];

function parseTreasuryCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const head = lines[0].split(',').map((s) => s.replace(/"/g, ''));
  return lines.slice(1).map((l) => {
    const c = l.split(',');
    const [m, d, y] = c[0].split('/');
    const row = { date: `${y}-${m}-${d}` };
    head.forEach((k, i) => { if (i && c[i] !== '' && c[i] != null) row[k] = +c[i]; });
    return row;
  });
}

async function treasury(year) {
  const url = `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/${year}/all?type=daily_treasury_yield_curve&field_tdr_date_value=${year}&page&_format=csv`;
  return parseTreasuryCsv(await getJSON(url, { text: true, timeout: 20000 }));
}

export async function mount(root) {
  root.append(h(`
    <div class="grid" style="gap:12px">
      <section class="panel">
        <div class="panel-head"><h2>Curva del Tesoro de EE. UU.</h2><span id="t-tag">${tag('wait')}</span><span class="spacer"></span><span class="note" id="t-date"></span></div>
        <div class="stats" id="t-stats" style="border:0;border-radius:0"></div>
      </section>
      <div class="grid g-2">
        <section class="panel">
          <div class="panel-head"><h2>Curva: hoy vs. antes</h2></div>
          <div class="panel-body flush"><div id="t-curve" style="height:340px"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Diferenciales</h2><span class="spacer"></span>
            <div class="legend"><span><i style="background:#0bc4a5"></i>10A − 2A</span><span><i style="background:#e8a33d"></i>10A − 3M</span></div>
          </div>
          <div class="panel-body flush"><div class="chart" id="t-spread" style="height:340px"></div></div>
        </section>
      </div>
      <section class="panel">
        <div class="panel-head"><h2>Ciclo económico · G20</h2><span id="w-tag">${tag('wait')}</span><span class="spacer"></span><span class="note">Último dato anual disponible por país (Banco Mundial). Clic en un encabezado para ordenar.</span></div>
        <div class="table-wrap" style="max-height:none"><table id="w-table"><tbody><tr><td><div class="empty">Cargando indicadores…</div></td></tr></tbody></table></div>
      </section>
    </div>`));

  const spreadChart = makeChart($('#t-spread', root), { timeScale: { timeVisible: false } });
  const s2 = spreadChart.addLineSeries({ color: '#0bc4a5', lineWidth: 2, priceFormat: { type: 'custom', formatter: (v) => num(v, 2) + ' pp' } });
  const s3 = spreadChart.addLineSeries({ color: '#e8a33d', lineWidth: 2, priceFormat: { type: 'custom', formatter: (v) => num(v, 2) + ' pp' } });
  s2.createPriceLine({ price: 0, color: '#6e7884', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
  let Plotly = null;

  // ---------- Treasury ----------
  const loadTreasury = (async () => {
    try {
      const y = new Date().getUTCFullYear();
      const [cur, prev, prev2] = await Promise.all([treasury(y), treasury(y - 1), treasury(y - 2).catch(() => [])]);
      const rows = [...cur, ...prev, ...prev2].filter((r) => r['10 Yr'] != null).sort((a, b) => a.date.localeCompare(b.date));
      if (!rows.length) throw new Error('Sin datos');
      const last = rows.at(-1);
      const back = (days) => {
        const t = new Date(last.date).getTime() - days * 864e5;
        for (let i = rows.length - 1; i >= 0; i--) if (new Date(rows[i].date).getTime() <= t) return rows[i];
        return rows[0];
      };
      const w1 = back(7), m1 = back(30), y1 = back(365);
      const sp = (r) => r['10 Yr'] - r['2 Yr'];
      const sp3 = (r) => r['10 Yr'] - r['3 Mo'];
      const curSp = sp(last), curSp3 = sp3(last);
      const regime = curSp < -0.1 ? ['Invertida', 'down', 'Históricamente antecede recesiones'] : curSp < 0.25 ? ['Plana', 'warn', 'Transición de ciclo'] : ['Normal', 'up', 'Expansión o recorte de tasas descontado'];
      const dir = sp(last) - sp(m1) > 0.05 ? 'empinándose' : sp(last) - sp(m1) < -0.05 ? 'aplanándose' : 'estable';
      $('#t-stats', root).innerHTML = [
        ['3 meses', num(last['3 Mo']) + '%', `${(last['3 Mo'] - m1['3 Mo'] >= 0 ? '+' : '')}${num((last['3 Mo'] - m1['3 Mo']) * 100, 0)} pb en 1 mes`],
        ['2 años', num(last['2 Yr']) + '%', `${(last['2 Yr'] - m1['2 Yr'] >= 0 ? '+' : '')}${num((last['2 Yr'] - m1['2 Yr']) * 100, 0)} pb en 1 mes`],
        ['10 años', num(last['10 Yr']) + '%', `${(last['10 Yr'] - m1['10 Yr'] >= 0 ? '+' : '')}${num((last['10 Yr'] - m1['10 Yr']) * 100, 0)} pb en 1 mes`],
        ['30 años', num(last['30 Yr']) + '%', ''],
        ['10A − 2A', `<span class="${signCls(curSp)}">${num(curSp * 100, 0)} pb</span>`, dir],
        ['10A − 3M', `<span class="${signCls(curSp3)}">${num(curSp3 * 100, 0)} pb</span>`, ''],
        ['Régimen', `<span class="${regime[1]}">${regime[0]}</span>`, regime[2]],
      ].map(([k, v, s]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
      $('#t-date', root).textContent = 'Último cierre: ' + fmtDate(last.date);
      $('#t-tag', root).innerHTML = tag('daily');
      status.set('ust', `Tesoro EE. UU.: home.treasury.gov (${fmtDate(last.date)})`, 'daily');

      s2.setData(rows.map((r) => ({ time: r.date, value: +(sp(r) * 1).toFixed(3) })));
      s3.setData(rows.filter((r) => r['3 Mo'] != null).map((r) => ({ time: r.date, value: +sp3(r).toFixed(3) })));
      spreadChart.timeScale().fitContent();

      Plotly = await loadPlotly();
      const trace = (r, name, color, dash) => ({
        type: 'scatter', mode: 'lines+markers', name: `${name} · ${fmtDate(r.date)}`,
        x: TENORS.map((t) => TENOR_LABEL[t]), y: TENORS.map((t) => r[t] ?? null), connectgaps: true,
        line: { color, width: dash ? 1.5 : 2.5, dash: dash ? 'dot' : 'solid' }, marker: { size: dash ? 4 : 6 },
        hovertemplate: '%{x}: %{y:.2f}%<extra>' + name + '</extra>',
      });
      Plotly.react($('#t-curve', root), [trace(y1, 'Hace 1 año', '#6e7884', true), trace(m1, 'Hace 1 mes', '#9b7dff', true), trace(w1, 'Hace 1 semana', '#4c8dff', true), trace(last, 'Hoy', '#0bc4a5', false)],
        { ...LAYOUT, margin: { l: 44, r: 12, t: 8, b: 64 }, xaxis: { ...AXIS, type: 'category', title: 'Plazo' }, yaxis: { ...AXIS, title: 'Rendimiento (%)', ticksuffix: '%' } }, CONFIG);
    } catch (e) {
      $('#t-tag', root).innerHTML = tag('err');
      $('#t-stats', root).innerHTML = `<div class="stat"><div class="k">Error</div><div class="s">No se pudo leer la curva del Tesoro: ${esc(e.message)}</div></div>`;
      status.set('ust', 'Tesoro EE. UU.', 'err', e.message);
    }
  })();

  // ---------- World Bank ----------
  let sortKey = 'NY.GDP.MKTP.KD.ZG', sortDir = -1, table = [];
  function renderTable() {
    const sorted = table.slice().sort((a, b) => {
      if (sortKey === 'name') return a.name.localeCompare(b.name) * sortDir;
      const va = a[sortKey]?.v, vb = b[sortKey]?.v;
      if (va == null) return 1; if (vb == null) return -1;
      return (va - vb) * sortDir;
    });
    const head = `<thead><tr><th data-k="name" style="cursor:pointer">País</th>${INDICATORS.map(([id, name]) => `<th class="num" data-k="${id}" style="cursor:pointer">${name}${sortKey === id ? (sortDir < 0 ? ' ↓' : ' ↑') : ''}</th>`).join('')}<th>Fase</th></tr></thead>`;
    const body = sorted.map((r) => {
      const g = r['NY.GDP.MKTP.KD.ZG']?.v, inf = r['FP.CPI.TOTL.ZG']?.v;
      let phase = '—', cls = 'muted';
      if (g != null && inf != null) {
        if (g >= 2 && inf <= 4) [phase, cls] = ['Expansión', 'up'];
        else if (g >= 2) [phase, cls] = ['Sobrecalentamiento', 'warn'];
        else if (g < 0.5 && inf > 4) [phase, cls] = ['Estanflación', 'down'];
        else if (g < 0.5) [phase, cls] = ['Contracción', 'down'];
        else [phase, cls] = ['Desaceleración', 'warn'];
      }
      return `<tr><td><b>${esc(r.name)}</b></td>${INDICATORS.map(([id]) => {
        const c = r[id];
        if (!c) return '<td class="num muted">—</td>';
        const color = id === 'NY.GDP.MKTP.KD.ZG' ? signCls(c.v) : id === 'FP.CPI.TOTL.ZG' ? (c.v > 6 ? 'down' : c.v > 3.5 ? 'warn' : '') : '';
        return `<td class="num ${color}" title="Dato de ${c.y}">${num(c.v, 1)}<span class="muted" style="font-size:10px"> ${c.y}</span></td>`;
      }).join('')}<td class="${cls}">${phase}</td></tr>`;
    }).join('');
    $('#w-table', root).innerHTML = head + `<tbody>${body}</tbody>`;
  }
  $('#w-table', root).addEventListener('click', (e) => {
    const th = e.target.closest('th[data-k]');
    if (!th) return;
    if (sortKey === th.dataset.k) sortDir *= -1; else { sortKey = th.dataset.k; sortDir = th.dataset.k === 'name' ? 1 : -1; }
    renderTable();
  });
  const loadWB = (async () => {
    try {
      const countries = Object.keys(G20).join(';');
      const results = await Promise.all(INDICATORS.map(([id]) => getJSON(`https://api.worldbank.org/v2/country/${countries}/indicator/${id}?format=json&mrnev=1&per_page=100`, { timeout: 20000 })));
      const byC = Object.fromEntries(Object.entries(G20).map(([iso, name]) => [iso, { iso, name }]));
      results.forEach((res, i) => {
        for (const x of res[1] ?? []) if (x.value != null && byC[x.countryiso3code]) byC[x.countryiso3code][INDICATORS[i][0]] = { v: x.value, y: x.date };
      });
      table = Object.values(byC);
      renderTable();
      $('#w-tag', root).innerHTML = tag('annual');
      status.set('wb', 'G20: Banco Mundial (anual)', 'annual');
    } catch (e) {
      $('#w-tag', root).innerHTML = tag('err');
      $('#w-table', root).innerHTML = `<tbody><tr><td><div class="empty"><h3>No respondió el Banco Mundial</h3>${esc(e.message)}</div></td></tr></tbody>`;
      status.set('wb', 'G20: Banco Mundial', 'err', e.message);
    }
  })();

  await Promise.allSettled([loadTreasury, loadWB]);
  return () => {
    spreadChart.remove();
    const el = $('#t-curve', root); if (el && Plotly) Plotly.purge(el);
    status.clear(['ust', 'wb']);
  };
}
