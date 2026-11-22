// Picks the options data source per symbol: the real proxy when configured, else the simulator.
// If the proxy fails, the view falls back to the simulator and says why.

import { getSim } from '../sim/options.js';
import { RealOptions } from './real.js';
import { optionsApi } from '../config.js';

const real = new Map(); // symbol -> Promise<RealOptions>

export async function getEngine(symbol) {
  const api = optionsApi();
  if (!api) { const s = getSim(symbol); s.fallbackReason = null; return s; }
  const key = api + "|" + symbol;
  let p = real.get(key);
  if (!p) {
    const e = new RealOptions(symbol, api);
    p = e.ready.then(() => { e.start(); return e; });
    real.set(key, p);
    p.catch(() => real.delete(key)); // retry on the next visit
  }
  try {
    return await p;
  } catch (err) {
    const sim = getSim(symbol);
    sim.fallbackReason = err.message;
    return sim;
  }
}

export function sourceLabel(engine, symbol) {
  if (engine.source !== 'real') {
    return engine.fallbackReason
      ? [`Opciones ${symbol}: simulador (el proxy falló: ${engine.fallbackReason})`, 'err']
      : [`Opciones ${symbol}: simulador (Black-Scholes, OI sintético)`, 'sim'];
  }
  const name = { tradier: 'Tradier', polygon: 'Polygon' }[engine.provider] ?? engine.provider ?? 'proveedor';
  return [`Opciones ${symbol}: ${name}${engine.delayed ? ' (con retraso de 15 min)' : ''}`, 'live'];
}
