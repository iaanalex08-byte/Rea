#!/usr/bin/env python3
"""Entrada a mercado a las 8:30 CDMX (UTC-6 fija) en NQ con distintas direcciones, SL y TP.
Dirección: EMA 20/50 de 15 min · tendencia 00:00 -> 8:30 · contra Londres (00:00 -> 6:00).
TP: 1:1, 1:2, 1:3 o sin TP (cierre a las 14:30 CDMX). Costo 2 pts por operación (apertura con deslizamiento).

    python3 backtest/entrada_830.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as c  # noqa: E402

df = c.bars(1)
tm = df.index.hour * 60 + df.index.minute
c15 = df.close.resample("15min", label="left", closed="left").last().dropna()
e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
days = []
for d, g in df.groupby(df.index.date):
    t = (g.index.hour * 60 + g.index.minute).to_numpy()
    if t[0] != 0 or 510 not in t or (t >= 870).sum() == 0 or d < pd.Timestamp("2024-01-01").date():
        continue
    i0 = int(np.searchsorted(t, 510)); i1 = int(np.searchsorted(t, 870))
    e = g.open.values[i0]; o0 = g.open.values[0]
    lc = g.close.values[int(np.searchsorted(t, 360)) - 1]
    k = c15.index.searchsorted(g.index[i0]) - 1
    dirs = {"EMA 15 min": 1 if e20.iloc[k] > e50.iloc[k] else -1, "tendencia 00:00": int(np.sign(e - o0)),
            "contra Londres": -int(np.sign(lc - o0))}
    H, L = g.high.values[i0:i1] - e, e - g.low.values[i0:i1]
    exitp = g.open.values[i1] - e
    summer = g.index[i0].tz_convert("America/New_York").utcoffset() == pd.Timedelta(hours=-4)
    days.append((d.year, summer, dirs, H, L, exitp))


def first(a, x):
    i = np.argmax(a >= x)
    return i if a[i] >= x else 10 ** 6


rows = []
for dname in ("EMA 15 min", "tendencia 00:00", "contra Londres"):
    for sl in (20, 30, 40, 60, 80, 100):
        for rr in (1, 2, 3, None):
            res = []
            for y, su, dirs, H, L, ex in days:
                s = dirs[dname]
                if s == 0:
                    continue
                fav, adv = (H, L) if s == 1 else (L, H)
                isl = first(adv, sl); itp = first(fav, rr * sl) if rr else 10 ** 6
                pts = -sl if (isl <= itp and isl < 10 ** 6) else (rr * sl if itp < 10 ** 6 else ex * s)
                res.append((y, su, pts - 2.0))
            x = pd.DataFrame(res, columns=["y", "verano", "p"])
            rows.append({"dirección": dname, "SL": sl, "TP": f"1:{rr}" if rr else "cierre 14:30", "acierto %": round(100 * (x.p > 0).mean(), 1),
                         "pts/op 24-25": round(x.p[x.y <= 2025].mean(), 1), "pts/op 2026": round(x.p[x.y == 2026].mean(), 1),
                         "pts/op invierno": round(x.p[~x.verano].mean(), 1), "pts/op verano": round(x.p[x.verano].mean(), 1),
                         "R/op": round(x.p.mean() / sl, 3)})
T = pd.DataFrame(rows)
T["robusta"] = (T["pts/op 24-25"] > 0) & (T["pts/op 2026"] > 0)
pd.set_option("display.width", 220)
print(T.to_string(index=False))
print(f"\nRobustas: {T.robusta.sum()} de {len(T)}")
T.to_csv("backtest/resultados/entrada_830.csv", index=False)
