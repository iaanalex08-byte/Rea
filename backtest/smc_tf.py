#!/usr/bin/env python3
"""SMC en distintas temporalidades (entradas desde 9:30 ET, vigilando desde 3:00 ET) y días al primer retiro (1 MNQ).
    python3 backtest/smc_tf.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import retiro_rapido as rr  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

nq1 = load("backtest/datos_NQ")
allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
rows = []
for tf in (1, 2, 3, 5, 15):
    for ef, lab in ((570, "desde 9:30 ET"), (0, "desde 3:00 ET")):
        s = sm.run(resample(nq1, tf), 180, "FVG", False, "nuevo extremo", 1.0, entry_from=ef)
        if s.empty:
            continue
        y = pd.to_datetime(s.date).dt.year
        ops = []
        for r in s.itertuples():
            w = nq1.loc[r.entry_time:r.exit_time]
            ref = w.close.iloc[0] if len(w) else np.nan
            adv = (w.high.max() - ref) if r.side == -1 else (ref - w.low.min())
            ops.append({"est": "SMC", "date": r.entry_time.tz_convert("Etc/GMT+6").date(), "entry": r.entry_time.tz_convert("UTC"),
                        "exit": r.exit_time.tz_convert("UTC"), "pts": r.R * r.risk,
                        "mae": r.risk if r.how == "SL" else float(np.clip(adv, 0, r.risk))})
        days = rr.per_day(pd.DataFrame(ops), ["SMC"], allday)
        res = [rr.sim(days, lambda b, e: 1, st) for st in range(0, len(days) - 120)]
        res = [x for x in res if x[0] is not None]
        ok = [x[1] for x in res if x[0]]
        rows.append({"velas": f"{tf} min", "entradas": lab, "ops/año": round(len(s) / 2.85), "acierto %": round(100 * (s.R > 0).mean(), 1),
                     "SL mediano pts": round(s.risk.median(), 1), "R/op": round(s.R.mean(), 3), "R 24-25": round(s.R[y <= 2025].sum(), 1),
                     "R 2026": round(s.R[y == 2026].sum(), 1), "$ al año (1 MNQ)": round((s.R * s.risk * 2 - 1.24).sum() / 2.85),
                     "1er retiro %": round(100 * np.mean([x[0] for x in res]), 1), "días al 1er retiro": np.median(ok) if ok else None})
    print(f"{tf} min listo", file=sys.stderr)
pd.set_option("display.width", 220)
print(pd.DataFrame(rows).to_string(index=False))
