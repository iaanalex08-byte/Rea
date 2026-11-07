#!/usr/bin/env python3
"""SMC con inicio de ventana más tarde (sin madrugar) y su efecto en la fondeada 8:30 + 10:30 + SMC (1 MNQ c/u).
    python3 backtest/smc_horario.py
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
base = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry", "exit"])
base = base[base.est != "C SMC"]
base["entry"] = pd.to_datetime(base.entry, utc=True); base["exit"] = pd.to_datetime(base.exit, utc=True)
base["date"] = pd.to_datetime(base.date).dt.date
nq1 = load("backtest/datos_NQ"); n5 = resample(nq1, 5)
rows = []
for h, m in ((3, 0), (6, 0), (7, 0), (8, 0), (8, 30), (9, 0), (9, 30)):
    s = sm.run(n5, h * 60 + m, "FVG", False, "nuevo extremo", 1.0)
    y = pd.to_datetime(s.date).dt.year
    c = []
    for r in s.itertuples():
        w = nq1.loc[r.entry_time:r.exit_time]
        ref = w.close.iloc[0] if len(w) else np.nan
        adv = (w.high.max() - ref) if r.side == -1 else (ref - w.low.min())
        c.append({"est": "C SMC", "date": r.entry_time.tz_convert("Etc/GMT+6").date(), "entry": r.entry_time.tz_convert("UTC"),
                  "exit": r.exit_time.tz_convert("UTC"), "pts": r.R * r.risk,
                  "mae": r.risk if r.how == "SL" else float(np.clip(adv, 0, r.risk)), "R": r.R})
    t = pd.concat([base, pd.DataFrame(c)]).sort_values("entry")
    keep, busy = [], None
    for r in t.itertuples():
        if busy is not None and r.entry < busy:
            continue
        keep.append(r.Index); busy = r.exit
    t = t.loc[keep]
    x = pd.DataFrame({"date": t.date, "u": t.pts * PV - COM, "m": t.mae * PV + COM}).groupby("date").sum()
    D = list(zip(x.u, x.m))
    fr = [LR.fondeada(D, st) for st in range(0, len(D) - 60)]
    first = [f[3] for f in fr if f[3]]
    rows.append({"SMC desde (ET)": f"{h}:{m:02d}", "CDMX invierno": f"{h - 1}:{m:02d}", "CDMX verano": f"{h - 2}:{m:02d}",
                 "SMC ops": len(s), "SMC acierto": round(100 * (s.R > 0).mean(), 1), "SMC R/op": round(s.R.mean(), 3),
                 "SMC R 24-25": round(s.R[y <= 2025].sum(), 1), "SMC R 2026": round(s.R[y == 2026].sum(), 1),
                 "combo neto $": round(x.u.sum()), "fond 1+ retiro %": round(100 * np.mean([f[1] >= 1 for f in fr]), 1),
                 "fond cobrado $": round(np.mean([f[0] for f in fr])), "días 1er retiro": np.median(first)})
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).to_string(index=False))
