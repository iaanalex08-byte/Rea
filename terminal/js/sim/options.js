// Simulated options market: underlying price, option chain (open interest + IV surface),
// Black-Scholes greeks, dealer gamma/delta exposure and an aggressor-tagged trade flow.
//
// Everything here is synthetic. The public interface (snapshot / flow / onTick) is what a
// real provider (Polygon, ThetaData, Tradier, CBOE…) would need to implement to replace it.

import { rng, hashStr, gauss } from '../util.js';

export const UNDERLYINGS = {
  SPY: { spot: 600, step: 1, width: 0.10, oiScale: 60000, baseVol: 0.15 },
  QQQ: { spot: 520, step: 1, width: 0.11, oiScale: 40000, baseVol: 0.19 },
  SPX: { spot: 6000, step: 5, width: 0.07, oiScale: 9000, baseVol: 0.15 },
  IWM: { spot: 225, step: 1, width: 0.12, oiScale: 25000, baseVol: 0.22 },
};

const R = 0.042; // risk-free rate
export const YEAR_SEC = 365 * 24 * 3600;
const SQ2PI = Math.sqrt(2 * Math.PI);
const npdf = (x) => Math.exp(-0.5 * x * x) / SQ2PI;
function ncdf(x) {
  // Abramowitz–Stegun 7.1.26
  const t = 1 / (1 + 0.3275911 * Math.abs(x));
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x / 2);
  return x >= 0 ? (1 + y) / 2 : (1 - y) / 2;
}

export function greeks(S, K, T, iv) {
  const sT = iv * Math.sqrt(T);
  const d1 = (Math.log(S / K) + (R + 0.5 * iv * iv) * T) / sT;
  const d2 = d1 - sT;
  const pd1 = npdf(d1);
  const disc = Math.exp(-R * T);
  const Nd1 = ncdf(d1), Nd2 = ncdf(d2);
  return {
    gamma: pd1 / (S * sT),
    callDelta: Nd1,
    putDelta: Nd1 - 1,
    vanna: -pd1 * d2 / iv,
    callPrice: S * Nd1 - K * disc * Nd2,
    putPrice: K * disc * (1 - Nd2) - S * (1 - Nd1),
  };
}

// ---------- calendar ----------
export function nyParts(d) {
  const p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }).formatToParts(d);
  const g = (t) => p.find((x) => x.type === t).value;
  return { ymd: `${g('year')}-${g('month')}-${g('day')}`, wd: g('weekday') };
}
const isWeekday = (d) => { const w = d.getUTCDay(); return w > 0 && w < 6; };
export function thirdFriday(y, m) {
  const d = new Date(Date.UTC(y, m, 1));
  const first = (5 - d.getUTCDay() + 7) % 7;
  return new Date(Date.UTC(y, m, 1 + first + 14));
}
// Expiry close: 16:00 New York ≈ 21:00 UTC (20:00 in summer; 1h error is irrelevant here).
export const expiryTs = (d) => Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 21, 0);

export function buildExpiries(now = Date.now()) {
  const { ymd } = nyParts(new Date(now));
  const today = new Date(ymd + 'T00:00:00Z');
  const out = [];
  const seen = new Set();
  const add = (d, kind) => {
    const key = d.toISOString().slice(0, 10);
    if (seen.has(key) || expiryTs(d) <= now) return;
    seen.add(key);
    out.push({ key, ts: expiryTs(d), kind });
  };
  // Dailies for the next 5 trading days (0DTE included while the session is open).
  for (let i = 0, n = 0; n < 5 && i < 10; i++) {
    const d = new Date(today.getTime() + i * 864e5);
    if (isWeekday(d)) { add(d, i === 0 ? '0DTE' : 'diario'); n++; }
  }
  // Next weekly Fridays.
  for (let i = 5; i < 35; i++) {
    const d = new Date(today.getTime() + i * 864e5);
    if (d.getUTCDay() === 5) add(d, 'semanal');
  }
  // Next three monthlies.
  for (let k = 0; k < 4; k++) {
    const y = today.getUTCFullYear(), m = today.getUTCMonth() + k;
    add(thirdFriday(y + Math.floor(m / 12), m % 12), 'mensual');
  }
  return out.sort((a, b) => a.ts - b.ts).slice(0, 10);
}

// ---------- shared chain model ----------
// Everything that turns an option chain into dealer exposure. Subclasses provide:
//   spot, expiries [{key, ts, kind}], strikes [K], oi[expiry][strike] = {call, put, vol},
//   iv(K, T, S) and cfg.width (strike range shown, as a fraction of spot).
export class ChainModel {
  constructor() {
    this.listeners = new Set();
    this.flowListeners = new Set();
    this.minuteFlow = new Map(); // minute ts -> {callBuy, callSell, putBuy, putSell, deltaNotional}
    this.big = []; // recent large trades, newest first
    this.lastSnap = null;
    this.ready = Promise.resolve(this);
  }

  T(e, now = Date.now()) { return Math.max((e.ts - now) / 1000 / YEAR_SEC, 0.5 / (365 * 24)); }

  expIndex(filter) {
    if (filter === 'all') return this.expiries.map((_, i) => i);
    if (filter === '0dte') return [0];
    if (filter === 'weekly') return this.expiries.map((e, i) => (i < 5 ? i : -1)).filter((i) => i >= 0);
    if (filter === 'monthly') return this.expiries.map((e, i) => (e.kind === 'mensual' ? i : -1)).filter((i) => i >= 0);
    const i = this.expiries.findIndex((e) => e.key === filter);
    return i >= 0 ? [i] : [0];
  }

  // Dealer exposure for a hypothetical spot S (used for the gamma-flip search too).
  #exposure(S, idx, now, perStrike) {
    let total = 0;
    const mul = 100 * S * S * 0.01; // $ gamma per 1% move
    for (const ei of idx) {
      const e = this.expiries[ei];
      const T = this.T(e, now);
      const row = this.oi[ei];
      for (let si = 0; si < this.strikes.length; si++) {
        const K = this.strikes[si];
        if (Math.abs(K - S) / S > 0.25) continue;
        const o = row[si];
        const g = greeks(S, K, T, this.iv(K, T, S));
        const cg = g.gamma * o.call * mul;   // dealers long calls (customer overwriting)
        const pg = -g.gamma * o.put * mul;   // dealers short puts (customer hedging)
        total += cg + pg;
        if (perStrike) {
          const p = perStrike[si];
          p.callGex += cg; p.putGex += pg;
          p.callOI += o.call; p.putOI += o.put;
          p.dex += (g.callDelta * o.call + g.putDelta * o.put) * 100 * S;
          p.vanna += (g.vanna * (o.call - o.put)) * 100 * S * 0.01;
          p.vol += o.vol;
        }
      }
    }
    return total;
  }

  snapshot(filter = 'all') {
    const now = Date.now();
    const idx = this.expIndex(filter);
    const S = this.spot;
    const per = this.strikes.map((K) => ({ K, callGex: 0, putGex: 0, callOI: 0, putOI: 0, dex: 0, vanna: 0, vol: 0 }));
    const total = this.#exposure(S, idx, now, per);
    for (const p of per) p.net = p.callGex + p.putGex;

    let callWall = per[0], putWall = per[0], maxAbs = per[0];
    for (const p of per) {
      if (p.callGex > callWall.callGex) callWall = p;
      if (p.putGex < putWall.putGex) putWall = p;
      if (Math.abs(p.net) > Math.abs(maxAbs.net)) maxAbs = p;
    }

    // Gamma flip: spot level where total dealer gamma changes sign.
    const grid = [];
    const span = this.cfg.width * 0.75;
    const n = 36;
    for (let i = 0; i <= n; i++) {
      const s = S * (1 - span + (2 * span * i) / n);
      grid.push([s, this.#exposure(s, idx, now, null)]);
    }
    let flip = null, best = Infinity;
    for (let i = 1; i < grid.length; i++) {
      const [s0, g0] = grid[i - 1], [s1, g1] = grid[i];
      if ((g0 <= 0 && g1 > 0) || (g0 >= 0 && g1 < 0)) {
        const x = s0 + (s1 - s0) * (-g0 / (g1 - g0));
        if (Math.abs(x - S) < best) { best = Math.abs(x - S); flip = x; }
      }
    }

    // Heatmap: net GEX per (expiry, strike) near spot.
    const heat = this.expiries.map((e, ei) => {
      const T = this.T(e, now);
      return this.strikes.map((K, si) => {
        if (Math.abs(K - S) / S > this.cfg.width) return 0;
        const o = this.oi[ei][si];
        const g = greeks(S, K, T, this.iv(K, T));
        return g.gamma * (o.call - o.put) * 100 * S * S * 0.01;
      });
    });

    const dexTotal = per.reduce((a, p) => a + p.dex, 0);
    const callOI = per.reduce((a, p) => a + p.callOI, 0);
    const putOI = per.reduce((a, p) => a + p.putOI, 0);
    this.lastSnap = {
      time: now, spot: S, filter, strikes: per, total, dexTotal,
      callWall: callWall.K, putWall: putWall.K, flip, maxGamma: maxAbs.K,
      pcr: putOI / Math.max(1, callOI), heat, gridCurve: grid,
    };
    return this.lastSnap;
  }

  onTick(f) { this.listeners.add(f); return () => this.listeners.delete(f); }
  onFlow(f) { this.flowListeners.add(f); return () => this.flowListeners.delete(f); }
  flowSeries() { return [...this.minuteFlow.values()]; }
}

// ---------- engine ----------
export class OptionsSim extends ChainModel {
  constructor(symbol) {
    super();
    this.symbol = symbol;
    this.cfg = UNDERLYINGS[symbol];
    const day = nyParts(new Date()).ymd;
    this.seed = hashStr(symbol + day);
    this.r = rng(this.seed ^ 0x9e3779b9);
    this.volShock = 0; // added to ATM IV, mean-reverting, rises on selloffs
    this.source = 'sim';
    this.expiries = buildExpiries();
    this.#buildHistory();
    this.#buildChain();
    // Backfill the last two hours of flow so the charts are not empty on first load.
    const now = Date.now();
    for (const c of this.candles.slice(-120)) {
      this.lastRet = (c.close - c.open) / c.open;
      for (let k = 0; k < 20; k++) this.#trades(c.time, c.time * 1000 + k * 3000, c.close);
    }
    this.lastRet = 0;
  }

  // Intraday history of 1-minute candles ending now (seeded, deterministic per day).
  #buildHistory() {
    const hr = rng(this.seed);
    const nowMin = Math.floor(Date.now() / 60000) * 60;
    const n = 600;
    const sig = this.cfg.baseVol / Math.sqrt(252 * 390);
    let p = this.cfg.spot * (1 + (hr() - 0.5) * 0.03);
    this.candles = [];
    for (let i = n; i > 0; i--) {
      const o = p;
      let hi = o, lo = o;
      for (let k = 0; k < 6; k++) {
        p *= 1 + gauss(hr) * sig / Math.sqrt(6) + (this.cfg.spot - p) / this.cfg.spot * 0.002;
        hi = Math.max(hi, p); lo = Math.min(lo, p);
      }
      this.candles.push({ time: nowMin - i * 60, open: o, high: hi, low: lo, close: p });
    }
    this.spot = p;
    this.open = this.candles[Math.max(0, this.candles.length - 390)].open;
    this.anchor = this.cfg.spot; // OI is centred where the market was when positions were opened
  }

  #buildChain() {
    const { step, width, oiScale } = this.cfg;
    const S0 = this.anchor;
    const lo = Math.ceil((S0 * (1 - width * 1.4)) / step) * step;
    const hi = Math.floor((S0 * (1 + width * 1.4)) / step) * step;
    this.strikes = [];
    for (let k = lo; k <= hi + 1e-9; k += step) this.strikes.push(+k.toFixed(2));
    const or = rng(this.seed ^ 0x51ed27);
    // A handful of "institutional" strikes with outsized positioning.
    const hot = new Map();
    for (let i = 0; i < 6; i++) {
      const k = this.strikes[Math.floor(or() * this.strikes.length)];
      hot.set(k, 2 + or() * 3);
    }
    this.oi = this.expiries.map((e) => {
      const T = Math.max((e.ts - Date.now()) / 1000 / YEAR_SEC, 1 / 365);
      const kindMul = e.kind === 'mensual' ? 2.6 : e.kind === 'semanal' ? 1.2 : e.kind === '0DTE' ? 0.8 : 0.6;
      const spread = width * (0.35 + Math.sqrt(T) * 1.6);
      return this.strikes.map((K) => {
        const m = (K - S0) / S0;
        const bell = Math.exp(-((m / spread) ** 2));
        const round = K % (step * 10) === 0 ? 2.4 : K % (step * 5) === 0 ? 1.5 : 1;
        const h = hot.get(K) ?? 1;
        const noise = () => Math.exp(gauss(or) * 0.35);
        const callBias = m > 0 ? 1.25 : 0.55; // calls sold/bought OTM above spot
        const putBias = m < 0 ? 1.45 : 0.45;  // put hedges concentrate below
        return {
          call: Math.round(oiScale * kindMul * bell * round * h * callBias * noise()),
          put: Math.round(oiScale * kindMul * bell * round * h * putBias * noise() * 1.1),
          vol: 0,
        };
      });
    });
  }

  // Term structure: upward sloping (contango) in calm markets. Selloffs raise volShock, which
  // lifts the short end most and can invert the curve (backwardation) under stress.
  atmIv(T) {
    const calm = this.cfg.baseVol * (0.86 + 0.32 * Math.sqrt(Math.min(T, 1)));
    return Math.max(0.05, calm + this.volShock * Math.exp(-T * 6));
  }

  // Smile/skew in standardized moneyness; short expiries are normalized at one week so the
  // wings stay realistic instead of exploding as T → 0.
  iv(K, T, S = this.spot) {
    const Tm = Math.max(T, 7 / 365);
    const m = Math.max(-2.5, Math.min(2.5, Math.log(K / S) / Math.sqrt(Tm)));
    return Math.max(0.04, this.atmIv(T) * (1 - 0.35 * m + 0.6 * m * m));
  }

  // ---- live loop ----
  start() {
    if (this.timer) return;
    this.timer = setInterval(() => this.#tick(), 1000);
  }
  stop() { clearInterval(this.timer); this.timer = null; }

  #tick() {
    const r = this.r;
    const sig = this.atmIv(1 / 52) / Math.sqrt(252 * 23400);
    // Price dynamics depend on dealer positioning: positive gamma pins toward the largest
    // gamma strike, negative gamma amplifies moves (dealers hedge in the trend direction).
    const snap = this.lastSnap;
    let drift = 0, volMul = 1;
    if (snap) {
      if (snap.total > 0) drift = (snap.maxGamma - this.spot) / this.spot * 0.0025;
      else { volMul = 1.7; drift = (this.lastRet ?? 0) * 0.15; }
    }
    const ret = drift + gauss(r) * sig * volMul * 2.2;
    this.lastRet = ret;
    this.spot *= 1 + ret;
    this.volShock = this.volShock * 0.995 - ret * 1.4;
    this.volShock = Math.max(-0.05, Math.min(0.25, this.volShock));

    const t = Math.floor(Date.now() / 60000) * 60;
    const last = this.candles[this.candles.length - 1];
    if (last.time === t) {
      last.high = Math.max(last.high, this.spot); last.low = Math.min(last.low, this.spot); last.close = this.spot;
    } else {
      this.candles.push({ time: t, open: last.close, high: Math.max(last.close, this.spot), low: Math.min(last.close, this.spot), close: this.spot });
      if (this.candles.length > 1500) this.candles.shift();
    }

    this.#trades(t, Date.now(), this.spot);
    const bar = this.candles[this.candles.length - 1];
    this.listeners.forEach((f) => f(bar));
  }

  #trades(minute, now, S) {
    const r = this.r;
    const n = 2 + Math.floor(r() * 7);
    let agg = this.minuteFlow.get(minute);
    if (!agg) {
      agg = { time: minute, callBuy: 0, callSell: 0, putBuy: 0, putSell: 0, deltaNotional: 0 };
      this.minuteFlow.set(minute, agg);
      if (this.minuteFlow.size > 400) this.minuteFlow.delete(this.minuteFlow.keys().next().value);
    }
    const bias = (this.lastRet ?? 0) > 0 ? 0.56 : 0.44; // flow chases the tape
    for (let i = 0; i < n; i++) {
      const ei = r() < 0.45 ? 0 : Math.min(this.expiries.length - 1, Math.floor(-Math.log(1 - r()) * 2));
      const e = this.expiries[ei];
      const T = this.T(e, now);
      const isCall = r() < bias + 0.04;
      const otm = Math.abs(gauss(r)) * S * 0.012 * (1 + T * 6);
      const Kraw = isCall ? S + otm : S - otm;
      const si = Math.max(0, Math.min(this.strikes.length - 1, Math.round((Kraw - this.strikes[0]) / this.cfg.step)));
      const K = this.strikes[si];
      const g = greeks(S, K, T, this.iv(K, T));
      const prem = Math.max(0.01, isCall ? g.callPrice : g.putPrice);
      const whale = r() < 0.012;
      const size = Math.max(1, Math.round(Math.exp(gauss(r) * 1.1 + 2.2) * (whale ? 60 : 1)));
      const buy = r() < (isCall ? bias : 1 - bias) + 0.02;
      const side = buy ? 1 : -1;
      const delta = isCall ? g.callDelta : g.putDelta;
      const dn = side * delta * size * 100 * S;
      agg.deltaNotional += dn;
      agg[(isCall ? 'call' : 'put') + (buy ? 'Buy' : 'Sell')] += prem * size * 100;
      this.oi[ei][si].vol += size;
      const trade = { ts: now, expiry: e.key, kind: e.kind, K, type: isCall ? 'C' : 'P', side: buy ? 'compra' : 'venta', size, price: prem, premium: prem * size * 100, deltaNotional: dn, iv: this.iv(K, T) };
      if (trade.premium >= 100_000) { this.big.unshift(trade); if (this.big.length > 120) this.big.pop(); }
      this.flowListeners.forEach((f) => f(trade));
    }
  }

}

// One running engine per symbol, shared by the gamma map, flow and volatility views.
const engines = new Map();
export function getSim(symbol) {
  let e = engines.get(symbol);
  if (!e) { e = new OptionsSim(symbol); engines.set(symbol, e); }
  e.start();
  return e;
}
