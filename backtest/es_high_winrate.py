"""Busca combinaciones de hora CDMX, SL y TP del modelo B donde >= 91% de las operaciones llegan al TP1.

    python backtest/es_high_winrate.py  ->  results/es/busqueda_winrate_91.csv
"""
import os
import numpy as np
import pandas as pd
from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series
from es_analysis_config import trade_detail

df = load()
tr = trend_series(df)["EMA20 3m"]
rows = []
for h in range(7, 12):
    for m in range(0, 60, 6):
        if (h, m) < (7, 30) or (h, m) > (11, 0):
            continue
        hm = f"{h}:{m:02d}"
        paths = []
        for d, t0, g in day_paths(df, hm, "America/Mexico_City"):
            ref = tr.get(t0, np.nan)
            if np.isnan(ref):
                continue
            e = g["o"].iloc[0]
            paths.append((pd.Timestamp(d).year, e, 1 if e > ref else -1, g))
        yrs = np.array([p[0] for p in paths])
        for sl in (30, 45, 60, 80, 100, 120, 160):
            for tp1 in (4, 6, 8, 10, 12, 15, 20):
                det = [trade_detail(e, s, g, sl, tp1, 2 * tp1) for _, e, s, g in paths]
                u = np.array([x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD for x in det])
                hit = np.array([x["x1"] == "TP1" for x in det])
                gl = -u[u < 0].sum()
                eq = np.cumsum(u)
                rows.append(dict(hora=hm, sl=sl, tp1=tp1, tp2=2 * tp1, n=len(u), tp1_rate=hit.mean(), winrate=(u > 0).mean(),
                                 tp1_25=hit[yrs == 2025].mean(), tp1_26=hit[yrs == 2026].mean(),
                                 pf=u[u > 0].sum() / gl if gl else np.inf, net=u.sum(), avg=u.mean(),
                                 maxdd=float(-(eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()),
                                 t=u.mean() / u.std(ddof=1) * np.sqrt(len(u)),
                                 avg25=u[yrs == 2025].mean(), avg26=u[yrs == 2026].mean()))
    print(h, flush=True)
r = pd.DataFrame(rows)
r.round(4).to_csv(os.path.join(ROOT, "results", "es", "busqueda_winrate_91.csv"), index=False)
hi = r[r.tp1_rate >= 0.91]
print("combinaciones:", len(r), "| que llegan a TP1 >= 91%:", len(hi), "| de esas con neto > 0:", (hi.net > 0).sum(),
      "| positivas en 2025 y 2026:", ((hi.avg25 > 0) & (hi.avg26 > 0)).sum())
pd.set_option("display.width", 200)
print(hi.sort_values("net", ascending=False).head(10).round(3).to_string(index=False))
print(hi.groupby(["sl", "tp1"]).agg(horas=("hora", "size"), tp1=("tp1_rate", "mean"), pf=("pf", "mean"), pos=("net", lambda x: (x > 0).sum())).round(3).to_string())
print("Mayor % a TP1:", r.sort_values("tp1_rate", ascending=False).head(3).round(3).to_string(index=False))

print("9:12 con TP1 15:", r[(r.hora == "9:12") & (r.tp1 == 15)][["sl", "tp1_rate", "pf", "net"]].round(3).to_string(index=False))
print("Mejor % a TP1 por hora (SL 60):"); print(r[r.sl == 60].sort_values("tp1_rate", ascending=False).head(5)[["hora","tp1","tp1_rate","pf","net"]].round(3).to_string(index=False))
