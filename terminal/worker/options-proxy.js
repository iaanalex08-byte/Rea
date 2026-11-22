// ORBE options proxy — Cloudflare Worker.
//
// Keeps the data-provider API key on the server and returns a compact, provider-independent
// option chain to the terminal (terminal/js/options/real.js). Responses are cached for a few
// seconds so many open terminals cost a handful of provider requests.
//
// Endpoints (GET):
//   /chain?symbol=SPY    -> { symbol, provider, delayed, asOf, spot, contracts: [[expiry, strike, 'C'|'P', oi, volume, iv, mid]] }
//   /candles?symbol=SPY  -> { symbol, candles: [[unixSeconds, open, high, low, close, volume]] }
//   /health              -> { ok, provider }
//
// Settings (wrangler.toml [vars] or the Cloudflare dashboard; keys as encrypted secrets):
//   PROVIDER          'tradier' | 'polygon'
//   TRADIER_TOKEN     secret, Tradier access token
//   TRADIER_SANDBOX   'true' to use sandbox.tradier.com (free developer account, 15-min delayed)
//   POLYGON_KEY       secret, Polygon/Massive API key
//   POLYGON_BASE      default https://api.polygon.io
//   POLYGON_DELAYED   'true' when your Polygon plan is 15-min delayed (Starter)
//   ALLOWED_ORIGINS   comma-separated origins allowed to call the proxy, e.g. https://usuario.github.io
//   SYMBOLS           allowed underlyings, default SPY,QQQ,SPX,IWM
//   MAX_EXPIRIES      default 10
//   STRIKE_RANGE      fraction of spot kept on each side, default 0.15
//   CACHE_SECONDS     default 20

const DEFAULTS = { SYMBOLS: 'SPY,QQQ,SPX,IWM', MAX_EXPIRIES: '10', STRIKE_RANGE: '0.15', CACHE_SECONDS: '20' };
// Index options and their price series use different tickers on Polygon.
const POLYGON_TICKERS = { SPX: { options: 'I:SPX', stock: 'I:SPX' }, NDX: { options: 'I:NDX', stock: 'I:NDX' }, RUT: { options: 'I:RUT', stock: 'I:RUT' } };

const cfg = (env, k) => (env[k] ?? DEFAULTS[k] ?? '').toString().trim();
const num = (v) => (v == null || v === '' || Number.isNaN(+v) ? null : +v);
const round = (v, d = 4) => (v == null ? null : Math.round(v * 10 ** d) / 10 ** d);
const asArray = (x) => (x == null ? [] : Array.isArray(x) ? x : [x]);

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function getJSON(url, headers = {}) {
  const r = await fetch(url, { headers: { Accept: 'application/json', ...headers } });
  if (!r.ok) {
    const body = (await r.text()).slice(0, 200);
    throw new HttpError(502, `Proveedor respondió HTTP ${r.status}: ${body}`);
  }
  return r.json();
}

function nyDate(d = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(d);
}
const addDays = (ymd, n) => new Date(Date.parse(ymd + 'T12:00:00Z') + n * 864e5).toISOString().slice(0, 10);

// ---------------------------------------------------------------- Tradier
const tradier = {
  base: (env) => (cfg(env, 'TRADIER_SANDBOX') === 'true' ? 'https://sandbox.tradier.com/v1' : 'https://api.tradier.com/v1'),
  headers: (env) => {
    if (!cfg(env, 'TRADIER_TOKEN')) throw new HttpError(500, 'Falta el secreto TRADIER_TOKEN');
    return { Authorization: `Bearer ${cfg(env, 'TRADIER_TOKEN')}` };
  },
  delayed: (env) => cfg(env, 'TRADIER_SANDBOX') === 'true',

  async chain(env, symbol) {
    const base = this.base(env), h = this.headers(env);
    const [q, ex] = await Promise.all([
      getJSON(`${base}/markets/quotes?symbols=${symbol}`, h),
      getJSON(`${base}/markets/options/expirations?symbol=${symbol}&includeAllRoots=true`, h),
    ]);
    const quote = asArray(q?.quotes?.quote)[0];
    const spot = num(quote?.last) ?? num(quote?.close) ?? num(quote?.prevclose);
    if (!spot) throw new HttpError(502, `Sin cotización para ${symbol}`);
    const today = nyDate();
    const dates = asArray(ex?.expirations?.date).filter((d) => d >= today).slice(0, +cfg(env, 'MAX_EXPIRIES'));
    const range = +cfg(env, 'STRIKE_RANGE');
    const chains = await Promise.all(dates.map((d) =>
      getJSON(`${base}/markets/options/chains?symbol=${symbol}&expiration=${d}&greeks=true&includeAllRoots=true`, h)));
    const contracts = [];
    chains.forEach((c, i) => {
      for (const o of asArray(c?.options?.option)) {
        const K = num(o.strike);
        if (K == null || Math.abs(K - spot) / spot > range) continue;
        const bid = num(o.bid), ask = num(o.ask);
        const mid = bid > 0 && ask > 0 ? (bid + ask) / 2 : num(o.last) ?? 0;
        const iv = num(o.greeks?.mid_iv) || num(o.greeks?.smv_vol) || null;
        contracts.push([o.expiration_date || dates[i], K, o.option_type === 'put' ? 'P' : 'C', num(o.open_interest) ?? 0, num(o.volume) ?? 0, round(iv), round(mid, 3)]);
      }
    });
    return { spot, delayed: this.delayed(env), contracts };
  },

  async candles(env, symbol) {
    const start = `${addDays(nyDate(), -4)} 04:00`;
    const d = await getJSON(`${this.base(env)}/markets/timesales?symbol=${symbol}&interval=1min&start=${encodeURIComponent(start)}&session_filter=open`, this.headers(env));
    return asArray(d?.series?.data).map((b) => [num(b.timestamp) ?? Math.floor(Date.parse(b.time + '-05:00') / 1000), b.open, b.high, b.low, b.close, b.volume ?? 0]);
  },
};

// ---------------------------------------------------------------- Polygon / Massive
const polygon = {
  base: (env) => cfg(env, 'POLYGON_BASE') || 'https://api.polygon.io',
  key: (env) => {
    if (!cfg(env, 'POLYGON_KEY')) throw new HttpError(500, 'Falta el secreto POLYGON_KEY');
    return cfg(env, 'POLYGON_KEY');
  },
  tickers: (symbol) => POLYGON_TICKERS[symbol] ?? { options: symbol, stock: symbol },
  withKey: (url, key) => url + (url.includes('?') ? '&' : '?') + 'apiKey=' + encodeURIComponent(key),

  async spot(env, symbol) {
    const t = this.tickers(symbol), key = this.key(env), base = this.base(env);
    try {
      const s = await getJSON(this.withKey(`${base}/v3/snapshot/options/${t.options}?limit=1`, key));
      const ua = s?.results?.[0]?.underlying_asset;
      const v = num(ua?.price) ?? num(ua?.value);
      if (v) return v;
    } catch { /* fall through */ }
    try {
      const p = await getJSON(this.withKey(`${base}/v2/aggs/ticker/${t.stock}/prev`, key));
      const v = num(p?.results?.[0]?.c);
      if (v) return v;
    } catch { /* fall through */ }
    return null;
  },

  async chain(env, symbol) {
    const key = this.key(env), base = this.base(env), t = this.tickers(symbol);
    const range = +cfg(env, 'STRIKE_RANGE');
    let spot = await this.spot(env, symbol);
    const today = nyDate();
    const params = new URLSearchParams({ 'expiration_date.gte': today, 'expiration_date.lte': addDays(today, 70), limit: '250' });
    if (spot) { params.set('strike_price.gte', String(Math.floor(spot * (1 - range)))); params.set('strike_price.lte', String(Math.ceil(spot * (1 + range)))); }
    let url = `${base}/v3/snapshot/options/${t.options}?${params}`;
    const rows = [];
    for (let page = 0; url && page < 60; page++) {
      const d = await getJSON(this.withKey(url, key));
      rows.push(...(d.results ?? []));
      url = d.next_url || null;
    }
    // Without an underlying quote, estimate spot from the nearest expiry's 50-delta call.
    if (!spot) {
      const calls = rows.filter((r) => r.details?.contract_type === 'call' && num(r.greeks?.delta) != null);
      const near = calls.sort((a, b) => Math.abs(a.greeks.delta - 0.5) - Math.abs(b.greeks.delta - 0.5))[0];
      spot = num(near?.details?.strike_price);
      if (!spot) throw new HttpError(502, `Sin precio del subyacente para ${symbol}`);
    }
    const dates = [...new Set(rows.map((r) => r.details?.expiration_date).filter(Boolean))].sort().slice(0, +cfg(env, 'MAX_EXPIRIES'));
    const keep = new Set(dates);
    const contracts = [];
    for (const r of rows) {
      const d = r.details ?? {};
      const K = num(d.strike_price);
      if (!keep.has(d.expiration_date) || K == null || Math.abs(K - spot) / spot > range) continue;
      const mid = num(r.last_quote?.midpoint) ?? num(r.day?.close) ?? num(r.day?.vwap) ?? 0;
      contracts.push([d.expiration_date, K, d.contract_type === 'put' ? 'P' : 'C', num(r.open_interest) ?? 0, num(r.day?.volume) ?? 0, round(num(r.implied_volatility)), round(mid, 3)]);
    }
    return { spot, delayed: cfg(env, 'POLYGON_DELAYED') === 'true', contracts };
  },

  async candles(env, symbol) {
    const t = this.tickers(symbol), today = nyDate();
    const d = await getJSON(this.withKey(`${this.base(env)}/v2/aggs/ticker/${t.stock}/range/1/minute/${addDays(today, -4)}/${today}?adjusted=true&sort=asc&limit=50000`, this.key(env)));
    return (d.results ?? []).map((b) => [Math.floor(b.t / 1000), b.o, b.h, b.l, b.c, b.v ?? 0]);
  },
};

const PROVIDERS = { tradier, polygon };

// ---------------------------------------------------------------- HTTP
function corsHeaders(env, origin) {
  const allowed = cfg(env, 'ALLOWED_ORIGINS').split(',').map((s) => s.trim()).filter(Boolean);
  const ok = allowed.includes('*') || (origin && allowed.includes(origin));
  return ok ? { 'Access-Control-Allow-Origin': allowed.includes('*') ? '*' : origin, Vary: 'Origin' } : {};
}

function json(body, status, extra) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...extra } });
}

export async function handle(request, env, ctx) {
  const url = new URL(request.url);
  const origin = request.headers.get('Origin');
  const cors = corsHeaders(env, origin);
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: { ...cors, 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Max-Age': '86400' } });
  if (request.method !== 'GET') return json({ error: 'Solo GET' }, 405, cors);
  if (origin && !cors['Access-Control-Allow-Origin']) return json({ error: 'Origen no permitido' }, 403, {});

  const providerName = cfg(env, 'PROVIDER').toLowerCase();
  const provider = PROVIDERS[providerName];
  if (url.pathname === '/health') return json({ ok: !!provider, provider: providerName || null }, 200, cors);
  if (!provider) return json({ error: 'PROVIDER debe ser "tradier" o "polygon"' }, 500, cors);
  if (url.pathname !== '/chain' && url.pathname !== '/candles') return json({ error: 'Ruta desconocida' }, 404, cors);

  const symbol = (url.searchParams.get('symbol') || '').toUpperCase();
  const allowed = cfg(env, 'SYMBOLS').split(',').map((s) => s.trim().toUpperCase());
  if (!allowed.includes(symbol)) return json({ error: `Símbolo no permitido: ${symbol || '(vacío)'}` }, 400, cors);

  // Shared cache across all visitors (keyed without Origin so every page shares one entry).
  const ttl = Math.max(5, +cfg(env, 'CACHE_SECONDS'));
  const cacheKey = new Request(`https://orbe-options-cache${url.pathname}?symbol=${symbol}&p=${providerName}`);
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  if (cache) {
    const hit = await cache.match(cacheKey);
    if (hit) return json(await hit.json(), 200, { ...cors, 'X-Cache': 'HIT' });
  }

  try {
    let body;
    if (url.pathname === '/chain') {
      const c = await provider.chain(env, symbol);
      body = { symbol, provider: providerName, delayed: c.delayed, asOf: Date.now(), spot: c.spot, contracts: c.contracts };
    } else {
      body = { symbol, candles: await provider.candles(env, symbol) };
    }
    if (cache) {
      const stored = json(body, 200, { 'Cache-Control': `public, max-age=${ttl}` });
      ctx?.waitUntil?.(cache.put(cacheKey, stored));
    }
    return json(body, 200, { ...cors, 'X-Cache': 'MISS' });
  } catch (e) {
    return json({ error: e.message }, e.status || 502, cors);
  }
}

export default { fetch: handle };
