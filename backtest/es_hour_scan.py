"""Barrido de la hora de entrada (hora de Ciudad de México) para varias configuraciones del modelo B.

    python backtest/es_hour_scan.py  ->  results/es/barrido_horario_cdmx.csv
"""
import os

import numpy as np
import pandas as pd

from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series
from es_analysis_config import trade_detail

CONFIGS = [("SL 60 · TP 15/30", 60, 15, 30), ("SL 45 · TP 30/60", 45, 30, 60), ("SL 15 · TP 55/110", 15, 55, 110)]


def main():
    df = load()
    tr = trend_series(df)["EMA20 3m"]
    rows = []
    for h in range(7, 12):
        for m in range(0, 60, 6):
            hm = f"{h}:{m:02d}"
            if (h, m) < (7, 30) or (h, m) > (11, 0):
                continue
            paths = []
            for d, t0, g in day_paths(df, hm, "America/Mexico_City"):
                ref = tr.get(t0, np.nan)
                if np.isnan(ref):
                    continue
                e = g["o"].iloc[0]
                paths.append((pd.Timestamp(d), e, 1 if e > ref else -1, g))
            for name, sl, tp1, tp2 in CONFIGS:
                u = np.array([trade_detail(e, s, g, sl, tp1, tp2)["ticks"] * TICK_USD - 2 * COST_T * TICK_USD
                              for _, e, s, g in paths])
                yrs = np.array([d.year for d, *_ in paths])
                gl = -u[u < 0].sum()
                sd = u.std(ddof=1)
                eq = np.cumsum(u)
                rows.append(dict(hora=hm, config=name, n=len(u), winrate=round((u > 0).mean(), 4),
                                 pf=round(u[u > 0].sum() / gl, 4), net=round(u.sum(), 2), avg=round(u.mean(), 2),
                                 maxdd=round(float(-(eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()), 2),
                                 t=round(u.mean() / sd * np.sqrt(len(u)), 3),
                                 avg25=round(u[yrs == 2025].mean(), 2), avg26=round(u[yrs == 2026].mean(), 2)))
        print(h, flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(ROOT, "results", "es", "barrido_horario_cdmx.csv"), index=False)
    return out


if __name__ == "__main__":
    o = main()
    pd.set_option("display.width", 200)
    for c in o.config.unique():
        s = o[o.config == c].sort_values("t", ascending=False)
        print(c); print(s.head(6).to_string(index=False)); print("9:12:", s[s.hora == "9:12"].to_dict("records"))
        print("positivas", (s.avg > 0).sum(), "de", len(s), "| positivas en ambos años", ((s.avg25 > 0) & (s.avg26 > 0)).sum())
