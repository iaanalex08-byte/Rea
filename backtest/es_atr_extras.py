"""Superficie 3D (TP1 % × SL % del rango medio) y barrido de hora CDMX del modelo B con objetivos por rango medio.

    python backtest/es_atr_extras.py
"""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK, TICK_USD, day_paths, load, trend_series

OUT = os.path.join(ROOT, "results", "es", "analisis_B_CDMX_ATR_tp3_sl50")
df = load()
e20 = trend_series(df)["EMA20 3m"]
rth = df.between_time("09:30", "15:59")
day = rth.index.normalize()
atr = (rth["h"].groupby(day).max() - rth["l"].groupby(day).min()).rolling(10).mean().shift(1)


def paths_at(hm):
    out = []
    for d, t0, g in day_paths(df, hm, "America/Mexico_City"):
        ref, a = e20.get(t0, np.nan), atr.get(pd.Timestamp(d), np.nan)
        if np.isnan(ref) or np.isnan(a):
            continue
        e = g["o"].iloc[0]
        out.append((pd.Timestamp(d).year, e, 1 if e > ref else -1, g, a))
    return out


def run(paths, tpf, slf):
    u = []
    for _, e, s, g, a in paths:
        tp1 = max(4, round(a * tpf / TICK)); sl = max(20, round(a * slf / TICK))
        x = trade_detail(e, s, g, sl, tp1, 2 * tp1)
        u.append(x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD)
    return np.array(u)


P912 = paths_at("9:12")
rows = []
for tp in range(1, 9):
    for sl in range(20, 105, 10):
        u = run(P912, tp / 100, sl / 100)
        gl = -u[u < 0].sum()
        rows.append(dict(sl=sl, tp1=tp, tp2=2 * tp, avg=round(u.mean(), 2), pf=round(u[u > 0].sum() / gl, 4) if gl else None,
                         wr=round((u > 0).mean(), 4), net=round(u.sum(), 2)))
S = pd.DataFrame(rows)
S.to_csv(os.path.join(OUT, "cfg_superficie.csv"), index=False)
print(S.sort_values("avg", ascending=False).head(5).to_string(index=False)); print("positivas", (S.avg > 0).sum(), "de", len(S))

hrows = []
old = pd.read_csv(os.path.join(ROOT, "results", "es", "barrido_horario_cdmx.csv"))
for h in range(7, 12):
    for m in range(0, 60, 6):
        if (h, m) < (7, 30) or (h, m) > (11, 0):
            continue
        hm = f"{h}:{m:02d}"
        P = paths_at(hm)
        u = run(P, 0.03, 0.5)
        yrs = np.array([p[0] for p in P])
        gl = -u[u < 0].sum(); eq = np.cumsum(u)
        hrows.append(dict(hora=hm, config="TP1 3% · SL 50% del rango", n=len(u), winrate=round((u > 0).mean(), 4),
                          pf=round(u[u > 0].sum() / gl, 4), net=round(u.sum(), 2), avg=round(u.mean(), 2),
                          maxdd=round(float(-(eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()), 2),
                          t=round(u.mean() / u.std(ddof=1) * np.sqrt(len(u)), 3),
                          avg25=round(u[yrs == 2025].mean(), 2), avg26=round(u[yrs == 2026].mean(), 2)))
H = pd.concat([pd.DataFrame(hrows), old[old.config.isin(["SL 60 · TP 15/30", "SL 45 · TP 30/60"])]])
H.to_csv(os.path.join(OUT, "cfg_horario.csv"), index=False)
h = pd.DataFrame(hrows)
print(h.sort_values("t", ascending=False).head(6).to_string(index=False))
print("horas positivas", (h.avg > 0).sum(), "de", len(h), "| ambos años", ((h.avg25 > 0) & (h.avg26 > 0)).sum(), "| 9:12:", h[h.hora == "9:12"][["winrate", "pf", "net"]].to_dict("records"))
