// Open Food Facts: free, open database of packaged products (many from Mexico), with barcodes.
// https://world.openfoodfacts.org — values are per 100 g (or 100 ml for drinks).

const FIELDS = 'code,product_name,product_name_es,brands,nutriments,serving_size,serving_quantity,quantity';
const BASE = 'https://world.openfoodfacts.org';

async function getJSON(url, timeout = 12000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctl.signal });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } finally { clearTimeout(t); }
}

function toFood(p) {
  const n = p.nutriments || {};
  let kcal = n['energy-kcal_100g'];
  if (kcal == null && n.energy_100g != null) kcal = n.energy_100g / 4.184; // kJ → kcal
  const name = (p.product_name_es || p.product_name || '').trim();
  if (kcal == null || !name) return null;
  const sq = +p.serving_quantity;
  return {
    id: 'off' + p.code,
    src: 'off',
    code: p.code,
    name,
    brand: (p.brands || '').split(',')[0].trim(),
    kcal: Math.round(+kcal),
    p: +(n.proteins_100g ?? 0),
    c: +(n.carbohydrates_100g ?? 0),
    f: +(n.fat_100g ?? 0),
    serving: sq > 0 ? { label: '1 porción' + (p.serving_size ? ` (${p.serving_size})` : ''), g: sq } : null,
  };
}

// The search endpoint is rate-limited (about 10 searches per minute) and sometimes overloaded,
// so: one request per search, one automatic retry, and results cached for the session.
const cache = new Map();
async function getWithRetry(url) {
  try { return await getJSON(url); } catch {
    await new Promise((r) => setTimeout(r, 1500));
    return getJSON(url);
  }
}

export async function searchProducts(q) {
  const key = q.trim().toLowerCase();
  if (cache.has(key)) return cache.get(key);
  const common = `search_terms=${encodeURIComponent(q)}&search_simple=1&action=process&json=1&page_size=24&sort_by=unique_scans_n&fields=${FIELDS}`;
  // Products sold in Mexico first; the worldwide database only when Mexico has none.
  const mx = await getWithRetry(`${BASE}/cgi/search.pl?${common}&tagtype_0=countries&tag_contains_0=contains&tag_0=mexico`);
  let list = (mx.products || []).map(toFood).filter(Boolean);
  if (!list.length) {
    const world = await getWithRetry(`${BASE}/cgi/search.pl?${common}`);
    list = (world.products || []).map(toFood).filter(Boolean);
  }
  list = list.slice(0, 24);
  cache.set(key, list);
  return list;
}

export async function byBarcode(code) {
  const d = await getJSON(`${BASE}/api/v2/product/${encodeURIComponent(code)}.json?fields=${FIELDS}`);
  if (d.status !== 1 || !d.product) return null;
  return toFood({ ...d.product, code: d.code || code });
}
