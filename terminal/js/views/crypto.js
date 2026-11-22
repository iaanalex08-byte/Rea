// Live crypto: watchlist + candles over WebSocket, futures liquidations, market dominance.
// Providers are tried in order until one answers (some regions block binance.com).

import { h, $, $$, esc, num, price, pct, compact, signCls, makeChart, candleStyle, getJSON, status, tag, fmtTime } from '../util.js';

const COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'BNB', 'DOGE', 'ADA', 'AVAX', 'LINK', 'LTC', 'DOT', 'TRX'];
const INTERVALS = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600 };

// ---------- providers ----------
const binanceLike = (name, rest, ws) => ({
  name,
  pair: (c) => c + 'USDT',
  async tickers(coins) {
    const syms = encodeURIComponent(JSON.stringify(coins.map((c) => c + 'USDT')));
    const d = await getJSON(`${rest}/api/v3/ticker/24hr?symbols=${syms}`, { timeout: 8000 });
    return d.map((t) => ({ coin: t.symbol.replace(/USDT$/, ''), last: +t.lastPrice, open: +t.openPrice, high: +t.highPrice, low: +t.lowPrice, quoteVol: +t.quoteVolume }));
  },
  async klines(coin, iv) {
    const d = await getJSON(`${rest}/api/v3/klines?symbol=${coin}USDT&interval=${iv}&limit=500`, { timeout: 8000 });
    return d.map((k) => ({ time: k[0] / 1000, open: +k[1], high: +k[2], low: +k[3], close: +k[4], volume: +k[5] }));
  },
  connect(coins, iv, chartCoin, on) {
    const streams = coins.map((c) => c.toLowerCase() + 'usdt@miniTicker');
    streams.push(chartCoin.toLowerCase() + 'usdt@kline_' + iv);
    const sock = new WebSocket(`${ws}/stream?streams=${streams.join('/')}`);
    sock.onmessage = (m) => {
      const { data: d } = JSON.parse(m.data);
      if (d.e === '24hrMiniTicker') on.ticker({ coin: d.s.replace(/USDT$/, ''), last: +d.c, open: +d.o, high: +d.h, low: +d.l, quoteVol: +d.q });
      else if (d.e === 'kline') on.kline({ time: d.k.t / 1000, open: +d.k.o, high: +d.k.h, low: +d.k.l, close: +d.k.c, volume: +d.k.v });
    };
    return sock;
  },
});

const coinbase = {
  name: 'Coinbase',
  pair: (c) => c + '-USD',
  async tickers(coins) {
    const out = await Promise.all(coins.map(async (c) => {
      try {
        const s = await getJSON(`https://api.exchange.coinbase.com/products/${c}-USD/stats`, { timeout: 8000 });
        return { coin: c, last: +s.last, open: +s.open, high: +s.high, low: +s.low, quoteVol: +s.volume * +s.last };
      } catch { return null; }
    }));
    return out.filter(Boolean);
  },
  async klines(coin, iv) {
    const d = await getJSON(`https://api.exchange.coinbase.com/products/${coin}-USD/candles?granularity=${INTERVALS[iv]}`, { timeout: 8000 });
    return d.map((k) => ({ time: k[0], low: k[1], high: k[2], open: k[3], close: k[4], volume: k[5] })).reverse();
  },
  connect(coins, iv, chartCoin, on) {
    const sock = new WebSocket('wss://ws-feed.exchange.coinbase.com');
    const step = INTERVALS[iv];
    let bar = null;
    sock.onopen = () => sock.send(JSON.stringify({ type: 'subscribe', product_ids: coins.map((c) => c + '-USD'), channels: ['ticker'] }));
    sock.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (d.type !== 'ticker') return;
      const coin = d.product_id.replace(/-USD$/, '');
      const px = +d.price;
      on.ticker({ coin, last: px, open: +d.open_24h, high: +d.high_24h, low: +d.low_24h, quoteVol: +d.volume_24h * px });
      if (coin === chartCoin) {
        const t = Math.floor(new Date(d.time).getTime() / 1000 / step) * step;
        if (!bar || bar.time !== t) bar = { time: t, open: px, high: px, low: px, close: px, volume: 0 };
        bar.high = Math.max(bar.high, px); bar.low = Math.min(bar.low, px); bar.close = px; bar.volume += +d.last_size || 0;
        on.kline({ ...bar });
      }
    };
    return sock;
  },
};

const PROVIDERS = [
  binanceLike('Binance', 'https://data-api.binance.vision', 'wss://data-stream.binance.vision'),
  binanceLike('Binance.US', 'https://api.binance.us', 'wss://stream.binance.us:443'),
  coinbase,
];

// ---------- liquidations (Binance futures + Bybit) ----------
function liquidationFeeds(onLiq, onState) {
  const socks = [];
  const state = { binance: 'wait', bybit: 'wait' };
  const report = () => onState(state);
  try {
    const b = new WebSocket('wss://fstream.binance.com/ws/!forceOrder@arr');
    b.onopen = () => { state.binance = 'open'; report(); };
    b.onerror = () => { state.binance = 'err'; report(); };
    b.onmessage = (m) => {
      const o = JSON.parse(m.data).o;
      // Side of the forced order: SELL closes a long, BUY closes a short.
      onLiq({ venue: 'Binance', ts: o.T, symbol: o.s.replace(/USDT$/, ''), long: o.S === 'SELL', qty: +o.q, price: +o.ap || +o.p, usd: (+o.q) * (+o.ap || +o.p) });
    };
    socks.push(b);
  } catch { state.binance = 'err'; }
  try {
    const y = new WebSocket('wss://stream.bybit.com/v5/public/linear');
    const args = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'LINK', 'LTC'].map((c) => `allLiquidation.${c}USDT`);
    let ping;
    y.onopen = () => { state.bybit = 'open'; report(); y.send(JSON.stringify({ op: 'subscribe', args })); ping = setInterval(() => y.readyState === 1 && y.send('{"op":"ping"}'), 20000); };
    y.onerror = () => { state.bybit = 'err'; report(); };
    y.onclose = () => clearInterval(ping);
    y.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (!d.topic?.startsWith('allLiquidation')) return;
      for (const x of d.data) {
        // Bybit: side "Buy" = a long position was liquidated.
        onLiq({ venue: 'Bybit', ts: x.T, symbol: x.s.replace(/USDT$/, ''), long: x.S === 'Buy', qty: +x.v, price: +x.p, usd: (+x.v) * (+x.p) });
      }
    };
    socks.push(y);
  } catch { state.bybit = 'err'; }
  report();
  return () => socks.forEach((s) => { s.onclose = null; s.close(); });
}

export async function mount(root) {
  let chartCoin = localStorage.getItem('orbe.crypto.coin') || 'BTC';
  let iv = localStorage.getItem('orbe.crypto.iv') || '1m';
  if (!INTERVALS[iv]) iv = '1m';
  let provider = null, sock = null, closed = false, retry;
  const rows = new Map();

  root.append(h(`
    <div class="grid" style="gap:12px">
      <div class="stats" id="c-stats"></div>
      <div class="grid g-side">
        <section class="panel">
          <div class="panel-head"><h2 id="c-title">BTC / USD</h2><span id="c-tag">${tag('wait')}</span><span class="spacer"></span>
            <div class="seg" id="c-iv">${Object.keys(INTERVALS).map((k) => `<button data-iv="${k}" aria-pressed="${k === iv}">${k}</button>`).join('')}</div>
          </div>
          <div class="panel-body flush"><div class="chart tall" id="c-chart"></div></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Mercado</h2><span class="spacer"></span><span class="note" id="c-prov"></span></div>
          <div class="table-wrap" style="max-height:470px">
            <table><thead><tr><th>Activo</th><th class="num">Precio</th><th class="num">24 h</th><th class="num">Volumen 24 h</th></tr></thead><tbody id="c-rows"></tbody></table>
          </div>
        </section>
      </div>
      <div class="grid g-side">
        <section class="panel">
          <div class="panel-head"><h2>Liquidaciones de futuros</h2><span id="l-tag">${tag('wait')}</span><span class="spacer"></span>
            <div class="legend"><span><i style="background:var(--down)"></i>Largos liquidados</span><span><i style="background:var(--up)"></i>Cortos liquidados</span></div>
          </div>
          <div class="stats" id="l-stats" style="border-width:0 0 1px;border-radius:0"></div>
          <ul class="feed" id="l-feed"><li class="muted" style="display:block">Esperando liquidaciones… Llegan en ráfagas cuando el precio se mueve fuerte; los totales cuentan desde que abriste la página.</li></ul>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Dominancia</h2><span id="d-tag">${tag('wait')}</span></div>
          <div class="panel-body"><div class="bars" id="d-bars"></div><p class="note" id="d-note" style="margin-top:12px"></p></div>
        </section>
      </div>
    </div>`));

  const chart = makeChart($('#c-chart', root), {}, 'America/Mexico_City');
  const series = chart.addCandlestickSeries(candleStyle);
  const volume = chart.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
  chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  const tbody = $('#c-rows', root);

  function renderRow(t) {
    const prev = rows.get(t.coin);
    rows.set(t.coin, t);
    let tr = tbody.querySelector(`tr[data-symbol="${t.coin}"]`);
    if (!tr) {
      tr = document.createElement('tr');
      tr.dataset.symbol = t.coin;
      tr.innerHTML = `<td><b>${esc(t.coin)}</b></td><td class="num p"></td><td class="num c"></td><td class="num v"></td>`;
      tr.addEventListener('click', () => selectCoin(t.coin));
      // Keep the watchlist in COINS order regardless of which update arrives first.
      const after = [...tbody.children].find((x) => COINS.indexOf(x.dataset.symbol) > COINS.indexOf(t.coin));
      tbody.insertBefore(tr, after ?? null);
    }
    tr.classList.toggle('sel', t.coin === chartCoin);
    const chg = (t.last / t.open - 1) * 100;
    tr.querySelector('.p').textContent = price(t.last);
    const c = tr.querySelector('.c'); c.textContent = pct(chg); c.className = 'num c ' + signCls(chg);
    tr.querySelector('.v').textContent = '$' + compact(t.quoteVol);
    if (prev && prev.last !== t.last) {
      tr.classList.remove('flash-up', 'flash-down'); void tr.offsetWidth;
      tr.classList.add(t.last > prev.last ? 'flash-up' : 'flash-down');
    }
    if (t.coin === chartCoin) $('#c-title', root).innerHTML = `${esc(t.coin)} / USD <span class="${signCls(chg)}" style="font-family:var(--mono);margin-left:8px">${price(t.last)} ${pct(chg)}</span>`;
  }

  async function loadChart() {
    $('#c-title', root).textContent = `${chartCoin} / USD`;
    $$('tr[data-symbol]', tbody).forEach((tr) => tr.classList.toggle('sel', tr.dataset.symbol === chartCoin));
    try {
      const k = await provider.klines(chartCoin, iv);
      series.setData(k);
      volume.setData(k.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? 'rgba(34,171,148,.35)' : 'rgba(242,54,69,.35)' })));
      chart.timeScale().fitContent();
    } catch (e) { console.warn('klines', e); series.setData([]); volume.setData([]); }
  }

  function openStream() {
    if (sock) { sock.onclose = null; sock.close(); }
    const live = (ok) => { $('#c-tag', root).innerHTML = tag(ok ? 'live' : 'err'); status.set('crypto', `Cripto: ${provider.name} (WebSocket)`, ok ? 'live' : 'err'); };
    sock = provider.connect(COINS, iv, chartCoin, {
      ticker: renderRow,
      kline: (b) => {
        series.update(b);
        volume.update({ time: b.time, value: b.volume, color: b.close >= b.open ? 'rgba(34,171,148,.35)' : 'rgba(242,54,69,.35)' });
      },
    });
    sock.onopen = ((orig) => function () { live(true); orig?.call(this); })(sock.onopen);
    sock.onclose = () => { if (closed) return; live(false); retry = setTimeout(openStream, 3000); };
  }

  async function pickProvider() {
    for (const p of PROVIDERS) {
      try {
        const t = await p.tickers(COINS);
        if (t.length) { provider = p; t.forEach(renderRow); return true; }
      } catch (e) { console.warn(p.name, e.message); }
    }
    return false;
  }

  function selectCoin(c) {
    chartCoin = c; localStorage.setItem('orbe.crypto.coin', c);
    loadChart(); openStream();
  }
  $$('#c-iv button', root).forEach((b) => b.addEventListener('click', () => {
    iv = b.dataset.iv; localStorage.setItem('orbe.crypto.iv', iv);
    $$('#c-iv button', root).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    loadChart(); openStream();
  }));

  // ---------- liquidations ----------
  const feed = $('#l-feed', root);
  const liqs = [];
  let feedEmpty = true;
  function liqStats() {
    const now = Date.now();
    const win = liqs.filter((l) => now - l.ts < 3600e3);
    const longs = win.filter((l) => l.long).reduce((a, l) => a + l.usd, 0);
    const shorts = win.filter((l) => !l.long).reduce((a, l) => a + l.usd, 0);
    const biggest = win.reduce((m, l) => (l.usd > (m?.usd ?? 0) ? l : m), null);
    $('#l-stats', root).innerHTML = [
      ['Largos · 1 h', `<span class="down">$${compact(longs)}</span>`],
      ['Cortos · 1 h', `<span class="up">$${compact(shorts)}</span>`],
      ['Eventos · 1 h', num(win.length, 0)],
      ['Mayor', biggest ? `$${compact(biggest.usd)} <span class="muted" style="font-size:12px">${esc(biggest.symbol)}</span>` : '—'],
    ].map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  }
  liqStats();
  const offLiq = liquidationFeeds((l) => {
    liqs.push(l); if (liqs.length > 3000) liqs.shift();
    if (feedEmpty) { feed.innerHTML = ''; feedEmpty = false; }
    const li = document.createElement('li');
    li.className = 'new' + (l.long ? ' sell' : '');
    li.innerHTML = `<span class="muted">${fmtTime(l.ts, 'America/Mexico_City')}</span><span><b>${esc(l.symbol)}</b> ${l.long ? '<span class="down">largo</span>' : '<span class="up">corto</span>'} @ ${price(l.price)} <span class="muted">${esc(l.venue)}</span></span><span class="${l.long ? 'down' : 'up'}">$${compact(l.usd)}</span>`;
    feed.prepend(li);
    while (feed.children.length > 120) feed.lastChild.remove();
    liqStats();
  }, (st) => {
    const ok = Object.values(st).filter((v) => v === 'open').length;
    const venues = Object.entries(st).filter(([, v]) => v === 'open').map(([k]) => (k === 'binance' ? 'Binance' : 'Bybit')).join(' + ');
    const kind = ok ? 'live' : Object.values(st).every((v) => v === 'err') ? 'err' : 'wait';
    $('#l-tag', root).innerHTML = tag(kind);
    status.set('liq', `Liquidaciones: ${venues || 'sin conexión'}`, kind, 'Binance Futures !forceOrder y Bybit allLiquidation');
  });
  const liqTimer = setInterval(liqStats, 15000);

  // ---------- dominance (CoinGecko) ----------
  async function loadDominance() {
    try {
      const { data: g } = await getJSON('https://api.coingecko.com/api/v3/global');
      const pctMap = g.market_cap_percentage;
      const top = Object.entries(pctMap).sort((a, b) => b[1] - a[1]).slice(0, 8);
      const other = 100 - top.reduce((a, [, v]) => a + v, 0);
      const max = top[0][1];
      const palette = ['#e8a33d', '#9b7dff', '#22ab94', '#4c8dff', '#0bc4a5', '#f23645', '#a7b0bb', '#6e7884'];
      $('#d-bars', root).innerHTML = [...top, ['otros', other]].map(([k, v], i) =>
        `<div class="bar-row"><span style="overflow:hidden;text-overflow:ellipsis" title="${esc(k.toUpperCase())}">${esc(k.toUpperCase())}</span><div class="track"><div class="fill" style="left:0;width:${(v / max) * 100}%;background:${palette[i] ?? '#3a4552'}"></div></div><span class="val">${num(v, 1)}%</span></div>`).join('');
      const stats = [
        ['Cap. total', '$' + compact(g.total_market_cap.usd), `<span class="${signCls(g.market_cap_change_percentage_24h_usd)}">${pct(g.market_cap_change_percentage_24h_usd)} 24 h</span>`],
        ['Dominancia BTC', num(pctMap.btc, 1) + '%', ''],
        ['Dominancia ETH', num(pctMap.eth, 1) + '%', ''],
        ['Stablecoins', num((pctMap.usdt ?? 0) + (pctMap.usdc ?? 0), 1) + '%', 'USDT + USDC'],
        ['Volumen 24 h', '$' + compact(g.total_volume.usd), ''],
      ];
      $('#c-stats', root).innerHTML = stats.map(([k, v, s]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
      $('#d-note', root).textContent = `Participación en la capitalización total · CoinGecko · actualizado ${fmtTime(g.updated_at * 1000, 'America/Mexico_City', false)}`;
      $('#d-tag', root).innerHTML = tag('live');
      status.set('dom', 'Dominancia: CoinGecko (cada 2 min)', 'live');
    } catch (e) {
      $('#d-tag', root).innerHTML = tag('err');
      $('#d-note', root).textContent = 'CoinGecko no respondió (límite de peticiones). Se reintenta en 2 minutos.';
      status.set('dom', 'Dominancia: CoinGecko', 'err', e.message);
    }
  }
  loadDominance();
  const domTimer = setInterval(loadDominance, 120000);

  // ---------- start ----------
  status.set('crypto', 'Cripto: conectando…', 'wait');
  if (await pickProvider()) {
    $('#c-prov', root).textContent = 'Fuente: ' + provider.name;
    await loadChart();
    if (!closed) openStream();
  } else {
    $('#c-tag', root).innerHTML = tag('err');
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty"><h3>Sin conexión a exchanges</h3>Ni Binance, Binance.US ni Coinbase respondieron desde tu red.</div></td></tr>`;
    status.set('crypto', 'Cripto: sin proveedor disponible', 'err');
  }

  return () => {
    closed = true;
    clearTimeout(retry); clearInterval(domTimer); clearInterval(liqTimer);
    if (sock) { sock.onclose = null; sock.close(); }
    offLiq();
    chart.remove();
    status.clear(['crypto', 'liq', 'dom']);
  };
}
