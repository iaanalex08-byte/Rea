#!/usr/bin/env python3
"""SP500 a favor de la tendencia 00:00-9:00 CDMX (>= 20 pts): SL 45 ticks, mitad en TP1 30 ticks + BE, resto en TP2 60 ticks.
Entradas 9:12 y 9:00. 2 MES, comisión y 1 tick de deslizamiento incluidos.
    python3 backtest/sp500_sl45.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

SL = 45
g.SALIDAS["sl45"] = ([(0.5, 30 / SL), (0.5, 60 / SL)], True)
USD_R = SL * g.TICK * g.PV * 2


def main():
    days = g.prep(bars("backtest/datos"))
    for ent in (552, 540):
        for mt in (20, 0):
            rows = []
            for d in days:
                t = g.run([d], SL, "sl45", ent, mt)
                if not t.empty:
                    rows.append((d[0], float(t.R.iloc[0])))
            x = pd.DataFrame(rows, columns=["f", "R"])
            x["usd"] = x.R * USD_R
            x["res"] = pd.cut(x.R, [-9, -0.5, 0.05, 0.6, 9], labels=["SL", "BE/cierre", "TP1+BE", "TP2"])
            x["a"] = x.f.astype(str).str[:4]
            print(f"\n=== {ent // 60}:{ent % 60:02d}  tendencia >= {mt} pts")
            for a, z in list(x.groupby("a")) + [("total", x)]:
                eq = z.usd.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
                s = (z.R < -0.5).astype(int); ml = s.groupby((s != s.shift()).cumsum()).sum().max()
                m = z.groupby(z.f.astype(str).str[:7]).usd.sum()
                vc = z.res.value_counts(normalize=True) * 100
                print(f"{a:6} {len(z):4d} TP1 {(z.R > 0.05).mean() * 100:5.1f}  TP2 {vc['TP2']:5.1f}  TP1+BE {vc['TP1+BE']:5.1f}  "
                      f"SL {vc['SL']:5.1f}  otro {vc['BE/cierre']:4.1f}  R {z.R.sum():6.1f}  R/op {z.R.mean():6.3f}  usd {z.usd.sum():7.0f}  "
                      f"DD {dd:5.0f}  SLseg {ml}  meses+ {(m > 0).sum()}/{len(m)}")
            if ent == 552 and mt == 20:
                z = x[x.a == "2026"]
                print(z.groupby(z.f.astype(str).str[:7]).usd.sum().round().to_string())


if __name__ == "__main__":
    main()
