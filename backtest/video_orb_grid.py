"""Modelo del video (ORB de la primera vela de 5 min, 9:30–9:35 NY, ratio invertido) en ES: búsqueda de objetivo y stop.
Entrada: orden stop 1 tick fuera del máximo o mínimo de la vela; la primera que se toque; se descarta si rompe ambos en la misma vela.
Vela de entrada: solo cuenta el stop (conservador). Stop primero si una vela toca ambos. Cierre 15:59 NY. Costos ES 1.36 ticks."""
import sys
import numpy as np, pandas as pd
import mas_dinero as M

T, COST = 0.25, 1.36
C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C)

def camino(m1, day):
    t0 = pd.Timestamp(day).tz_localize(M.NY) + pd.Timedelta(hours=9, minutes=30)
    r = m1[(m1.index >= t0) & (m1.index < t0 + pd.Timedelta(minutes=5))]
    if len(r) < 4: return None
    hi, lo = r.h.max() + T, r.l.min() - T
    b = m1[(m1.index >= t0 + pd.Timedelta(minutes=5)) & (m1.index < t0 + pd.Timedelta(hours=6, minutes=29))]
    H, L = b.h.values, b.l.values
    for i in range(len(b)):
        up, dn = H[i] >= hi, L[i] <= lo
        if up and dn: return None
        if up or dn:
            d, e = (1, hi) if up else (-1, lo)
            fav = ((H[i:] - e) if d > 0 else (e - L[i:])) / T
            adv = ((e - L[i:]) if d > 0 else (H[i:] - e)) / T
            fav[0] = -1e9
            return day, d, np.maximum.accumulate(fav), np.maximum.accumulate(adv), d * (b.c.values[-1] - e) / T, (r.h.max() - r.l.min()) / T
    return None

P = [x for x in (camino(C[c], d) for d, c in ch.items()) if x]
y = np.array([p[0].year for p in P]); rango = np.array([p[5] for p in P])

def res(p, tp, sl):
    _, _, cf, ca, last, _ = p; n = len(cf)
    it, isl = np.searchsorted(cf, tp), np.searchsorted(ca, sl)
    if isl <= it: return -sl if isl < n else last
    return tp if it < n else last

pf = lambda x: round(x[x > 0].sum() / -x[x < 0].sum(), 2) if (x < 0).any() else np.inf
rows = []
for tp in range(4, 41, 4):
    for sl in range(16, 241, 8):
        x = np.array([res(p, tp, sl) for p in P]) - COST
        rows.append({'tp_pts': tp / 4, 'sl_pts': sl / 4, 'ops': len(x), 'gana%': round(100 * (x > 0).mean(), 1), 'PF': pf(x),
                     'PF_2018-22': pf(x[y <= 2022]), 'PF_2023-26': pf(x[y >= 2023]), 'neto_1ES': round(x.sum() * 12.5)})
r = pd.DataFrame(rows); r.to_csv('video_orb_grid.csv', index=False)
pd.set_option('display.width', 200)
print('días operados', len(P))
print('mejores con winrate >= 80 %'); print(r[r['gana%'] >= 80].sort_values('PF', ascending=False).head(8).to_string(index=False))
print('cuántas combinaciones ganan (PF > 1) con winrate >= 80 %:', ((r['gana%'] >= 80) & (r.PF > 1)).sum(), 'de', (r['gana%'] >= 80).sum())

def rachas(x):
    w = l = bw = bl = 0; lu = peor = 0.0; corridas = []
    for v in x:
        if v > 0:
            if l: corridas.append(('P', l))
            w, l, lu = w + 1, 0, 0.0
        else:
            if w: corridas.append(('G', w))
            l, w = l + 1, 0; lu += v
            if l > bl or (l == bl and lu < peor): peor = lu
        bw, bl = max(bw, w), max(bl, l)
    corridas.append(('G', w) if w else ('P', l))
    return bw, bl, peor, corridas

print('\nRachas (después de costos de ES)')
for tp, sl, nombre in ((8, 43, 'Proporción del Dow 2 / 10.75'), (16, 80, '4 / 20'), (20, 168, '5 / 42 (mejor con 80 % o más)'), (40, 184, '10 / 46 (mejor de todas)')):
    x = np.array([res(p, tp, sl) for p in P]) - COST
    bw, bl, peor, cor = rachas(x)
    perd = [n for k, n in cor if k == 'P']; gan = [n for k, n in cor if k == 'G']
    print(f'{nombre}: gana {round(100 * (x > 0).mean(), 1)} %, mejor racha ganadora {bw}, peor racha perdedora {bl} '
          f'({round(peor * 12.5)} con 1 ES), racha ganadora media {round(np.mean(gan), 1)}, '
          f'rachas de 2+ perdedoras {sum(n >= 2 for n in perd)}, de 3+ {sum(n >= 3 for n in perd)}')
    print('   por año (mejor ganadora / peor perdedora):', {int(k): rachas(x[y == k])[:2] for k in np.unique(y)})
