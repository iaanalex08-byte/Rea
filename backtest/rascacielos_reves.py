#!/usr/bin/env python3
"""Rascacielos al revés: misma entrada a las 9:30 ET, pero en dirección contraria a las EMAs de 15 min,
con SL chico (el TP original) y TP grande (el SL original). Cierre 15:55 ET. 1 MNQ, comisión $1.24 + 1 tick.

    python3 backtest/rascacielos_reves.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import retiro_rapido as rr  # noqa: E402
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
    days.append((d, 1 if e20.iloc[k] > e50.iloc[k] else -1, g.open.values, g.high.values, g.low.values, g.close.values))
allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
rows = []
for tp_o, sl_o in ((10, 150), (22, 270), (20, 300), (40, 300), (20, 150)):
    for modo in ("original", "al revés"):
        res = []
        for d, side, O, H, Lw, C in days:
            if modo == "al revés":
                side, tp, sl = -side, sl_o, tp_o
            else:
                tp, sl = tp_o, sl_o
            e = O[0]; tpp, slp = e + side * tp, e - side * sl; out, mae = None, 0.0
            for i in range(len(O)):
                mae = max(mae, (e - (Lw[i] if side == 1 else H[i])) * side)
                if (Lw[i] <= slp) if side == 1 else (H[i] >= slp):
                    out = -sl; break
                if (H[i] >= tpp) if side == 1 else (Lw[i] <= tpp):
                    out = tp; break
            if out is None:
                out = (C[-1] - e) * side
            res.append((d, out * 2 - 1.74, min(mae, sl) * 2 + 1.74))
        x = pd.DataFrame(res, columns=["d", "usd", "mae"]); y = pd.to_datetime(x.d).dt.year
        g = {dd: [] for dd in allday}
        for r in x.itertuples():
            if r.d in g:
                g[r.d].append(("x", r.usd, r.mae))
        dl = [g[dd] for dd in allday]
        DD = [(sum(p for _, p, _ in o), sum(m for _, _, m in o)) for o in dl]
        ev = [(s, L.evaluacion(DD, s)) for s in range(len(DD))]; ev = [(s, r_) for s, r_ in ev if r_[0] is not None]
        fr = [rr.sim(dl, lambda b, e_: 1, s) for s in range(0, len(dl) - 120)]; fr = [f for f in fr if f[0] is not None]
        eq = x.usd.cumsum()
        rows.append({"TP/SL original": f"{tp_o}/{sl_o}", "modo": modo, "TP": tp if modo == "original" else sl_o, "SL": sl if modo == "original" else tp_o,
                     "acierto %": round(100 * (x.usd > 0).mean(), 1), "$/op 24-25": round(x.usd[y <= 2025].mean(), 1),
                     "$/op 2026": round(x.usd[y == 2026].mean(), 1), "neto 3 años $": round(x.usd.sum()),
                     "caída máx $": round((eq.cummax().clip(lower=0) - eq).max()),
                     "eval pasa %": round(100 * np.mean([r_[0] for _, r_ in ev]), 1), "1er retiro %": round(100 * np.mean([f[0] for f in fr]), 1)})
pd.set_option("display.width", 220)
print(pd.DataFrame(rows).to_string(index=False))
