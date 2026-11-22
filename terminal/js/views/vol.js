// Volatility: implied-volatility surface, skew by expiry and term structure (simulated chain).

import { UNDERLYINGS } from '../sim/options.js';
import { getEngine, sourceLabel } from '../options/engine.js';
import { h, $, num, signCls, status, tag } from '../util.js';
import { loadPlotly, AXIS, LAYOUT, CONFIG } from '../plotly.js';

export async function mount(root) {
  let symbol = localStorage.getItem('orbe.qmap.symbol') || 'SPY';
  if (!UNDERLYINGS[symbol]) symbol = 'SPY';

  root.append(h(`
    <div class="grid" style="gap:12px">
      <section class="panel">
        <div class="panel-head"><h2>Volatilidad implícita</h2><span id="v-tag">${tag('wait')}</span>
          <select id="v-sym" aria-label="Subyacente">${Object.keys(UNDERLYINGS).map((s) => `<option${s === symbol ? ' selected' : ''}>${s}</option>`).join('')}</select>
          <span class="spacer"></span><span class="note">Skew, estructura temporal y volatilidad por strike. La IV sube cuando el subyacente cae.</span>
        </div>
        <div class="stats" id="v-stats" style="border:0;border-radius:0 0 10px 10px"></div>
      </section>
      <div class="grid g-2">
        <section class="panel span-2">
          <div class="panel-head"><h2>Superficie de IV</h2><span class="note">Arrastra para rotar</span></div>
          <div class="panel-body flush"><div id="v-surface" style="height:520px"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Skew por vencimiento</h2></div>
          <div class="panel-body flush"><div id="v-skew" style="height:320px"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Estructura temporal (ATM)</h2></div>
          <div class="panel-body flush"><div id="v-term" style="height:320px"></div></div>
        </section>
      </div>
    </div>`));

  let Plotly;
  try { Plotly = await loadPlotly(); } catch (e) {
    $('#v-surface', root).innerHTML = `<div class="empty"><h3>${e.message}</h3>Revisa tu conexión y vuelve a abrir la pestaña.</div>`;
    return () => {};
  }
  let sim = null, timer, first = true, closed = false, seq = 0;

  function data() {
    const S = sim.spot;
    const now = Date.now();
    const exps = sim.expiries.map((e) => ({ e, T: sim.T(e, now), dte: Math.max(0, (e.ts - now) / 864e5) }));
    const ms = [];
    for (let m = -12; m <= 12; m += 1) ms.push(m);
    const z = exps.map(({ T }) => ms.map((m) => sim.iv(S * (1 + m / 100), T) * 100));
    return { S, exps, ms, z };
  }

  function draw() {
    if (!sim || !sim.expiries.length) return;
    const { S, exps, ms, z } = data();
    const dteLabels = exps.map((x) => num(x.dte, x.dte < 2 ? 1 : 0));
    Plotly.react($('#v-surface', root), [{
      type: 'surface', x: ms, y: exps.map((x) => x.dte), z,
      colorscale: [[0, '#0b3b4a'], [0.35, '#089981'], [0.65, '#e8a33d'], [1, '#f23645']],
      showscale: false, contours: { z: { show: true, usecolormap: true, project: { z: false }, width: 1 } },
      hovertemplate: 'Moneyness %{x}%<br>DTE %{y:.1f}<br>IV %{z:.1f}%<extra></extra>',
    }], {
      ...LAYOUT, margin: { l: 0, r: 0, t: 0, b: 0 },
      scene: {
        xaxis: { ...AXIS, title: 'Strike vs spot (%)', backgroundcolor: 'rgba(0,0,0,0)' },
        yaxis: { ...AXIS, title: 'Días al vencimiento', backgroundcolor: 'rgba(0,0,0,0)' },
        zaxis: { ...AXIS, title: 'IV (%)', backgroundcolor: 'rgba(0,0,0,0)' },
        camera: first ? { eye: { x: -1.5, y: -1.7, z: 0.65 } } : undefined,
        aspectmode: 'manual', aspectratio: { x: 1.4, y: 1.2, z: 0.6 },
      },
      uirevision: symbol,
    }, CONFIG);

    const pick = [0, Math.min(4, exps.length - 1), exps.length - 1].filter((v, i, a) => a.indexOf(v) === i);
    const colors = ['#0bc4a5', '#e8a33d', '#9b7dff'];
    Plotly.react($('#v-skew', root), pick.map((i, k) => ({
      type: 'scatter', mode: 'lines', name: `${exps[i].e.key} (${dteLabels[i]} d)`,
      x: ms.map((m) => S * (1 + m / 100)), y: z[i], line: { color: colors[k], width: 2 },
      hovertemplate: 'Strike %{x:.0f}<br>IV %{y:.1f}%<extra></extra>',
    })), {
      ...LAYOUT, uirevision: symbol,
      xaxis: { ...AXIS, title: 'Strike' }, yaxis: { ...AXIS, title: 'IV (%)' },
      shapes: [{ type: 'line', x0: S, x1: S, yref: 'paper', y0: 0, y1: 1, line: { color: '#e9edf1', dash: 'dot', width: 1 } }],
    }, CONFIG);

    const atm = exps.map(({ T }) => sim.iv(S, T) * 100);
    Plotly.react($('#v-term', root), [{
      type: 'scatter', mode: 'lines+markers', x: exps.map((x) => x.dte), y: atm, text: exps.map((x) => x.e.key),
      line: { color: '#0bc4a5', width: 2 }, marker: { size: 6 },
      hovertemplate: '%{text}<br>DTE %{x:.1f}<br>IV ATM %{y:.2f}%<extra></extra>',
    }], { ...LAYOUT, uirevision: symbol, showlegend: false, xaxis: { ...AXIS, title: 'Días al vencimiento' }, yaxis: { ...AXIS, title: 'IV ATM (%)' } }, CONFIG);
    first = false;

    // Stats: 30-day ATM IV, 25-delta-style skew proxy (−5% vs +5% moneyness), term slope.
    const T30 = 30 / 365, T7 = 7 / 365, T90 = 90 / 365;
    const iv30 = sim.iv(S, T30) * 100;
    const skew = (sim.iv(S * 0.95, T30) - sim.iv(S * 1.05, T30)) * 100;
    const slope = (sim.iv(S, T90) - sim.iv(S, T7)) * 100;
    const move1d = S * (iv30 / 100) / Math.sqrt(252);
    const items = [
      ['IV ATM 30 d', num(iv30) + '%', 'índice tipo VIX'],
      ['Movimiento esperado 1 d', '±' + num(move1d), `±${num((iv30 / Math.sqrt(252)), 2)}%`],
      ['Skew 30 d', num(skew) + ' pts', 'IV put −5% menos call +5%'],
      ['Pendiente 7→90 d', `<span class="${signCls(slope)}">${slope > 0 ? '+' : ''}${num(slope)} pts</span>`, slope >= 0 ? 'Contango: calma' : 'Backwardation: estrés'],
      ['IV 0DTE', num(sim.iv(S, exps[0].T) * 100) + '%', exps[0].e.key],
    ];
    $('#v-stats', root).innerHTML = items.map(([k, v, s]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
  }

  async function use(sym) {
    const my = ++seq;
    $('#v-tag', root).innerHTML = tag('wait');
    const engine = await getEngine(sym);
    if (my !== seq || closed) return;
    sim = engine; first = true;
    const [label, kind] = sourceLabel(sim, sym);
    $('#v-tag', root).innerHTML = tag(kind === 'err' ? 'sim' : kind);
    status.set('vol', label.replace(/^Opciones/, 'Volatilidad'), kind);
    clearInterval(timer);
    draw();
    timer = setInterval(draw, sim.source === 'real' ? 20000 : 4000);
  }
  $('#v-sym', root).addEventListener('change', (e) => {
    symbol = e.target.value; localStorage.setItem('orbe.qmap.symbol', symbol);
    use(symbol);
  });

  await use(symbol);
  return () => {
    closed = true;
    clearInterval(timer);
    ['#v-surface', '#v-skew', '#v-term'].forEach((s) => { const el = $(s, root); if (el) Plotly.purge(el); });
    status.clear(['vol']);
  };
}
