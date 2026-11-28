"""Genera los JSON del dashboard del ORB con retroceso (8:30 CDMX, 1:2) en ES 2021–2026."""
import json, os, sys
from dataclasses import replace
import pandas as pd
import mas_dinero as M, orb as O

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard_orb'); os.makedirs(OUT, exist_ok=True)
C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C)
prep = {k: {'m1': df} for k, df in C.items()}
DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
meta = [{'label': 'Origen', 'value': 'ES de 1 minuto de NinjaTrader, contrato con más volumen cada día, ene 2021 – 20 nov 2026'},
        {'label': 'Script', 'value': 'backtest/orb.py y backtest/orb_dashboard.py'}]

p = replace(O.ORB(), inicio='08:30', tz='America/Mexico_City')
t = O.correr(prep, ch, p)
o = t[t.estado == 'Operada']
rows = []
for r in o.itertuples():
    f = pd.Timestamp(r.fecha)
    rows.append({'fecha': f.strftime('%Y-%m-%d'), 'anio': str(f.year), 'mes': f.strftime('%Y-%m'), 'dia': DIAS[f.dayofweek],
                 'direccion': 'Compra' if r.dir > 0 else 'Venta',
                 'rango_ny': '9:30 NY (invierno)' if r.hora_entrada.tz_convert(M.NY).normalize().tz_localize(None) is not None and
                             pd.Timestamp(f).tz_localize('America/Mexico_City').replace(hour=8, minute=30).tz_convert(M.NY).hour == 9 else '10:30 NY (verano)',
                 'hora_entrada_cdmx': r.hora_entrada.tz_convert('America/Mexico_City').strftime('%H:%M'),
                 'riesgo_pts': round(float(r.riesgo_pts), 2), 'salida': r.salida, 'R_bruto': round(float(r.R), 4), 'pts': round(float(r.pts), 4)})
json.dump({'rows': rows, 'meta': meta + [{'label': 'Reglas', 'value': 'Rango 8:30–8:35 CDMX, ruptura por cierre de 1 min, retroceso al nivel roto, entrada al volver a cruzarlo, stop en el extremo del retroceso, objetivo 2R, cierre 15:59 NY, sin costos (la página los resta).'}]},
          open(os.path.join(OUT, 'orb_operaciones.json'), 'w'), ensure_ascii=False)

est = t.estado.value_counts()
orden = ['Operada', 'Riesgo muy chico', 'Tocó el otro lado', 'Sin retroceso / entrada', 'Sin ruptura']
json.dump({'rows': [{'estado': k, 'dias': int(est.get(k, 0))} for k in orden], 'meta': meta},
          open(os.path.join(OUT, 'orb_estados.json'), 'w'), ensure_ascii=False)

COST = 0.25 + 4.5 / 50
def fila(nombre, q, mp):
    tt = O.correr(prep, ch, q); g = tt[(tt.estado == 'Operada') & (tt.riesgo_pts >= mp)]
    R = ((g.pts - COST) / g.riesgo_pts).values; y = pd.to_datetime(g.fecha).dt.year.values
    pf = lambda r: round(float(r[r > 0].sum() / -r[r < 0].sum()), 2)
    import numpy as np
    eq = np.cumsum(R); dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    return {'variante': nombre, 'ops': int(len(R)), 'ganadoras': round(100 * float((R > 0).mean()), 1), 'pf': pf(R),
            'pf_2021_2023': pf(R[y <= 2023]), 'pf_2024_2026': pf(R[y >= 2024]), 'esperanza_r': round(float(R.mean()), 3),
            'neto_r': round(float(R.sum()), 1), 'caida_r': round(float(dd), 1)}
base = O.ORB()
var = [fila('8:30 CDMX · 1:2 · stop ≥ 2 pts (recomendada)', p, 2),
       fila('8:30 CDMX · 1:2 · sin stop mínimo (tal cual)', p, 0),
       fila('8:30 CDMX · 1:3 · stop ≥ 2 pts', replace(p, rr=3.0), 2),
       fila('8:30 CDMX · 1:1.5 · stop ≥ 2 pts', replace(p, rr=1.5), 2),
       fila('9:30 NY todo el año · 1:2 · stop ≥ 2 pts', base, 2),
       fila('10:30 NY todo el año · 1:2 · stop ≥ 2 pts', replace(base, inicio='10:30'), 2),
       fila('9:30 NY · rango de 15 min · 1:2 · stop ≥ 2 pts', replace(base, rango_min=15), 2)]
json.dump({'rows': var, 'meta': meta + [{'label': 'Costos', 'value': 'ES: 1 tick de deslizamiento + 4.50 USD de comisión por contrato, ida y vuelta.'}]},
          open(os.path.join(OUT, 'orb_variantes.json'), 'w'), ensure_ascii=False)
print(len(rows), est.to_dict()); print(pd.DataFrame(var).to_string(index=False))
