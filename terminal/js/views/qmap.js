// Gamma map: price with dealer levels, GEX/DEX/OI by strike, expiry × strike heatmap,
// delta-notional flow per minute and an unusual-flow tape.

import { UNDERLYINGS, getSim } from '../sim/options.js';
import { h, $, $$, esc, num, price, compact, signCls, makeChart, candleStyle, fitCanvas, status, tag, fmtTime } from '../util.js';

const COLORS = { call: '#22ab94', put: '#f23645', flip: '#e8a33d', spot: '#e9edf1', grid: '#161d25', text: '#a7b0bb', mute: '#6e7884' };
const UNUSUAL_MIN = 150_000;

export function mount(root) {
  let symbol = localStorage.getItem('orbe.qmap.symbol') || 'SPY';
  if (!UNDERLYINGS[symbol]) symbol = 'SPY';
  let filter = 'all';
  let metric = 'gex';
  let sim, offTick, offFlow, timer;
  let snap = null;

  root.append(h(`
    <div class="grid" style="gap:12px">
      <section class="panel">
        <div class="panel-head">
          <h2>Mapa de gamma</h2>${tag('sim')}
          <select id="q-sym" aria-label="Subyacente">${Object.keys(UNDERLYINGS).map((s) => `<option${s === symbol ? ' selected' : ''}>${s}</option>`).join('')}</select>
          <div class="seg" id="q-filter" role="group" aria-label="Vencimientos">
            <button data-f="all" aria-pressed="true">Todos</button>
            <button data-f="0dte">0DTE</button>
            <button data-f="weekly">Próx. 5</button>
            <button data-f="monthly">Mensuales</button>
          </div>
          <select id="q-exp" aria-label="Vencimiento específico"></select>
          <span class="spacer"></span>
          <span class="note">Exposición de los dealers por strike y vencimiento: dónde se concentra la gamma y qué niveles frenan o aceleran el precio.</span>
        </div>
        <div class="stats" id="q-stats" style="border:0;border-radius:0 0 10px 10px"></div>
      </section>

      <div class="grid g-qmap">
        <section class="panel">
          <div class="panel-head"><h2>Precio y niveles</h2><span class="spacer"></span>
            <div class="legend"><span><i style="background:${COLORS.call}"></i>Call wall</span><span><i style="background:${COLORS.put}"></i>Put wall</span><span><i style="background:${COLORS.flip}"></i>Gamma flip</span></div>
          </div>
          <div class="panel-body flush"><div class="chart tall" id="q-price"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Por strike</h2><span class="spacer"></span>
            <div class="seg" id="q-metric" role="group" aria-label="Métrica">
              <button data-m="gex" aria-pressed="true">GEX</button><button data-m="dex">DEX</button><button data-m="oi">OI</button><button data-m="vol">Volumen</button>
            </div>
          </div>
          <div class="panel-body flush" style="position:relative"><canvas class="fill" id="q-bars"></canvas><div class="tooltip" id="q-tip"></div></div>
        </section>
      </div>

      <section class="panel">
        <div class="panel-head"><h2>Gamma neta · vencimiento × strike</h2><span class="spacer"></span>
          <div class="legend"><span><i style="background:${COLORS.call}"></i>Gamma positiva (frena)</span><span><i style="background:${COLORS.put}"></i>Gamma negativa (acelera)</span></div>
        </div>
        <div class="panel-body flush" style="position:relative"><canvas class="fill" id="q-heat"></canvas><div class="tooltip" id="q-htip"></div></div>
      </section>

      <div class="grid g-side">
        <section class="panel">
          <div class="panel-head"><h2>Delta nocional por minuto</h2><span class="spacer"></span>
            <div class="legend"><span><i style="background:${COLORS.call}"></i>Compra neta de delta</span><span><i style="background:${COLORS.put}"></i>Venta neta</span><span><i style="background:#4c8dff"></i>Acumulado</span></div>
          </div>
          <div class="panel-body flush"><div class="chart short" id="q-flow"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Flujo inusual</h2><span class="note">prima ≥ $${compact(UNUSUAL_MIN, 0)}</span></div>
          <ul class="feed" id="q-tape"><li class="muted" style="display:block">Esperando operaciones…</li></ul>
        </section>
      </div>
    </div>`));

  // ---------- price chart ----------
  const chart = makeChart($('#q-price', root));
  const candles = chart.addCandlestickSeries(candleStyle);
  const lines = {};
  const setLine = (key, value, color, title) => {
    if (value == null) { if (lines[key]) { candles.removePriceLine(lines[key]); delete lines[key]; } return; }
    const opts = { price: value, color, lineWidth: 1, lineStyle: key === 'flip' ? 2 : 0, axisLabelVisible: true, title };
    if (lines[key]) lines[key].applyOptions(opts); else lines[key] = candles.createPriceLine(opts);
  };

  // ---------- flow chart ----------
  const flowChart = makeChart($('#q-flow', root), { leftPriceScale: { visible: true, borderColor: '#1f2731' } });
  const flowHist = flowChart.addHistogramSeries({ priceFormat: { type: 'custom', formatter: (v) => compact(v) } });
  const flowCum = flowChart.addLineSeries({ color: '#4c8dff', lineWidth: 2, priceScaleId: 'left', priceFormat: { type: 'custom', formatter: (v) => compact(v) } });

  const tape = $('#q-tape', root);
  let tapeEmpty = true;

  // ---------- strike bars (canvas) ----------
  const bars = $('#q-bars', root);
  const tip = $('#q-tip', root);
  let barRows = [];
  function drawBars() {
    if (!snap) return;
    const { ctx, w, h: H } = fitCanvas(bars, 470);
    ctx.clearRect(0, 0, w, H);
    const S = snap.spot;
    const near = snap.strikes.filter((p) => Math.abs(p.K - S) / S <= sim.cfg.width * 0.55);
    const maxRows = 64;
    let rows = near;
    if (near.length > maxRows) {
      const i0 = near.findIndex((p) => p.K >= S);
      const a = Math.max(0, Math.min(near.length - maxRows, i0 - maxRows / 2));
      rows = near.slice(a, a + maxRows);
    }
    rows = rows.slice().reverse(); // high strikes on top, like a price axis
    barRows = rows;
    const padL = 54, padR = 10, padT = 8, padB = 22;
    const rh = (H - padT - padB) / rows.length;
    const val = (p) => metric === 'gex' ? [p.callGex, p.putGex, p.net]
      : metric === 'dex' ? [Math.max(0, p.dex), Math.min(0, p.dex), p.dex]
      : metric === 'oi' ? [p.callOI, -p.putOI, p.callOI - p.putOI]
      : [p.vol, 0, p.vol];
    const maxV = Math.max(1, ...rows.map((p) => { const [a, b] = val(p); return Math.max(Math.abs(a), Math.abs(b)); }));
    const zero = padL + (w - padL - padR) / 2;
    const half = (w - padL - padR) / 2;
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = COLORS.grid; ctx.beginPath(); ctx.moveTo(zero, padT); ctx.lineTo(zero, H - padB); ctx.stroke();
    rows.forEach((p, i) => {
      const y = padT + i * rh;
      const [a, b, net] = val(p);
      const bh = Math.max(1, rh - 2);
      if (metric === 'vol') {
        ctx.fillStyle = '#4c8dff'; ctx.fillRect(zero, y + 1, (a / maxV) * half, bh);
      } else {
        ctx.globalAlpha = 0.35;
        ctx.fillStyle = COLORS.call; ctx.fillRect(zero, y + 1, (Math.max(0, a) / maxV) * half, bh);
        ctx.fillStyle = COLORS.put; ctx.fillRect(zero, y + 1, (Math.min(0, b) / maxV) * half, bh);
        ctx.globalAlpha = 1;
        ctx.fillStyle = net >= 0 ? COLORS.call : COLORS.put;
        ctx.fillRect(zero, y + 1 + bh * 0.25, (net / maxV) * half, Math.max(1, bh * 0.5));
      }
      const special = p.K === snap.callWall ? COLORS.call : p.K === snap.putWall ? COLORS.put : null;
      if (rows.length <= 40 || p.K % (sim.cfg.step * 5) === 0 || special) {
        ctx.fillStyle = special ?? COLORS.text;
        ctx.textAlign = 'right';
        ctx.fillText(num(p.K, p.K % 1 ? 1 : 0), padL - 8, y + rh / 2);
      }
    });
    const yOf = (k) => {
      const hiK = rows[0].K, loK = rows[rows.length - 1].K;
      return padT + ((hiK - k) / (hiK - loK || 1)) * (rows.length - 1) * rh + rh / 2;
    };
    const mark = (k, color, label, dash, below) => {
      if (k == null || k > rows[0].K || k < rows[rows.length - 1].K) return;
      const y = yOf(k);
      ctx.setLineDash(dash ? [4, 4] : []);
      ctx.strokeStyle = color; ctx.beginPath(); ctx.moveTo(padL - 4, y); ctx.lineTo(w - padR, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = color; ctx.textAlign = 'right'; ctx.fillText(label, w - padR, below ? y + 8 : y - 7);
    };
    mark(snap.flip, COLORS.flip, 'flip ' + price(snap.flip), true, snap.flip != null && snap.flip < S);
    mark(S, COLORS.spot, 'spot ' + price(S), false, snap.flip != null && snap.flip > S);
    ctx.fillStyle = COLORS.mute; ctx.textAlign = 'center';
    const unit = metric === 'gex' ? '$ por 1% de movimiento' : metric === 'dex' ? 'delta nocional ($)' : metric === 'oi' ? 'contratos (call ▸ · ◂ put)' : 'contratos operados hoy';
    ctx.fillText(unit, zero, H - 8);
  }
  bars.addEventListener('mousemove', (ev) => {
    if (!barRows.length) return;
    const r = bars.getBoundingClientRect();
    const rh = (r.height - 30) / barRows.length;
    const i = Math.floor((ev.clientY - r.top - 8) / rh);
    const p = barRows[i];
    if (!p) { tip.style.display = 'none'; return; }
    tip.innerHTML = `Strike <b>${num(p.K, p.K % 1 ? 1 : 0)}</b><br>GEX call <span class="up">${compact(p.callGex)}</span> · put <span class="down">${compact(p.putGex)}</span><br>GEX neta <span class="${signCls(p.net)}">${compact(p.net)}</span><br>DEX ${compact(p.dex)} · OI ${compact(p.callOI, 0)}C / ${compact(p.putOI, 0)}P<br>Vol. hoy ${compact(p.vol, 0)}`;
    tip.style.display = 'block';
    tip.style.left = Math.min(ev.clientX - r.left + 14, r.width - 230) + 'px';
    tip.style.top = (ev.clientY - r.top + 10) + 'px';
  });
  bars.addEventListener('mouseleave', () => { tip.style.display = 'none'; });

  // ---------- heatmap (canvas) ----------
  const heat = $('#q-heat', root);
  const htip = $('#q-htip', root);
  let heatGeom = null;
  function drawHeat() {
    if (!snap) return;
    const S = snap.spot;
    const cols = sim.strikes.map((K, i) => [K, i]).filter(([K]) => Math.abs(K - S) / S <= sim.cfg.width * 0.4);
    let picked = cols;
    const maxCols = 42;
    if (cols.length > maxCols) {
      const stride = Math.ceil(cols.length / maxCols);
      picked = cols.filter((_, i) => i % stride === 0);
    }
    const rowsN = sim.expiries.length;
    const { ctx, w, h: H } = fitCanvas(heat, 40 + rowsN * 26);
    ctx.clearRect(0, 0, w, H);
    const padL = 116, padT = 6, padB = 26;
    const cw = (w - padL - 8) / picked.length;
    const ch = (H - padT - padB) / rowsN;
    let maxV = 1;
    snap.heat.forEach((row) => picked.forEach(([, si]) => { maxV = Math.max(maxV, Math.abs(row[si])); }));
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textBaseline = 'middle';
    sim.expiries.forEach((e, ei) => {
      const y = padT + ei * ch;
      ctx.fillStyle = COLORS.text; ctx.textAlign = 'left';
      ctx.fillText(`${e.key.slice(5)} ${e.kind}`, 6, y + ch / 2);
      picked.forEach(([K, si], ci) => {
        const v = snap.heat[ei][si];
        const a = Math.min(1, Math.sqrt(Math.abs(v) / maxV));
        ctx.fillStyle = v >= 0 ? `rgba(34,171,148,${0.08 + a * 0.85})` : `rgba(242,54,69,${0.08 + a * 0.85})`;
        ctx.fillRect(padL + ci * cw + 1, y + 1, cw - 2, ch - 2);
        if (cw > 34 && a > 0.45) {
          ctx.fillStyle = '#e9edf1'; ctx.textAlign = 'center';
          ctx.fillText(compact(v, 0), padL + ci * cw + cw / 2, y + ch / 2);
        }
      });
    });
    ctx.fillStyle = COLORS.mute; ctx.textAlign = 'center';
    const every = Math.max(1, Math.ceil(46 / cw));
    picked.forEach(([K], ci) => { if (ci % every === 0) ctx.fillText(num(K, K % 1 ? 1 : 0), padL + ci * cw + cw / 2, H - 12); });
    // spot marker
    const si = picked.findIndex(([K]) => K >= S);
    if (si > 0) {
      const [k0] = picked[si - 1], [k1] = picked[si];
      const x = padL + (si - 1) * cw + cw / 2 + ((S - k0) / (k1 - k0)) * cw;
      ctx.strokeStyle = '#e9edf1'; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, H - padB + 4); ctx.stroke(); ctx.setLineDash([]);
    }
    heatGeom = { padL, padT, cw, ch, picked };
  }
  heat.addEventListener('mousemove', (ev) => {
    if (!heatGeom || !snap) return;
    const r = heat.getBoundingClientRect();
    const ci = Math.floor((ev.clientX - r.left - heatGeom.padL) / heatGeom.cw);
    const ei = Math.floor((ev.clientY - r.top - heatGeom.padT) / heatGeom.ch);
    const col = heatGeom.picked[ci], e = sim.expiries[ei];
    if (!col || !e) { htip.style.display = 'none'; return; }
    const v = snap.heat[ei][col[1]];
    htip.innerHTML = `${e.key} (${e.kind}) · strike ${num(col[0], col[0] % 1 ? 1 : 0)}<br>Gamma neta <span class="${signCls(v)}">${compact(v)}</span>`;
    htip.style.display = 'block';
    htip.style.left = Math.min(ev.clientX - r.left + 14, r.width - 220) + 'px';
    htip.style.top = (ev.clientY - r.top + 10) + 'px';
  });
  heat.addEventListener('mouseleave', () => { htip.style.display = 'none'; });

  // ---------- stats ----------
  const statsEl = $('#q-stats', root);
  function drawStats() {
    if (!snap) return;
    const first = sim.candles[Math.max(0, sim.candles.length - 390)].open;
    const chg = (snap.spot / first - 1) * 100;
    const pos = snap.total >= 0;
    const distFlip = snap.flip ? (snap.spot / snap.flip - 1) * 100 : null;
    const items = [
      ['Spot', price(snap.spot), `<span class="${signCls(chg)}">${chg > 0 ? '+' : ''}${num(chg)}% sesión</span>`],
      ['GEX neta', `<span class="${signCls(snap.total)}">${compact(snap.total)}</span>`, '$ por 1% de movimiento'],
      ['Régimen', `<span class="${pos ? 'up' : 'down'}">${pos ? 'Gamma +' : 'Gamma −'}</span>`, pos ? 'Dealers frenan: rango, reversión' : 'Dealers aceleran: tendencia, volatilidad'],
      ['Gamma flip', `<span class="c-flip">${snap.flip ? price(snap.flip) : 'fuera de rango'}</span>`, distFlip == null ? '' : `spot ${distFlip > 0 ? '+' : ''}${num(distFlip)}% vs flip`],
      ['Call wall', `<span class="c-call">${num(snap.callWall, 0)}</span>`, 'resistencia por gamma'],
      ['Put wall', `<span class="c-put">${num(snap.putWall, 0)}</span>`, 'soporte por gamma'],
      ['DEX', `<span class="${signCls(snap.dexTotal)}">${compact(snap.dexTotal)}</span>`, 'delta nocional del OI'],
      ['Put/Call OI', num(snap.pcr), snap.pcr > 1.2 ? 'cobertura elevada' : snap.pcr < 0.8 ? 'sesgo alcista' : 'neutral'],
    ];
    statsEl.innerHTML = items.map(([k, v, s]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
  }

  // ---------- wiring ----------
  function refresh() {
    snap = sim.snapshot(filter);
    setLine('call', snap.callWall, COLORS.call, 'Call wall');
    setLine('put', snap.putWall, COLORS.put, 'Put wall');
    setLine('flip', snap.flip, COLORS.flip, 'Flip');
    drawStats(); drawBars(); drawHeat();
    const flow = sim.flowSeries();
    let cum = 0;
    flowHist.setData(flow.map((f) => ({ time: f.time, value: f.deltaNotional, color: f.deltaNotional >= 0 ? 'rgba(34,171,148,.8)' : 'rgba(242,54,69,.8)' })));
    flowCum.setData(flow.map((f) => ({ time: f.time, value: (cum += f.deltaNotional) })));
  }

  function fillExpirySelect() {
    const sel = $('#q-exp', root);
    sel.innerHTML = `<option value="">Vencimiento…</option>` + sim.expiries.map((e) => `<option value="${e.key}">${e.key} · ${e.kind}</option>`).join('');
  }

  function attach(sym) {
    offTick?.(); offFlow?.();
    sim = getSim(sym);
    candles.setData(sim.candles);
    chart.timeScale().scrollToRealTime();
    fillExpirySelect();
    offTick = sim.onTick((bar) => candles.update(bar));
    const addTrade = (t, fresh) => {
      if (t.premium < UNUSUAL_MIN) return;
      if (tapeEmpty) { tape.innerHTML = ''; tapeEmpty = false; }
      const li = document.createElement('li');
      if (fresh) li.className = 'new' + (t.side === 'venta' ? ' sell' : '');
      li.innerHTML = `<span class="muted">${fmtTime(t.ts)}</span><span><b class="${t.type === 'C' ? 'up' : 'down'}">${esc(sym)} ${num(t.K, t.K % 1 ? 1 : 0)}${t.type}</b> ${t.expiry.slice(5)} · ${t.side} ${num(t.size, 0)} @ ${num(t.price)}</span><span class="${t.side === 'compra' ? 'up' : 'down'}">$${compact(t.premium)}</span>`;
      if (fresh) tape.prepend(li); else tape.append(li);
      while (tape.children.length > 80) tape.lastChild.remove();
    };
    sim.big.forEach((t) => addTrade(t, false));
    offFlow = sim.onFlow((t) => addTrade(t, true));
    refresh();
    status.set('opt', `Opciones ${sym}: simulador (Black-Scholes, OI sintético)`, 'sim', 'Conecta un proveedor de opciones para datos reales');
  }

  $('#q-sym', root).addEventListener('change', (e) => {
    symbol = e.target.value;
    localStorage.setItem('orbe.qmap.symbol', symbol);
    tape.innerHTML = '<li class="muted" style="display:block">Esperando operaciones…</li>'; tapeEmpty = true;
    attach(symbol);
  });
  const setFilter = (f) => {
    filter = f;
    $$('#q-filter button', root).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.f === f)));
    if (!['all', '0dte', 'weekly', 'monthly'].includes(f)) $('#q-exp', root).value = f; else $('#q-exp', root).value = '';
    refresh();
  };
  $$('#q-filter button', root).forEach((b) => b.addEventListener('click', () => setFilter(b.dataset.f)));
  $('#q-exp', root).addEventListener('change', (e) => setFilter(e.target.value || 'all'));
  $$('#q-metric button', root).forEach((b) => b.addEventListener('click', () => {
    metric = b.dataset.m;
    $$('#q-metric button', root).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    drawBars();
  }));

  attach(symbol);
  timer = setInterval(refresh, 1000);
  const onResize = () => { drawBars(); drawHeat(); };
  window.addEventListener('resize', onResize);

  return () => {
    clearInterval(timer);
    offTick?.(); offFlow?.();
    window.removeEventListener('resize', onResize);
    chart.remove(); flowChart.remove();
    status.clear(['opt']);
  };
}
