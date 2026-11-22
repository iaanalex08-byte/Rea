#!/usr/bin/env node
// Downloads recent SEC Form 4 filings (insider transactions) and, when a Quiver Quantitative
// key is configured, recent congressional trades. Writes terminal/data/insiders.json and
// terminal/data/congress.json for the static terminal to read.
//
// Usage (GitHub Actions or locally, Node 20+):
//   SEC_USER_AGENT="ORBE Terminal tu-correo@dominio.com" node terminal/tools/fetch-insiders.mjs
//   QUIVER_API_KEY=... (optional) enables the congress dataset.
//
// SEC fair-access policy: identify yourself with a contact email in the User-Agent and stay
// under 10 requests per second. https://www.sec.gov/os/accessing-edgar-data

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DATA = join(dirname(fileURLToPath(import.meta.url)), '..', 'data');
const UA = process.env.SEC_USER_AGENT;
const MAX_FILINGS = +(process.env.MAX_FILINGS || 120);
const KEEP_DAYS = 45;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(url, headers = {}) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate', ...headers } });
    if (r.ok) return r.text();
    if (r.status === 429 || r.status >= 500) { await sleep(1500 * (attempt + 1)); continue; }
    throw new Error(`HTTP ${r.status} ${url}`);
  }
  throw new Error(`Retries exhausted ${url}`);
}

// ---------- minimal XML helpers (Form 4 documents are small and regular) ----------
const tag = (xml, name) => {
  const m = xml.match(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`));
  if (!m) return null;
  const v = m[1].match(/<value>([\s\S]*?)<\/value>/);
  return decode(v ? v[1] : m[1]).trim() || null;
};
const blocks = (xml, name) => [...xml.matchAll(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`, 'g'))].map((m) => m[1]);
const decode = (s) => s.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'");
const numOrNull = (s) => (s == null || s === '' || Number.isNaN(+s) ? null : +s);

export function parseForm4(xml) {
  const issuer = { name: tag(xml, 'issuerName'), ticker: (tag(xml, 'issuerTradingSymbol') || '').toUpperCase() || null, cik: tag(xml, 'issuerCik') };
  const owners = blocks(xml, 'reportingOwner').map((o) => {
    const rel = blocks(o, 'reportingOwnerRelationship')[0] || '';
    const flag = (n) => /^(1|true)$/i.test(tag(rel, n) || '');
    const roles = [];
    if (flag('isDirector')) roles.push('Consejero');
    if (flag('isOfficer')) roles.push(tag(rel, 'officerTitle') || 'Directivo');
    if (flag('isTenPercentOwner')) roles.push('Accionista 10%');
    if (flag('isOther')) roles.push(tag(rel, 'otherText') || 'Otro');
    return { name: tag(o, 'rptOwnerName'), roles };
  });
  const tx = blocks(xml, 'nonDerivativeTransaction').map((t) => {
    const amounts = blocks(t, 'transactionAmounts')[0] || '';
    const post = blocks(t, 'postTransactionAmounts')[0] || '';
    const shares = numOrNull(tag(amounts, 'transactionShares'));
    const price = numOrNull(tag(amounts, 'transactionPricePerShare'));
    return {
      date: tag(t, 'transactionDate'),
      code: tag(blocks(t, 'transactionCoding')[0] || '', 'transactionCode'),
      acquired: tag(amounts, 'transactionAcquiredDisposedCode') === 'A',
      shares, price,
      value: shares != null && price != null ? Math.round(shares * price) : null,
      after: numOrNull(tag(post, 'sharesOwnedFollowingTransaction')),
      security: tag(t, 'securityTitle'),
    };
  });
  return { issuer, owners, tx };
}

async function recentForm4Index() {
  // EDGAR "latest filings" Atom feed; each filing appears once per party (issuer & owner).
  const out = new Map();
  for (let start = 0; start < MAX_FILINGS * 2 && out.size < MAX_FILINGS; start += 100) {
    const atom = await get(`https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&start=${start}&count=100&output=atom`);
    for (const entry of blocks(atom, 'entry')) {
      const href = (entry.match(/<link[^>]*href="([^"]+)"/) || [])[1];
      const acc = (href || '').match(/(\d{10}-\d{2}-\d{6})/)?.[1];
      const title = tag(entry, 'title') || '';
      if (!href || !acc || !/^4\b/.test(title)) continue;
      if (!out.has(acc)) out.set(acc, { acc, index: href.replace(/^http:/, 'https:'), updated: tag(entry, 'updated') });
    }
    await sleep(200);
  }
  return [...out.values()].slice(0, MAX_FILINGS);
}

async function fetchInsiders() {
  const prev = JSON.parse(await readFile(join(DATA, 'insiders.json'), 'utf8').catch(() => '{"rows":[]}'));
  const known = new Set(prev.rows.map((r) => r.acc));
  const filings = (await recentForm4Index()).filter((f) => !known.has(f.acc));
  console.log(`Form 4: ${filings.length} filings nuevos`);
  const rows = [];
  for (const f of filings) {
    try {
      const folder = f.index.replace(/\/[^/]+$/, '/');
      const listing = JSON.parse(await get(folder + 'index.json'));
      const doc = listing.directory.item.map((i) => i.name).find((n) => /\.xml$/i.test(n) && !/^R\d+|FilingSummary/i.test(n));
      if (!doc) continue;
      const xml = await get(folder + doc);
      const { issuer, owners, tx } = parseForm4(xml);
      for (const t of tx) {
        if (!['P', 'S'].includes(t.code)) continue; // open-market buys and sells only
        rows.push({ acc: f.acc, filed: f.updated?.slice(0, 10), url: f.index, ticker: issuer.ticker, company: issuer.name, insider: owners.map((o) => o.name).join('; '), roles: [...new Set(owners.flatMap((o) => o.roles))].join(', '), ...t });
      }
    } catch (e) {
      console.warn(f.acc, e.message);
    }
    await sleep(150); // ~6 req/s including the index request
  }
  const cutoff = new Date(Date.now() - KEEP_DAYS * 864e5).toISOString().slice(0, 10);
  const merged = [...rows, ...prev.rows].filter((r) => (r.filed || r.date || '') >= cutoff).slice(0, 2000);
  await writeFile(join(DATA, 'insiders.json'), JSON.stringify({ updated: new Date().toISOString(), source: 'SEC EDGAR Form 4', rows: merged }));
  console.log(`insiders.json: ${merged.length} transacciones (${rows.length} nuevas)`);
}

async function fetchCongress() {
  const key = process.env.QUIVER_API_KEY;
  if (!key) {
    await writeFile(join(DATA, 'congress.json'), JSON.stringify({ updated: new Date().toISOString(), configured: false, rows: [] }));
    console.log('congress.json: sin QUIVER_API_KEY, se omite');
    return;
  }
  const r = await fetch('https://api.quiverquant.com/beta/live/congresstrading', { headers: { Authorization: `Bearer ${key}`, Accept: 'application/json' } });
  if (!r.ok) throw new Error(`Quiver HTTP ${r.status}`);
  const d = await r.json();
  const rows = d.slice(0, 1500).map((x) => ({
    member: x.Representative, chamber: x.House, party: x.Party, ticker: x.Ticker,
    type: x.Transaction, range: x.Range, amount: x.Amount ?? null, traded: x.TransactionDate, reported: x.ReportDate,
  }));
  await writeFile(join(DATA, 'congress.json'), JSON.stringify({ updated: new Date().toISOString(), configured: true, source: 'Quiver Quantitative', rows }));
  console.log(`congress.json: ${rows.length} operaciones`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await mkdir(DATA, { recursive: true });
  let failed = false;
  if (!UA || !/@/.test(UA)) {
    // Not configured yet: skip quietly so the scheduled job stays green.
    console.warn('Falta SEC_USER_AGENT con un correo de contacto, p. ej. "ORBE Terminal tu-correo@dominio.com". Se omiten los insiders.');
  } else {
    try { await fetchInsiders(); } catch (e) { console.error('Insiders:', e.message); failed = true; }
  }
  try { await fetchCongress(); } catch (e) { console.error('Congreso:', e.message); failed = true; }
  process.exitCode = failed ? 1 : 0;
}
