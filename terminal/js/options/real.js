// Real option-chain model. Reads a normalized chain from the ORBE options proxy (a Cloudflare
// Worker that holds the provider API key, see terminal/worker/) and reuses ChainModel for all
// exposure math, so the gamma map and volatility views work unchanged.
//
// Proxy contract:
//   GET {api}/chain?symbol=SPY   -> { symbol, provider, delayed, asOf, spot,
//                                     contracts: [[expiry 'YYYY-MM-DD', strike, 'C'|'P', oi, volume, iv, mid]] }
//   GET {api}/candles?symbol=SPY -> { candles: [[unixSeconds, open, high, low, close, volume]] }

import { ChainModel, UNDERLYINGS, expiryTs, thirdFriday, nyParts, greeks } from '../sim/options.js';
import { getJSON } from '../util.js';

const CHAIN_EVERY = 20_000;
const CANDLES_EVERY = 60_000;
const BIG_PREMIUM = 100_000;

function kindOf(key, todayKey) {
  if (key === todayKey) return '0DTE';
  const d = new Date(key + 'T00:00:00Z');
  if (d.getUTCDay() === 5) {
    const tf = thirdFriday(d.getUTCFullYear(), d.getUTCMonth());
    return tf.getUTCDate() === d.getUTCDate() ? 'mensual' : 'semanal';
  }
  return 'diario';
}

// Linear interpolation over sorted [x, y] pairs, flat beyond the ends.
function interp(pts, x) {
  if (!pts.length) return null;
  if (x <= pts[0][0]) return pts[0][1];
  if (x >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
  let lo = 0, hi = pts.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (pts[m][0] <= x) lo = m; else hi = m; }
  const [x0, y0] = pts[lo], [x1, y1] = pts[hi];
  return y0 + (y1 - y0) * ((x - x0) / (x1 - x0));
}

export class RealOptions extends ChainModel {
  constructor(symbol, api) {
    super();
    this.symbol = symbol;
    this.api = api.replace(/\/+$/, '');
    this.source = 'real';
    this.cfg = { width: UNDERLYINGS[symbol]?.width ?? 0.1, step: UNDERLYINGS[symbol]?.step ?? 1 };
    this.candles = [];
    this.prevVolume = null; // contract key -> cumulative volume at the previous poll
    this.ready = this.#load().then(() => this);
  }

  async #load() {
    const [chain, candles] = await Promise.all([
      getJSON(`${this.api}/chain?symbol=${encodeURIComponent(this.symbol)}`, { timeout: 25000 }),
      getJSON(`${this.api}/candles?symbol=${encodeURIComponent(this.symbol)}`, { timeout: 25000 }).catch(() => ({ candles: [] })),
    ]);
    this.#applyChain(chain);
    this.#applyCandles(candles);
  }

  #applyChain(d) {
    if (!d || !Array.isArray(d.contracts) || !d.contracts.length || !(d.spot > 0)) throw new Error('El proxy devolvió una cadena vacía');
    const S = d.spot;
    this.spot = S;
    this.provider = d.provider;
    this.delayed = !!d.delayed;
    this.asOf = d.asOf ?? Date.now();
    const todayKey = nyParts(new Date()).ymd;
    const now = Date.now();

    const expKeys = [...new Set(d.contracts.map((c) => c[0]))].filter((k) => expiryTs(new Date(k + 'T00:00:00Z')) > now).sort();
    const strikes = [...new Set(d.contracts.map((c) => +c[1]))].sort((a, b) => a - b);
    const eIdx = new Map(expKeys.map((k, i) => [k, i]));
    const sIdx = new Map(strikes.map((k, i) => [k, i]));
    const oi = expKeys.map(() => strikes.map(() => ({ call: 0, put: 0, vol: 0 })));
    const ivPts = expKeys.map(() => new Map()); // strike -> {C, P}
    const volume = new Map();

    for (const [e, kRaw, t, o, v, iv, mid] of d.contracts) {
      const ei = eIdx.get(e);
      if (ei == null) continue;
      const K = +kRaw, si = sIdx.get(K);
      const cell = oi[ei][si];
      if (t === 'C') cell.call += o || 0; else cell.put += o || 0;
      cell.vol += v || 0;
      if (iv > 0.01 && iv < 5) {
        const p = ivPts[ei].get(K) ?? {};
        p[t] = iv; ivPts[ei].set(K, p);
      }
      volume.set(`${e}|${K}|${t}`, { v: v || 0, mid: mid || 0, ei, K, t, iv });
    }

    this.expiries = expKeys.map((key) => ({ key, ts: expiryTs(new Date(key + 'T00:00:00Z')), kind: kindOf(key, todayKey) }));
    this.strikes = strikes;
    this.oi = oi;
    // Smile per expiry: OTM side is the most liquid (puts below spot, calls above).
    this.smiles = ivPts.map((m) => [...m.entries()]
      .map(([K, p]) => [K, K < S ? (p.P ?? p.C) : (p.C ?? p.P)])
      .filter(([, v]) => v != null)
      .sort((a, b) => a[0] - b[0]));

    // Typical strike spacing near spot, used for labels.
    const near = strikes.filter((k) => Math.abs(k - S) / S < 0.03);
    const diffs = near.slice(1).map((k, i) => +(k - near[i]).toFixed(2)).filter((x) => x > 0);
    if (diffs.length) {
      const counts = new Map(); diffs.forEach((x) => counts.set(x, (counts.get(x) ?? 0) + 1));
      this.cfg.step = [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
    }

    this.#flowFromVolume(volume, S);
  }

  // Option volume traded between two polls. Without a trade feed the aggressor side is unknown,
  // so this is traded premium and the delta notional of the volume, not signed buying pressure.
  #flowFromVolume(volume, S) {
    const prev = this.prevVolume;
    this.prevVolume = new Map([...volume].map(([k, x]) => [k, x.v]));
    if (!prev) return; // first poll: volume before the page opened is not attributable to a minute
    const now = Date.now();
    const minute = Math.floor(now / 60000) * 60;
    let agg = this.minuteFlow.get(minute);
    if (!agg) {
      agg = { time: minute, callBuy: 0, callSell: 0, putBuy: 0, putSell: 0, deltaNotional: 0 };
      this.minuteFlow.set(minute, agg);
      if (this.minuteFlow.size > 400) this.minuteFlow.delete(this.minuteFlow.keys().next().value);
    }
    for (const [key, x] of volume) {
      const dv = x.v - (prev.get(key) ?? x.v);
      if (dv <= 0) continue;
      const e = this.expiries[x.ei];
      if (!e) continue;
      const T = this.T(e, now);
      const iv = x.iv > 0 ? x.iv : this.iv(x.K, T);
      const g = greeks(S, x.K, T, iv);
      const delta = x.t === 'C' ? g.callDelta : g.putDelta;
      const premium = dv * x.mid * 100;
      agg.deltaNotional += dv * delta * 100 * S;
      if (x.t === 'C') agg.callBuy += premium; else agg.putBuy += premium;
      if (premium >= BIG_PREMIUM) {
        const trade = { ts: now, expiry: e.key, kind: e.kind, K: x.K, type: x.t, side: 'operado', size: dv, price: x.mid, premium, deltaNotional: dv * delta * 100 * S, iv };
        this.big.unshift(trade); if (this.big.length > 120) this.big.pop();
        this.flowListeners.forEach((f) => f(trade));
      }
    }
  }

  #applyCandles(d) {
    const rows = (d?.candles ?? []).map(([time, open, high, low, close]) => ({ time, open, high, low, close })).filter((c) => c.close > 0);
    if (!rows.length) return [];
    const lastKnown = this.candles.at(-1)?.time ?? -Infinity;
    const fresh = rows.filter((c) => c.time >= lastKnown);
    if (!this.candles.length) this.candles = rows;
    else for (const c of fresh) { if (c.time === lastKnown) this.candles[this.candles.length - 1] = c; else this.candles.push(c); }
    if (this.candles.length > 2000) this.candles.splice(0, this.candles.length - 2000);
    return fresh;
  }

  // IV at any strike and maturity: interpolate each expiry's smile in strike, then interpolate
  // total variance (iv² · T) between expiries. S is ignored (sticky-strike surface).
  iv(K, T) {
    const now = Date.now();
    const pts = [];
    this.expiries.forEach((e, i) => {
      const v = interp(this.smiles[i], K);
      if (v != null) pts.push([this.T(e, now), v]);
    });
    if (!pts.length) return 0.2;
    if (T <= pts[0][0]) return pts[0][1];
    if (T >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
    const w = interp(pts.map(([t, v]) => [t, v * v * t]), T);
    return Math.sqrt(Math.max(w, 1e-6) / T);
  }

  start() {
    if (this.timers) return;
    const emitLast = () => { const b = this.candles.at(-1); if (b) this.listeners.forEach((f) => f(b)); };
    const pollChain = async () => {
      try {
        const d = await getJSON(`${this.api}/chain?symbol=${encodeURIComponent(this.symbol)}`, { timeout: 25000 });
        this.#applyChain(d);
        this.error = null;
        // Reflect the latest spot in the current candle until the next candle refresh.
        const b = this.candles.at(-1);
        const minute = Math.floor(Date.now() / 60000) * 60;
        if (b && b.time === minute) { b.close = this.spot; b.high = Math.max(b.high, this.spot); b.low = Math.min(b.low, this.spot); }
        emitLast();
      } catch (e) { this.error = e.message; }
    };
    const pollCandles = async () => {
      try {
        const d = await getJSON(`${this.api}/candles?symbol=${encodeURIComponent(this.symbol)}`, { timeout: 25000 });
        for (const b of this.#applyCandles(d)) this.listeners.forEach((f) => f(b));
      } catch { /* keep the last candles */ }
    };
    this.timers = [setInterval(pollChain, CHAIN_EVERY), setInterval(pollCandles, CANDLES_EVERY)];
  }

  stop() { (this.timers ?? []).forEach(clearInterval); this.timers = null; }
}

export const ageText = (ms) => {
  const s = Math.round((Date.now() - ms) / 1000);
  return s < 90 ? `hace ${s} s` : `hace ${Math.round(s / 60)} min`;
};
