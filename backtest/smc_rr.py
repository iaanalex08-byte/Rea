#!/usr/bin/env python3
"""SMC 5 min: ¿se puede alargar el R:R? (vigila desde 3:00 ET; entradas desde 9:30 ET o desde 3:00 ET)
  nuevo extremo (R:R >= m): TP en el nuevo extremo, solo si queda a m R o más.
  max N: TP en el nuevo extremo o a N R, lo que quede más lejos.
  N: TP fijo a N R.
    python3 backtest/smc_rr.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import retiro_rapido as rr  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

nq1 = load("backtest/datos_NQ"); n5 = resample(nq1, 5)
allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
rows = []
for ef, lab in ((570, "9:30 ET"), (0, "3:00 ET")):
    for tp, mrr in (("nuevo extremo", 1.0), ("nuevo extremo", 1.5), ("nuevo extremo", 2.0), ("nuevo extremo", 2.5),
                    ("max 1.5", 1.0), ("max 2", 1.0), ("max 2.5", 1.0), ("max 3", 1.0),
                    ("1.5", 0), ("2", 0), ("2.5", 0), ("3", 0)):
        s = sm.run(n5, 180, "FVG", False, tp, mrr, entry_from=ef)
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
        res = [x for x in res if x[0] is not None]; ok = [x[1] for x in res if x[0]]
        name = tp if tp != "nuevo extremo" else f"extremo, solo si >= {mrr:g}R"
        rows.append({"entradas desde": lab, "TP": name, "ops/año": round(len(s) / 2.85), "acierto %": round(100 * (s.R > 0).mean(), 1),
                     "RR medio ganadoras": round(s.R[s.R > 0].mean(), 2), "R/op": round(s.R.mean(), 3),
                     "R 24-25": round(s.R[y <= 2025].sum(), 1), "R 2026": round(s.R[y == 2026].sum(), 1),
                     "$ al año 1 MNQ": round((s.R * s.risk * 2 - 1.24).sum() / 2.85), "cierres 12:00": int((s.how == "CIERRE").sum()),
                     "1er retiro %": round(100 * np.mean([x[0] for x in res]), 1), "días 1er retiro": np.median(ok) if ok else None})
    print(lab, "listo", file=sys.stderr)
pd.set_option("display.width", 240)
print(pd.DataFrame(rows).to_string(index=False))
