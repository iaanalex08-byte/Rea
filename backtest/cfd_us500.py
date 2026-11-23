"""Modelo B · Gap como CFD del US500: mismo precio de ES, costo = spread (+ deslizamiento en stops)."""
import json, os
import numpy as np, pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard')
o = pd.DataFrame(json.load(open(os.path.join(D, 'operaciones.json')))['rows'])
pts = o.ticks.values / 2 * 0.25          # resultado bruto en puntos por unidad (promedio de las dos mitades)
stop = o.salida.values == 'Stop'
yr = pd.to_datetime(o.fecha).dt.year.values
SL = 35 * 0.25                           # 8.75 puntos

def run(spread, slip):
    net = pts - spread - np.where(stop, slip, 0)   # puntos netos por unidad
    risk = SL + spread + slip                      # lo que pierdes en un stop
    R = net / risk
    def pf(r): l = -r[r < 0].sum(); return r[r > 0].sum() / l
    return R, {'pf': round(pf(R), 2), 'pf_is': round(pf(R[yr <= 2022]), 2), 'pf_oos': round(pf(R[yr >= 2023]), 2),
               'win': round(100 * (R > 0).mean(), 1), 'espR': round(R.mean(), 3)}

rows = []
rng = np.random.default_rng(11)
for spread in (0.3, 0.5, 0.7, 1.0, 1.5):
    for slip in (0.0, 0.5):
        R, s = run(spread, slip)
        sims = rng.choice(R, (10000, 57))
        out = {'spread': spread, 'desliz_stop': slip, **s}
        for f in (0.02, 0.05, 0.10):
            eq = 100 * np.cumprod(1 + f * sims, 1)
            out[f'{int(f*100)}%_tipico'] = round(float(np.median(eq[:, -1])))
            out[f'{int(f*100)}%_mitad'] = round(100 * float((eq.min(1) <= 50).mean()), 1)
        rows.append(out)
res = pd.DataFrame(rows)
print(res.to_string(index=False))
# referencia: futuros MES (costos 2.49 por MES)
Rm = o.usd_8mes.values / 369.92
print('MES referencia: PF', round(Rm[Rm > 0].sum() / -Rm[Rm < 0].sum(), 2), 'esperanza R', round(Rm.mean(), 3), 'win', round(100 * (Rm > 0).mean(), 1))
# spread de equilibrio
for s in np.arange(1.0, 4.01, 0.25):
    R, st = run(s, 0.5)
    if st['espR'] <= 0: print('El modelo deja de ganar con spread ≈', s, 'pts (con 0.5 de deslizamiento en stops)'); break
res.to_json(os.path.join(D, 'cfd_us500.json'), orient='records', force_ascii=False)
