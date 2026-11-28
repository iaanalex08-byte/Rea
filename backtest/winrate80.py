"""Modelo B · Gap con bracket invertido (TP corto, SL amplio) para buscar winrate de 80 % o más.
Misma señal del Gap (10:12 NY, todos los filtros); un solo objetivo, sin break-even, cierre 15:59.
Costos: ES 1 tick + $4.50 (1.36 ticks); MES 1 tick + $2.49. Ambigüedad: stop primero.
Uso: python3 backtest/winrate80.py backtest/datos"""
import sys
import numpy as np, pandas as pd
import mas_dinero as M, optimizar as O

ES_COST_T = 1.36

def resultado(pt, tp, sl):
    cf, ca, _, last = pt; n = len(cf)
    it, isl = np.searchsorted(cf, tp), np.searchsorted(ca, sl)
    if isl <= it: return -sl if isl < n else last
    return tp if it < n else last

def pf(x): return x[x > 0].sum() / -x[x < 0].sum()

def lucid(u, target=3000, dd=2000):
    res = []
    for s in range(len(u)):
        bal = pk = 0.0
        for k in range(s, len(u)):
            bal += u[k]; pk = max(pk, bal)
            if bal >= target: res.append(1); break
            if bal <= min(pk - dd, 0): res.append(0); break
    return round(100 * np.mean(res)) if res else None

if __name__ == '__main__':
    C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos')
    P = M.prepare(C); p = M.MODELO_GAP
    _, sig = M.run(P, M.choose_contracts(C), p)
    keep = (sig.A & sig.C & sig.BOS & sig.VWAP & sig.GAP).values
    sig = sig[keep].reset_index(drop=True); pth = O.paths(P, sig, p)
    y = pd.to_datetime(sig.fecha).dt.year.values
    rows = []
    for tp in range(4, 61, 4):
        for sl in range(16, 241, 8):
            t = np.array([resultado(x, tp, sl) for x in pth], float) - ES_COST_T
            u = t * 12.5
            rows.append({'tp_ticks': tp, 'sl_ticks': sl, 'ops': len(t), 'gana%': round(100 * (t > 0).mean(), 1),
                         'PF': round(pf(t), 2), 'PF_2018-22': round(pf(t[y <= 2022]), 2), 'PF_2023-26': round(pf(t[y >= 2023]), 2),
                         'neto_1ES': round(u.sum()), 'lucid_1ES%': lucid(u) if tp in (12, 20) and sl == 80 else None})
    r = pd.DataFrame(rows); r.to_csv('winrate80.csv', index=False)
    print(r[r['gana%'] >= 80].sort_values('PF', ascending=False).head(15).to_string(index=False))
