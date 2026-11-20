#!/usr/bin/env python3
"""Operar SOLO la SMC (vigila desde 3:00 ET, entradas desde la hora de llegada) en Lucid 25K Flex.
    python3 backtest/smc_sola.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import lucid_rapidez as LR  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

PV, COM = 2.0, 1.24
nq1 = load("backtest/datos_NQ"); n5 = resample(nq1, 5)
allday = pd.bdate_range("2024-01-02", "2026-11-06").date
rows = []
for llegada, ef in (("3:00 ET (madrugada)", 0), ("9:30 ET (8:30 CDMX inv.)", 570)):
    s = sm.run(n5, 180, "FVG", False, "nuevo extremo", 1.0, entry_from=ef)
    maes = []
    for r in s.itertuples():
        w = nq1.loc[r.entry_time:r.exit_time]
        ref = w.close.iloc[0] if len(w) else np.nan
        adv = (w.high.max() - ref) if r.side == -1 else (ref - w.low.min())
        maes.append(r.risk if r.how == "SL" else float(np.clip(adv, 0, r.risk)))
    s = s.assign(mae=maes, pts=s.R * s.risk)
    y = pd.to_datetime(s.date).dt.year
    for k in (1, 2, 3, 4):
        x = pd.DataFrame({"date": s.date, "u": s.pts * PV * k - COM * k, "m": s.mae * PV * k + COM * k}).groupby("date").sum()
        x = x.reindex(allday).fillna(0)  # todos los días hábiles, operes o no
        D = list(zip(x.u, x.m))
        ev = [(st, L.evaluacion(D, st)) for st in range(len(D))]
        ev = [(st, r) for st, r in ev if r[0] is not None]
        p = np.mean([r[0] for _, r in ev]); dp = np.median([r[1] for _, r in ev if r[0]])
        fr = [LR.fondeada(D, st) for st in range(0, len(D) - 60)]
        first = [f[3] for f in fr if f[3]]
        eq = x.u.cumsum()
        rows.append({"llegada": llegada, "MNQ": k, "ops/año": round(len(s) / 2.85), "acierto %": round(100 * (s.R > 0).mean(), 1),
                     "R/op": round(s.R.mean(), 3), "neto 3 años $": round(x.u.sum()), "caída máx $": round((eq.cummax().clip(lower=0) - eq).max()),
                     "eval pasa %": round(100 * p, 1), "eval días hábiles": int(dp),
                     "fond 1+ retiro %": round(100 * np.mean([f[1] >= 1 for f in fr]), 1), "fond cobrado $": round(np.mean([f[0] for f in fr])),
                     "días al 1er retiro": np.median(first) if first else None})
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).to_string(index=False))
