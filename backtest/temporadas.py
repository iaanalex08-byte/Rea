"""Modelo B por temporada: 9:12 CDMX fijo frente a fijar la hora de Nueva York.

Uso: python3 backtest/temporadas.py datos/
"""
import sys
import numpy as np, pandas as pd
from engine import load, run, stats

df = load(sys.argv[1] if len(sys.argv) > 1 else 'datos')
for nombre, kw in [('9:12 CDMX fijo (UTC-6)', dict(entry_tz='America/Mexico_City', eh=9, em=12)),
                   ('10:12 NY fijo', dict(entry_tz='America/New_York', eh=10, em=12)),
                   ('11:12 NY fijo', dict(entry_tz='America/New_York', eh=11, em=12))]:
    T = run(df, 1, **kw)
    verano = pd.to_datetime(T.date).dt.tz_localize('America/New_York').map(lambda t: t.dst() != pd.Timedelta(0)).values
    for etiqueta, mask in [('todo', np.ones(len(T), bool)), ('invierno EE. UU.', ~verano), ('verano EE. UU.', verano)]:
        s = stats(T[mask])
        print(f"{nombre:24s} {etiqueta:17s} ops {s['n']:4d}  win {s['wr']*100:5.1f}%  PF {s['pf']:.3f}  neto {s['net']:+10,.2f}")
