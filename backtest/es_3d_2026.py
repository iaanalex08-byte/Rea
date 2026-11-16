"""Datos 3D del modelo B (9:12 CDMX, EMA 20 de 3 min, 2 contratos ES) solo con 2026."""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series

OUT = os.path.join(ROOT, "results", "es", "modelos_3d_2026")
os.makedirs(OUT, exist_ok=True)
df = load()
e20 = trend_series(df)["EMA20 3m"]


def paths_at(hm):
    out = []
    for d, t0, g in day_paths(df, hm, "America/Mexico_City"):
        if d.year != 2026:
            continue
        ref = e20.get(t0, np.nan)
        if np.isnan(ref):
            continue
        e = g["o"].iloc[0]
        out.append((e, 1 if e > ref else -1, g))
    return out


def run(P, sl, tp1, tp2):
    return np.array([trade_detail(e, s, g, sl, tp1, tp2)["ticks"] * TICK_USD - 2 * COST_T * TICK_USD for e, s, g in P])


def summ(u):
    gl = -u[u < 0].sum()
    return dict(avg=round(u.mean(), 2), pf=round(u[u > 0].sum() / gl, 4) if gl else None, wr=round((u > 0).mean(), 4), net=round(u.sum(), 2))


P = paths_at("9:12")
rows = []
for sl in range(15, 95, 5):
    for tp1 in range(10, 65, 5):
        rows.append(dict(sl=sl, tp1=tp1, tp2=2 * tp1, **summ(run(P, sl, tp1, 2 * tp1))))
pd.DataFrame(rows).to_csv(os.path.join(OUT, "sup_sl_tp.csv"), index=False)
print("sl x tp listo")

rows = []
for h in range(7, 12):
    for m in range(0, 60, 6):
        if (h, m) < (7, 30) or (h, m) > (11, 0):
            continue
        Ph = paths_at(f"{h}:{m:02d}")
        for sl in (30, 40, 45, 50, 60, 70, 80, 90):
            rows.append(dict(hora=f"{h}:{m:02d}", min=h * 60 + m, sl=sl, **summ(run(Ph, sl, 30, 60))))
pd.DataFrame(rows).to_csv(os.path.join(OUT, "sup_hora_sl.csv"), index=False)
print("hora x sl listo")
