"""Calcula superficies de parámetros del Modelo B · Gap para la gráfica 3D: escribe dashboard/superficie.json."""
import json, os, sys
import numpy as np, pandas as pd
import mas_dinero as M, optimizar as O

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C); prep = M.prepare(C)
p = M.MODELO_GAP
_, sig = M.run(prep, ch, p)
keep = (pd.to_datetime(sig.fecha).dt.year >= 2018).values
sig = sig[keep].reset_index(drop=True)
pth = O.paths(prep, sig, p)
yr = pd.to_datetime(sig.fecha).dt.year.values
base = (sig.A & sig.C & sig.BOS & sig.VWAP).values

def metr(mask, sl, t1, t2):
    idx = np.nonzero(mask)[0]
    tk = np.array([O.bracket(pth[i], sl, t1, t2, True)[0] for i in idx], float)
    u = 4 * tk * 1.25 - 8 * 2.49; y = yr[idx]
    def pf(v): l = -v[v < 0].sum(); return round(float(v[v > 0].sum() / l), 3) if l else None
    return {'pf': pf(u), 'pf_is': pf(u[y <= 2022]), 'pf_oos': pf(u[y >= 2023]), 'neto': round(float(u.sum())), 'ops': int(len(u))}

out = {'meta': 'Modelo B · Gap, 2018–2026, 8 MES con costos. Break-even tras TP1. Se marca el modelo elegido.'}
gapm = base & (sig.gap > -8).values
sls = list(range(20, 55, 5)); t1s = list(range(20, 55, 5))
out['sl_tp1'] = {'x': t1s, 'y': sls, 'tp2': 120, 'z': [[metr(gapm, sl, t1, 120) for t1 in t1s] for sl in sls]}
ths = [2, 4, 6, 8, 10, 12, 14, 16, 20, 25, 30]
out['gap_sl'] = {'x': ths, 'y': sls, 'tp1': 35, 'tp2': 120, 'z': [[metr(base & (sig.gap > -th).values, sl, 35, 120) for th in ths] for sl in sls]}
t2s = [60, 80, 100, 120, 140, 160, 200, 240]
out['tp1_tp2'] = {'x': t2s, 'y': t1s, 'sl': 35, 'z': [[metr(gapm, 35, t1, t2) for t2 in t2s] for t1 in t1s]}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard', 'superficie.json'), 'w'), ensure_ascii=False)
for k in ('sl_tp1', 'gap_sl', 'tp1_tp2'):
    g = out[k]; print(k, 'x', g['x'], 'y', g['y'])
    for yv, row in zip(g['y'], g['z']): print(' ', yv, [r['pf'] for r in row])
