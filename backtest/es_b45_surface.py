"""Superficie SL x TP1 (TP2 = 2 x TP1) del modelo B · 9:12 CDMX · EMA20 3m, 2 contratos con BE."""
import os
import numpy as np
import pandas as pd
from es_backtest import COST_T, TICK_USD, day_paths, load, trend_series
from es_analysis_config import CFG, OUT, trade_detail

df = load()
tr = trend_series(df)[CFG["trend"]]
paths = []
for d, t0, g in day_paths(df, CFG["time"], CFG["tz"]):
    ref = tr.get(t0, np.nan)
    if np.isnan(ref):
        continue
    e = g["o"].iloc[0]
    paths.append((e, 1 if e > ref else -1, g))
rows = []
for sl in range(15, 95, 5):
    for tp1 in range(10, 65, 5):
        u = np.array([trade_detail(e, s, g, sl, tp1, 2 * tp1)["ticks"] * TICK_USD - 2 * COST_T * TICK_USD for e, s, g in paths])
        gl = -u[u < 0].sum()
        rows.append(dict(sl=sl, tp1=tp1, tp2=2 * tp1, avg=round(u.mean(), 2), pf=round(u[u > 0].sum() / gl, 4) if gl else None,
                         wr=round((u > 0).mean(), 4), net=round(u.sum(), 2)))
s = pd.DataFrame(rows)
s.to_csv(os.path.join(OUT, "b45_superficie.csv"), index=False)
print(s.sort_values("avg", ascending=False).head(5).to_string()); print(s[(s.sl == 45) & (s.tp1 == 30)])
print("positivas", (s.avg > 0).sum(), "de", len(s))
