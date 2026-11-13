#!/usr/bin/env python3
"""Entrada a las 9:30 ET (a favor o en contra de la EMA 20/50 de 15 min): búsqueda de SL y TP con ventaja.
Robusta = gana en 2024-25 y en 2026 con costo realista (2 pts por operación: comisión + deslizamiento en la apertura).
Cierre 15:55 ET si no toca nada. 1 MNQ.

    python3 backtest/rascacielos_grid.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load  # noqa: E402

nq = load("backtest/datos_NQ")
c15 = nq.close.resample("15min", label="left", closed="left").last().dropna()
e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
tm = nq.index.hour * 60 + nq.index.minute
w = nq[(tm >= 570) & (tm < 955)]
days = []
for d, g in w.groupby(w.index.date):
    if d < pd.Timestamp("2024-01-01").date() or g.index[0].hour * 60 + g.index[0].minute != 570:
        continue
    k = c15.index.searchsorted(g.index[0]) - 1
    e = g.open.values[0]
    days.append((d.year, 1 if e20.iloc[k] > e50.iloc[k] else -1, g.high.values - e, e - g.low.values, g.close.values[-1] - e))
TPS = [10, 20, 30, 40, 60, 80, 100, 150, 200, 300]
SLS = [10, 15, 20, 30, 40, 60, 80, 100, 150, 200, 300]


def first(arr, x):
    i = np.argmax(arr >= x)
    return i if arr[i] >= x else 10 ** 6


rows = []
for modo in ("a favor EMA", "contra EMA"):
    for tp in TPS:
        for sl in SLS:
            res = []
            for y, side, up, dn, last in days:
                s = side if modo == "a favor EMA" else -side
                fav, adv = (up, dn) if s == 1 else (dn, up)
                it, isl = first(fav, tp), first(adv, sl)
                if isl <= it and isl < 10 ** 6:
                    pts = -sl
                elif it < 10 ** 6:
                    pts = tp
                else:
                    pts = last * s
                res.append((y, pts))
            x = pd.DataFrame(res, columns=["y", "pts"])
            for cost in (0.5, 2.0):
                p = x.pts - cost
                rows.append({"modo": modo, "TP": tp, "SL": sl, "costo": cost, "acierto %": round(100 * (p > 0).mean(), 1),
                             "pts/op 24-25": round(p[x.y <= 2025].mean(), 2), "pts/op 2026": round(p[x.y == 2026].mean(), 2),
                             "R/op": round(p.mean() / sl, 3), "$ año 1 MNQ": round(p.sum() * 2 / 2.85)})
T = pd.DataFrame(rows)
T["robusta"] = (T["pts/op 24-25"] > 0) & (T["pts/op 2026"] > 0)
T.to_csv("backtest/resultados/rascacielos_grid.csv", index=False)
pd.set_option("display.width", 220)
for cost in (0.5, 2.0):
    R = T[T.costo == cost]
    print(f"\n=== costo {cost} pts: robustas {R.robusta.sum()} de {len(R)} ===")
    for m in ("a favor EMA", "contra EMA"):
        piv = R[R.modo == m].pivot_table(index="SL", columns="TP", values="robusta", aggfunc="max").astype(int)
        print(f"{m} (1 = gana en ambos periodos):"); print(piv.to_string())
    print(R[R.robusta].sort_values("R/op", ascending=False).head(12).to_string(index=False))
