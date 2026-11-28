"""Portafolio Gap + ORB 8:30 CDMX (idea del video: estrategias descorrelacionadas). Desde 2021, en MES.
Gap: 4 MES (mitad de usd_8mes). ORB con retroceso 1:2: solo días con riesgo >= 4 puntos, 2 MES, costo 0.748 pts por MES.
Mide correlación diaria, caída y aprobación de Lucid 50K (objetivo +3,000, caída 2,000 que sigue al máximo hasta el saldo inicial)."""
import json
import numpy as np, pandas as pd

g = pd.DataFrame(json.load(open('dashboard/operaciones.json'))['rows'])
g = g.assign(fecha=pd.to_datetime(g.fecha), u=g.usd_8mes / 2).query('fecha >= "2021-01-01"').set_index('fecha').u
o = pd.DataFrame(json.load(open('dashboard_orb/orb_operaciones.json'))['rows'])
o = o[o.riesgo_pts >= 4].assign(fecha=lambda x: pd.to_datetime(x.fecha))
o = o.assign(u=2 * (o.pts - 0.748) * 5).set_index('fecha').u

def lucid(u, target=3000, dd=2000):
    res, n = [], []
    for s in range(len(u)):
        bal = pk = 0.0
        for k in range(s, len(u)):
            bal += u[k]; pk = max(pk, bal)
            if bal >= target: res.append(1); n.append(k - s + 1); break
            if bal <= min(pk - dd, 0): res.append(0); break
    return round(100 * np.mean(res)), int(np.median(n))

def caida(u):
    eq = np.cumsum(u); return round((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())

dias = pd.concat([g.rename("gap"), o.rename("orb")], axis=1, sort=True)
ambos = dias.dropna()
print('días con operación: Gap', g.size, 'ORB', o.size, 'ambos el mismo día', len(ambos))
print('correlación del resultado el mismo día', round(ambos.gap.corr(ambos.orb), 2))
m = dias.fillna(0).groupby(pd.Grouper(freq='ME')).sum()
print('correlación mensual', round(m.gap.corr(m.orb), 2))
for nombre, u in (('Gap 4 MES', dias.gap.fillna(0)), ('ORB 2 MES', dias.orb.fillna(0)), ('Gap 4 + ORB 2', dias.fillna(0).sum(axis=1))):
    u = u[u != 0].values
    pas, med = lucid(u)
    print(f'{nombre}: neto {round(u.sum())}, caída {caida(u)}, Lucid {pas}% en ~{med} días operados')
