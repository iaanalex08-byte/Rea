"""Variantes del ORB con retroceso, con costos: 1 tick de deslizamiento + 4.50 USD de comisión por contrato ES."""
import sys
from dataclasses import replace
import numpy as np, pandas as pd
import mas_dinero as M, orb as O

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C)
prep = {k: {'m1': df} for k, df in C.items()}
COST_PTS = 0.25 + 4.5 / 50      # por contrato ES, ida y vuelta, en puntos

def neto(t):
    o = t[t.estado == 'Operada'].copy()
    o['Rn'] = (o.pts - COST_PTS) / o.riesgo_pts
    return o

def fila(nombre, p, min_pts=0):
    t = O.correr(prep, ch, p)
    o = neto(t); o = o[o.riesgo_pts >= min_pts]
    R = o.Rn.values; y = pd.to_datetime(o.fecha).dt.year.values
    def pf(r): l = -r[r < 0].sum(); return round(r[r > 0].sum() / l, 2) if l else np.inf
    eq = np.cumsum(R); dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    return {'variante': nombre, 'ops': len(R), 'win%': round(100 * (R > 0).mean(), 1), 'PF': pf(R),
            '2021-23': pf(R[y <= 2023]), '2024-26': pf(R[y >= 2024]), 'espR': round(R.mean(), 3), 'netoR': round(R.sum(), 1),
            'caidaR': round(dd, 1), 'stop_med_pts': round(float(np.median(o.riesgo_pts)), 2), 'anios+': int(sum(R[y == a].sum() > 0 for a in range(2021, 2027)))}

base = O.ORB()
rows = [fila('Base 1:2 (sin costos para comparar)', base)]
rows[0].update({'variante': 'Base 1:2 · con costos'})
for mp in (1, 2, 3, 4, 5):
    rows.append(fila(f'1:2 · stop mínimo {mp} pts', base, mp))
for rr in (1.0, 1.5, 3.0):
    rows.append(fila(f'1:{rr:g} · stop mínimo 2 pts', replace(base, rr=rr), 2))
rows.append(fila('1:2 · hora fija 8:30 CDMX · stop ≥2', replace(base, inicio='08:30', tz='America/Mexico_City'), 2))
rows.append(fila('1:2 · rango 15 min (9:30–9:45) · stop ≥2', replace(base, rango_min=15), 2))
rows.append(fila('1:2 · entrar solo hasta 10:30 · stop ≥2', replace(base, limite='10:30'), 2))
print(pd.DataFrame(rows).to_string(index=False))

print()
cdmx = replace(base, inicio='08:30', tz='America/Mexico_City')
rows = [fila('8:30 CDMX · 1:2 · sin stop mínimo (tu regla)', cdmx, 0),
        fila('8:30 CDMX · 1:2 · stop ≥1', cdmx, 1),
        fila('8:30 CDMX · 1:2 · stop ≥2', cdmx, 2),
        fila('8:30 CDMX · 1:2 · stop ≥3', cdmx, 3),
        fila('8:30 CDMX · 1:1.5 · stop ≥2', replace(cdmx, rr=1.5), 2),
        fila('8:30 CDMX · 1:3 · stop ≥2', replace(cdmx, rr=3.0), 2),
        fila('10:30 NY todo el año · 1:2 · stop ≥2', replace(base, inicio='10:30'), 2)]
print(pd.DataFrame(rows).to_string(index=False))
# 8:30 CDMX separado por invierno (9:30 NY) y verano (10:30 NY)
t = O.correr(prep, ch, cdmx); o = neto(t); o = o[o.riesgo_pts >= 2]
o['hora_ny'] = [ '9:30 NY (invierno)' if pd.Timestamp(f).tz_localize('America/Mexico_City').replace(hour=8, minute=30).tz_convert(M.NY).hour == 9 else '10:30 NY (verano)' for f in o.fecha]
for k, g in o.groupby('hora_ny'):
    R = g.Rn.values; print(k, len(R), 'win', round(100 * (R > 0).mean(), 1), 'PF', round(R[R > 0].sum() / -R[R < 0].sum(), 2), 'espR', round(R.mean(), 3))
