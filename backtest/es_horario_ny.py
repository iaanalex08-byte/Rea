"""Modelo B: 9:12 CDMX (como se opera; cambia de hora NY con el horario de verano de EE. UU.)
frente a hora fija de Nueva York todo el año (10:12 NY = 42 min tras la apertura; 11:12 NY = 1 h 42 min).

    python backtest/es_horario_ny.py  ->  results/es/horario_ny_vs_cdmx.csv
"""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series

df = load()
e20 = trend_series(df)["EMA20 3m"]
MODOS = [("9:12 CDMX (como operas)", "9:12", "America/Mexico_City"),
         ("10:12 NY fijo (42 min tras la apertura)", "10:12", "America/New_York"),
         ("11:12 NY fijo (1 h 42 min tras la apertura)", "11:12", "America/New_York"),
         ("9:42 NY fijo (12 min tras la apertura)", "9:42", "America/New_York")]
CONFIGS = [("SL 45 · TP 30/60", 45, 30, 60), ("SL 60 · TP 15/30", 60, 15, 30), ("SL 15 · TP 50/100", 15, 50, 100)]

# temporada según el horario de NY de cada fecha (verano = EDT)
def temporada(d):
    return "Verano NY" if pd.Timestamp(d).tz_localize("America/New_York").utcoffset().total_seconds() == -4 * 3600 else "Invierno NY"

rows = []
for modo, hm, tz in MODOS:
    for d, t0, g in day_paths(df, hm, tz):
        ref = e20.get(t0, np.nan)
        if np.isnan(ref):
            continue
        e = g["o"].iloc[0]; s = 1 if e > ref else -1
        for cfg, sl, t1, t2 in CONFIGS:
            x = trade_detail(e, s, g, sl, t1, t2)
            rows.append(dict(modo=modo, config=cfg, date=d, year=d.year, temporada=temporada(d), hora_ny=t0.strftime("%H:%M"),
                             usd=x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD))
T = pd.DataFrame(rows)


def st(u):
    u = np.asarray(u); gl = -u[u < 0].sum(); sd = u.std(ddof=1)
    eq = np.cumsum(u); dd = -(eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    return pd.Series(dict(n=len(u), wr=(u > 0).mean(), pf=u[u > 0].sum() / gl, net=u.sum(), avg=u.mean(), maxdd=dd, t=u.mean() / sd * np.sqrt(len(u))))


out = []
for (modo, cfg), g in T.groupby(["modo", "config"], sort=False):
    for etiqueta, sub in [("Todo", g), ("2025", g[g.year == 2025]), ("2026", g[g.year == 2026]),
                          ("Invierno NY", g[g.temporada == "Invierno NY"]), ("Verano NY", g[g.temporada == "Verano NY"])]:
        out.append(dict(modo=modo, config=cfg, periodo=etiqueta, **st(sub.usd)))
R = pd.DataFrame(out)
R.to_csv(os.path.join(ROOT, "results", "es", "horario_ny_vs_cdmx.csv"), index=False)
pd.set_option("display.width", 220)
for cfg in [c[0] for c in CONFIGS]:
    print("\n==", cfg)
    p = R[R.config == cfg].pivot_table(index="modo", columns="periodo", values="net", sort=False).round(0)
    print(p[["Todo", "2025", "2026", "Invierno NY", "Verano NY"]].to_string())
    print(R[(R.config == cfg) & (R.periodo == "Todo")][["modo", "n", "wr", "pf", "avg", "maxdd", "t"]].round(3).to_string(index=False))
print(T[T.modo.str.startswith("9:12")].groupby(["temporada", "hora_ny"]).size())
