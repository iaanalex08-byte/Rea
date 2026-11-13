"""Corre las variantes de los dos modelos en ES 1 min y 5 min. Uso: python3 run.py carpeta_con_es_1m.pkl_y_es_5m.pkl"""
import sys, json
import pandas as pd
from engine import run, stats

import glob


def load_histdata(folder):
    fs = sorted(glob.glob(folder + '/DAT_ASCII_SPXUSD_M1_*.csv'))
    df = pd.concat([pd.read_csv(f, sep=';', header=None, names=['ts', 'o', 'h', 'l', 'c', 'v']) for f in fs])
    t = pd.to_datetime(df.ts, format='%Y%m%d %H%M%S') + pd.Timedelta(hours=5)  # EST fijo -> UTC
    df.index = t.dt.tz_localize('UTC')
    df = df[['o', 'h', 'l', 'c', 'v']].sort_index()
    return df[~df.index.duplicated()]


def resample(df, m):
    return df.resample(f'{m}min').agg({'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}).dropna()


folder, src = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'es')
if src == 'es':
    data = {1: pd.read_pickle(f'{folder}/es_1m.pkl'), 5: pd.read_pickle(f'{folder}/es_5m.pkl')}
else:
    m1 = load_histdata(folder)
    data = {1: m1, 5: resample(m1, 5)}
V = [
    ('M1 · balance inicial · objetivo extensión', dict(model=1, balance='ib', target='mm')),
    ('M1 · balance inicial · objetivo 2R', dict(model=1, balance='ib', target='r2')),
    ('M1 · balance inicial · sin gatillo', dict(model=1, balance='ib', target='mm', trigger=False)),
    ('M1 · área de valor previa · objetivo extensión', dict(model=1, balance='prev', target='mm')),
    ('M1 · área de valor previa · objetivo 2R', dict(model=1, balance='prev', target='r2')),
    ('M2 · área de valor · objetivo POC', dict(model=2, target='poc')),
    ('M2 · área de valor · objetivo extremo opuesto', dict(model=2, target='opp')),
    ('M2 · área de valor · sin gatillo', dict(model=2, target='poc', trigger=False)),
    ('M2 · rango previo (extremos) · objetivo POC', dict(model=2, target='poc', rng_ref='hl')),
    ('M2 · rango previo (extremos) · extremo opuesto', dict(model=2, target='opp', rng_ref='hl')),
]
rows, trades = [], []
for tf in (5, 1):
    for name, kw in V:
        T = run(data[tf], tf, **kw)
        s = stats(T)
        rows.append(dict(tf=tf, variant=name, **s))
        print(f"{tf}m {name:48s} ops {s['n']:3d}  win {s['wr']*100:5.1f}%  PF {s['pf']:.2f}  R {s['R']:+.2f}  neto {s['net']:+9,.0f}  DD {s['mdd']:+8,.0f}")
        if len(T):
            T['tf'] = tf; T['variant'] = name; trades.append(T)
pd.DataFrame(rows).to_csv(f'resumen_{src}.csv', index=False)
pd.concat(trades).to_csv(f'operaciones_{src}.csv', index=False)
