#!/usr/bin/env python3
"""Varianza y riesgo de la estrategia del POC (9:00, SL 13, salida única) por R:R. 1 MES con costos.

    python3 backtest/varianza_rr.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

RRS = [1.0, 1.25, 1.5]
SLIP, COM, PV = 0.25, 1.24, 5.0


def streak(res, val):
    m = c = 0
    for r in res:
        c = c + 1 if r == val else 0
        m = max(m, c)
    return m


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data, "--single"])
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    d, _ = pb.filter_days(df, base)
    rng = np.random.default_rng(11)
    rows = []
    for rr in RRS:
        a = pb.parse_args([data, "--single", "--rr", str(rr)])
        tr, _ = pb.run(d, a)
        tr = tr[tr.result.isin(["GANADA", "PERDIDA"])].reset_index(drop=True)
        R = tr.pts.to_numpy() / a.sl
        usd = (tr.pts.to_numpy() - SLIP) * PV - COM
        eq = usd.cumsum()
        peak = np.maximum.accumulate(np.r_[0, eq])[1:]
        dd = eq - peak
        # tiempo bajo el agua (operaciones desde un máximo hasta recuperarlo)
        under, mx = 0, 0
        for x in dd:
            under = under + 1 if x < 0 else 0
            mx = max(mx, under)
        tr["mes"] = pd.to_datetime(tr.date).dt.to_period("M")
        mon = pd.Series(usd).groupby(tr.mes.values).sum()
        n = 250
        paths = rng.choice(usd, size=(20000, n)).cumsum(axis=1)
        pk = np.maximum.accumulate(np.concatenate([np.zeros((20000, 1)), paths], axis=1), axis=1)[:, 1:]
        mdd = (paths - pk).min(axis=1)
        rows.append({
            "R:R": f"1:{rr:g}", "operaciones": len(tr), "winrate %": round(100 * (tr.result == "GANADA").mean(), 1),
            "equilibrio %": round(100 / (1 + rr), 1),
            "esperanza R/op": round(R.mean(), 3), "desv R/op": round(R.std(ddof=1), 3),
            "varianza R²": round(R.var(ddof=1), 3), "esperanza/desv": round(R.mean() / R.std(ddof=1), 3),
            "esperanza $/op": round(usd.mean(), 2), "desv $/op": round(usd.std(ddof=1), 2),
            "peor racha SL": streak(tr.result, "PERDIDA"), "mejor racha TP": streak(tr.result, "GANADA"),
            "peor caída $": round(dd.min()), "ops bajo el agua (máx)": mx,
            "meses positivos": f"{(mon > 0).sum()}/{len(mon)}", "desv mensual $": round(mon.std(ddof=1)),
            "MC 1 año: P(ganar)": round(100 * (paths[:, -1] > 0).mean(), 1),
            "MC: neto mediana $": round(np.median(paths[:, -1])),
            "MC: P5 / P95 $": f"{np.percentile(paths[:, -1], 5):,.0f} / {np.percentile(paths[:, -1], 95):,.0f}",
            "MC: P(caída >= $1,000)": round(100 * (mdd <= -1000).mean(), 1),
            "MC: caída mediana $": round(np.median(mdd)),
        })
    out = pd.DataFrame(rows).set_index("R:R").T
    pd.set_option("display.width", 200)
    print(out.to_string())
    out.to_csv("backtest/resultados/varianza_rr.csv")


if __name__ == "__main__":
    main()
