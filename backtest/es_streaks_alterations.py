"""Mejor y peor racha de las alteraciones clave del modelo B (9:12 CDMX, EMA20 3m).

    python backtest/es_streaks_alterations.py -> results/es/alteraciones_winrate/rachas.csv
"""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK, TICK_USD, day_paths, load, trend_series

df = load()
e20 = trend_series(df)["EMA20 3m"]
rth = df.between_time("09:30", "15:59")
day = rth.index.normalize()
atr = (rth["h"].groupby(day).max() - rth["l"].groupby(day).min()).rolling(10).mean().shift(1)
B = []
for d, t0, g in day_paths(df, "9:12", "America/Mexico_City"):
    ref = e20.get(t0, np.nan)
    if np.isnan(ref):
        continue
    e = g["o"].iloc[0]
    B.append((pd.Timestamp(d), e, 1 if e > ref else -1, g, atr.get(pd.Timestamp(d), np.nan)))


def streaks(flags):
    best = worst = rw = rl = 0
    for f in flags:
        rw, rl = (rw + 1, 0) if f else (0, rl + 1)
        best, worst = max(best, rw), max(worst, rl)
    return best, worst


CASES = [("SL 60 · TP 15/30 (tu configuración)", lambda a: (60, 15)),
         ("SL 60 · TP 10/20", lambda a: (60, 10)),
         ("SL 60 · TP 8/16", lambda a: (60, 8)),
         ("SL 80 · TP 10/20", lambda a: (80, 10)),
         ("SL 45 · TP 30/60", lambda a: (45, 30)),
         ("SL 15 · TP 55/110", lambda a: (15, 55)),
         ("TP1 = 3% del rango medio · SL = 50%", lambda a: (max(20, round(a * .5 / TICK)), max(4, round(a * .03 / TICK)))),
         ("TP1 = 3% del rango medio · SL = 35%", lambda a: (max(20, round(a * .35 / TICK)), max(4, round(a * .03 / TICK))))]
rows = []
for name, f in CASES:
    usd, hit = [], []
    for d, e, s, g, a in B:
        if "rango" in name and np.isnan(a):
            continue
        sl, tp1 = f(a)
        x = trade_detail(e, s, g, sl, tp1, 2 * tp1)
        usd.append(x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD); hit.append(x["x1"] == "TP1")
    usd = np.array(usd)
    bw, ww = streaks(usd > 0)
    bt, wt = streaks(hit)
    gl = -usd[usd < 0].sum()
    rows.append(dict(alteracion=name, n=len(usd), tp1_rate=np.mean(hit), winrate=(usd > 0).mean(),
                     mejor_racha_ganancias=bw, peor_racha_perdidas=ww,
                     mejor_racha_tp1=bt, peor_racha_sin_tp1=wt,
                     perdida_max=usd.min(), pf=usd[usd > 0].sum() / gl, net=usd.sum()))
R = pd.DataFrame(rows)
R.round(4).to_csv(os.path.join(ROOT, "results", "es", "alteraciones_winrate", "rachas.csv"), index=False)
pd.set_option("display.width", 220)
print(R.round(3).to_string(index=False))


# ---- tabla por día de la semana
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie"]
drows = []
for name, f in CASES:
    recs = []
    for d, e, s, g, a in B:
        if "rango" in name and np.isnan(a):
            continue
        sl, tp1 = f(a)
        x = trade_detail(e, s, g, sl, tp1, 2 * tp1)
        recs.append((d.weekday(), x["x1"] == "TP1", x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD))
    t = pd.DataFrame(recs, columns=["wd", "hit", "usd"])
    for wd, g in t.groupby("wd"):
        u = g.usd.to_numpy()
        bw, ww = streaks(u > 0)
        gl = -u[u < 0].sum()
        drows.append(dict(alteracion=name, dia=DIAS[wd], n=len(u), tp1_rate=g.hit.mean(), winrate=(u > 0).mean(),
                          mejor_racha=bw, peor_racha=ww, pf=u[u > 0].sum() / gl if gl else np.nan,
                          net=u.sum(), avg=u.mean()))
D = pd.DataFrame(drows)
D.round(4).to_csv(os.path.join(ROOT, "results", "es", "alteraciones_winrate", "dias.csv"), index=False)
print(D.round(3).to_string(index=False))
