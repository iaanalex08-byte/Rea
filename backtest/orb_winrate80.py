"""ORB con retroceso de 8:30–8:35 CDMX (la estrategia del usuario) con brackets de winrate alto.
Misma entrada que orb.py (rango 8:30–8:35 hora fija de CDMX, ruptura por cierre, retroceso, entrada al recruzar el nivel).
Se cambia solo la salida: objetivo corto y stop amplio en ticks fijos, o el stop del retroceso con objetivo < 1R.
Costos ES: 1 tick + $4.50 = 1.36 ticks. Vela de entrada: solo stop; stop primero si una vela toca ambos."""
import sys
import numpy as np, pandas as pd
import mas_dinero as M
from orb import ORB, correr

COST = 1.36
C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C)
prep = {k: {'m1': df} for k, df in C.items()}
t = correr(prep, ch, ORB(inicio='08:30', tz='America/Mexico_City'), desde=2018)
o = t[t.estado == 'Operada'].reset_index(drop=True)
day_contract = ch.to_dict()

paths = []
for r in o.to_dict('records'):
    m1 = prep[day_contract[r['fecha']]]['m1']
    end = pd.Timestamp(r['fecha']).tz_localize(M.NY) + pd.Timedelta(hours=15, minutes=59)
    b = m1[(m1.index >= r['hora_entrada']) & (m1.index < end)]
    d, e = r['dir'], r['entrada']
    fav = (b.h.values - e) / .25 if d > 0 else (e - b.l.values) / .25
    adv = (e - b.l.values) / .25 if d > 0 else (b.h.values - e) / .25
    fav[0] = -1e9                                   # en la vela de entrada solo cuenta el stop
    last = d * (b.c.values[-1] - e) / .25
    paths.append((np.maximum.accumulate(fav), np.maximum.accumulate(adv), last, r['riesgo_pts'] / .25))

def res(p, tp, sl):
    cf, ca, last, _ = p; n = len(cf)
    it, isl = np.searchsorted(cf, tp), np.searchsorted(ca, sl)
    if isl <= it: return -sl if isl < n else last
    return tp if it < n else last

y = pd.to_datetime(o.fecha).dt.year.values
pf = lambda x: round(x[x > 0].sum() / -x[x < 0].sum(), 2)
rows = []
for tp in range(4, 41, 4):
    for sl in range(16, 201, 8):
        x = np.array([res(p, tp, sl) for p in paths]) - COST
        rows.append({'salida': f'fijo {tp}/{sl} ticks', 'ops': len(x), 'gana%': round(100 * (x > 0).mean(), 1), 'PF': pf(x),
                     'PF_2018-22': pf(x[y <= 2022]), 'PF_2023-26': pf(x[y >= 2023]), 'PF_2021-26': pf(x[y >= 2021]),
                     'gana%_2021-26': round(100 * (x[y >= 2021] > 0).mean(), 1), 'neto_1ES': round(x.sum() * 12.5)})
for rr in (0.2, 0.3, 0.5):
    x = np.array([res(p, max(1, round(rr * p[3])), p[3]) for p in paths]) - COST
    rows.append({'salida': f'stop del retroceso, objetivo {rr}R', 'ops': len(x), 'gana%': round(100 * (x > 0).mean(), 1), 'PF': pf(x),
                 'PF_2018-22': pf(x[y <= 2022]), 'PF_2023-26': pf(x[y >= 2023]), 'PF_2021-26': pf(x[y >= 2021]),
                 'gana%_2021-26': round(100 * (x[y >= 2021] > 0).mean(), 1), 'neto_1ES': round(x.sum() * 12.5)})
r = pd.DataFrame(rows); r.to_csv('orb_winrate80.csv', index=False)
pd.set_option('display.width', 220)
print(r[r['gana%'] >= 80].sort_values('PF', ascending=False).head(10).to_string(index=False))
print(r[r.salida.str.startswith('stop')].to_string(index=False))

def lucid(u, target=3000, dd=2000):
    out = []
    for s in range(len(u)):
        bal = pk = 0.0
        for k in range(s, len(u)):
            bal += u[k]; pk = max(pk, bal)
            if bal >= target: out.append(1); break
            if bal <= min(pk - dd, 0): out.append(0); break
    return round(100 * np.mean(out)) if out else None

for tp, sl in ((20, 168), (20, 104)):
    x = np.array([res(p, tp, sl) for p in paths])
    w = l = bw = bl = 0
    for v in x - COST:
        w, l = (w + 1, 0) if v > 0 else (0, l + 1); bw, bl = max(bw, w), max(bl, l)
    print(f'{tp}/{sl}: racha ganadora {bw}, perdedora {bl}; por año gana%',
          {int(k): round(100 * ((x - COST)[y == k] > 0).mean()) for k in np.unique(y)})
    for n in (1, 2, 3, 4):
        u = n * ((x - 1) * 1.25 - 2.49)
        print(f'   {n} MES: neto {round(u.sum())}, stop vale {round(n * ((sl + 1) * 1.25 + 2.49))}, Lucid {lucid(u)}%')
    u = (x - COST) * 12.5
    print(f'   1 ES: neto {round(u.sum())}, Lucid {lucid(u)}%')
