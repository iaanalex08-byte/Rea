#!/usr/bin/env python3
"""Superficie de varianza/riesgo: SL x R:R (POC 9:00, salida única, 1 MES con costos, Monte Carlo de 250 operaciones).

    python3 backtest/varianza_superficie.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

SLS = [9, 11, 13, 15, 17]
RRS = [1.0, 1.25, 1.5, 1.75, 2.0]
SLIP, COM, PV, N, SIMS = 0.25, 1.24, 5.0, 250, 10000


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data, "--single"])
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    d, _ = pb.filter_days(df, base)
    rng = np.random.default_rng(5)
    rows = []
    for sl in SLS:
        for rr in RRS:
            a = pb.parse_args([data, "--single", "--sl", str(sl), "--rr", str(rr)])
            tr, _ = pb.run(d, a)
            tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
            R = tr.pts.to_numpy() / sl
            usd = (tr.pts.to_numpy() - SLIP) * PV - COM
            paths = rng.choice(usd, size=(SIMS, N)).cumsum(axis=1)
            pk = np.maximum.accumulate(np.concatenate([np.zeros((SIMS, 1)), paths], axis=1), axis=1)[:, 1:]
            mdd = (paths - pk).min(axis=1)
            rows.append({"sl": sl, "rr": rr, "winrate": round(100 * (tr.result == "GANADA").mean(), 2),
                         "esperanza_r": round(R.mean(), 4), "desv_r": round(R.std(ddof=1), 4),
                         "calidad": round(R.mean() / R.std(ddof=1), 4), "esperanza_usd": round(usd.mean(), 2),
                         "desv_usd": round(usd.std(ddof=1), 2), "prob_ganar_1a": round(100 * (paths[:, -1] > 0).mean(), 2),
                         "prob_caida_1000": round(100 * (mdd <= -1000).mean(), 2), "caida_mediana": round(np.median(mdd))})
    t = pd.DataFrame(rows)
    t.to_csv("backtest/resultados/varianza_superficie.csv", index=False)
    pd.set_option("display.width", 220)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
