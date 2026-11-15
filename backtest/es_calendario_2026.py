"""Calendario y rachas del modelo B (9:12 CDMX, EMA 20 de 3 min, 2 contratos ES) para SL 45 · TP 30/60 y SL 15 · TP 50/100."""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series

OUT = os.path.join(ROOT, "results", "es", "calendario_2026")
os.makedirs(OUT, exist_ok=True)
CONFIGS = [("SL 45 · TP 30/60", 45, 30, 60), ("SL 15 · TP 50/100", 15, 50, 100)]
df = load()
e20 = trend_series(df)["EMA20 3m"]
rows = []
for d, t0, g in day_paths(df, "9:12", "America/Mexico_City"):
    ref = e20.get(t0, np.nan)
    if np.isnan(ref):
        continue
    e = g["o"].iloc[0]; s = 1 if e > ref else -1
    for name, sl, t1, t2 in CONFIGS:
        x = trade_detail(e, s, g, sl, t1, t2)
        res = "Perdió (SL)" if x["outcome"] == "Stop (−2)" else ("Cerró a las 15:59" if x["outcome"] == "Cierre 15:59" else "Ganó (TP)")
        rows.append(dict(config=name, date=d.strftime("%Y-%m-%d"), resultado=res, desenlace=x["outcome"],
                         lado="Compra" if s > 0 else "Venta", hora_ny=t0.strftime("%H:%M"), mins=x["mins"],
                         usd=round(x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD, 2)))
C = pd.DataFrame(rows)
C.to_csv(os.path.join(OUT, "calendario.csv"), index=False)


def rachas(u):
    bw = ww = a = b = 0
    sw = ew = sl_ = el_ = None
    dates = u.index
    for i, v in enumerate(u.values):
        if v > 0:
            a += 1; b = 0
            if a > bw: bw, ew, sw = a, dates[i], dates[i - a + 1]
        else:
            b += 1; a = 0
            if b > ww: ww, el_, sl_ = b, dates[i], dates[i - b + 1]
    return bw, sw, ew, ww, sl_, el_


for (cfg, periodo), g in [((c, p), C[(C.config == c) & (C.date >= ("2026" if p == "2026" else "0"))]) for c, *_ in CONFIGS for p in ("2025-2026", "2026")]:
    u = g.set_index("date").usd
    bw, sw, ew, ww, s2, e2 = rachas(u)
    gl = -u[u < 0].sum()
    print(f"{cfg} | {periodo}: n={len(u)} gana={int((u > 0).sum())} pierde={int((u <= 0).sum())} wr={(u > 0).mean():.2f} pf={u[u > 0].sum() / gl:.2f} neto={u.sum():.0f} | mejor racha {bw} ({sw}→{ew}) | peor racha {ww} ({s2}→{e2})")
