"""Prueba los patrones de la presentación como filtros del Modelo B · Gap, con 2018–2022 / 2023–2026."""
import sys
import numpy as np, pandas as pd
import mas_dinero as M

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C); prep = M.prepare(C)
t, _ = M.run(prep, ch, M.MODELO_GAP)
t = t[pd.to_datetime(t.fecha).dt.year >= 2018].reset_index(drop=True)
t['f'] = pd.to_datetime(t.fecha); t['u'] = 4 * t.ticks * 1.25 - 8 * 2.49
def prev_range(c, f):
    P = prep[c]['days']; d = max(x for x in P if x < f.date() and len(P[x]) >= 300); return P[d].h.max() - P[d].l.min()
t['vol'] = [prev_range(c, f) for c, f in zip(t.contrato, t.f)]
IS = t.f.dt.year <= 2022
# cortes de volatilidad medidos solo con 2018–2022
q1, q2 = t.loc[IS, 'vol'].quantile([1/3, 2/3])
# volatilidad relativa: rango de ayer contra el promedio de 20 días (no depende del nivel del mercado)
def rel(c, f):
    P = prep[c]['days']; ds = sorted(x for x in P if x < f.date() and len(P[x]) >= 300)[-20:]
    r = [P[x].h.max() - P[x].l.min() for x in ds]; return r[-1] / np.mean(r)
t['vrel'] = [rel(c, f) for c, f in zip(t.contrato, t.f)]
r1, r2 = t.loc[IS, 'vrel'].quantile([1/3, 2/3])

def st(g):
    u = g.u.values; l = -u[u < 0].sum()
    return len(u), round(100 * (u > 0).mean(), 1), round(u[u > 0].sum() / l, 2) if l else np.inf, round(u.sum())
filtros = {
    'Base (sin filtro nuevo)': np.ones(len(t), bool),
    'Sin febrero ni marzo': ~t.f.dt.month.isin([2, 3]),
    'Sin jueves': t.f.dt.dayofweek != 3,
    'Solo gap leve en contra (0 a −8)': t.gap.between(-8, 0),
    'Sin gap a favor 0 a +8': ~t.gap.between(0, 8, inclusive='right'),
    f'Sin "ayer normal" (rango {q1:.0f}–{q2:.0f} pts)': ~t.vol.between(q1, q2),
    f'Solo ayer volátil (> {q2:.0f} pts)': t.vol > q2,
    'Sin "ayer normal" relativo (vs 20 días)': ~t.vrel.between(r1, r2),
    'Solo ayer volátil relativo': t.vrel > r2,
    'Solo octubre a diciembre': t.f.dt.month >= 10,
}
rows = []
for k, m in filtros.items():
    a, b = st(t[m & IS]), st(t[m & ~IS])
    rows.append({'filtro': k, 'IS_ops': a[0], 'IS_win': a[1], 'IS_pf': a[2], 'IS_neto': a[3], 'OOS_ops': b[0], 'OOS_win': b[1], 'OOS_pf': b[2], 'OOS_neto': b[3]})
print(pd.DataFrame(rows).to_string(index=False))
# por año del patrón de volatilidad y de meses
for k in ('Sin febrero ni marzo', 'Sin jueves'):
    m = filtros[k]; base = t.groupby(t.f.dt.year).u.sum(); con = t[m].groupby(t[m].f.dt.year).u.sum()
    print(k, 'años en que mejora:', int((con > base).sum()), 'de 9')

def lucid(u, target=3000, dd=2000):
    res = []
    for s in range(len(u)):
        bal = pk = 0.0
        for k in range(s, len(u)):
            bal += u[k]; pk = max(pk, bal)
            if bal >= target: res.append((1, k - s + 1)); break
            if bal <= min(pk - dd, 0): res.append((0, k - s + 1)); break
    r = np.array(res); return round(100 * r[:, 0].mean(), 1), int(np.median(r[r[:, 0] == 1, 1]))
print()
for k in ('Base (sin filtro nuevo)', 'Sin febrero ni marzo'):
    g = t[filtros[k]]; u8 = g.u.values; eq = np.cumsum(u8)
    dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    u6 = u8 / 8 * 6 + 0  # mismo costo proporcional
    print(f'{k}: ops {len(g)}  neto {u8.sum():,.0f}  caída 8 MES {dd:,.0f}  Lucid 6 MES {lucid(u6)}  Lucid 8 MES {lucid(u8)}  ops/año {len(g)/8.9:.0f}')
