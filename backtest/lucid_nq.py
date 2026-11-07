#!/usr/bin/env python3
"""POC en NQ (perfil 10:30, SL 66.5, 1:1, salida única, velas de 3 min) en una Lucid 25K Flex por tamaño (MNQ).

    python3 backtest/lucid_nq.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import analisis as an  # noqa: E402
import lucid_flex25k as L  # noqa: E402
import lucid_rapidez as LR  # noqa: E402
import poc_backtest as pb  # noqa: E402

ARGS = ["backtest/datos_NQ", "--prof-hour", "10", "--prof-min", "30", "--win-start", "10:42", "--win-end", "13:30",
        "--sl", "66.5", "--rr", "1.0", "--single"]
SLIP, COM, PV = 0.25, 1.24, 2.0


def main():
    a = pb.parse_args(ARGS)
    df = pb.load_bars(a.csv, a.input_tz, a.tz, a.tf, a.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]
    d, _ = pb.filter_days(df, a)
    tr, _ = pb.run(d, a)
    tr = an.excursions(d, tr)
    res = tr.result.value_counts().to_dict()
    y = pd.to_datetime(tr.date).dt.year
    w = tr[tr.result.isin(["GANADA", "PERDIDA"])]
    print("Operaciones:", res, "| winrate %.1f%%" % (100 * (w.result == "GANADA").mean()))
    for yy in sorted(y.unique()):
        s = tr[(y == yy) & tr.result.isin(["GANADA", "PERDIDA"])]
        print(f"  {yy}: {len(s)} ops, winrate {100 * (s.result == 'GANADA').mean():.1f}%, R {s.pts.sum() / 66.5:+.1f}")

    def days_for(k):
        out = []
        for t in tr.itertuples():
            pts = t.pts - (SLIP if t.result in ("GANADA", "PERDIDA") else 0)
            pnl = pts * PV * k - COM * k
            mae = (66.5 + SLIP) * PV * k + COM * k if t.result == "PERDIDA" else max(0.0, 0 if np.isnan(t.mae) else t.mae) * PV * k + COM * k
            out.append((pnl, mae))
        return out
    D = {k: days_for(k) for k in (1, 2, 3, 4)}
    print("\nPor operación: 1 MNQ gana ~$%.0f / pierde ~$%.0f" % (66.5 * PV - COM - SLIP * PV, -(66.5 + SLIP) * PV - COM))
    rows = []
    for ke in (1, 2, 3, 4):
        ev = [(s, L.evaluacion(D[ke], s)) for s in range(len(D[ke]))]
        ev = [(s, r) for s, r in ev if r[0] is not None]
        p = np.mean([r[0] for _, r in ev]); dp = np.median([r[1] for _, r in ev if r[0]]); dE = np.mean([r[1] for _, r in ev])
        for kf in (1, 2, 3):
            for rmin in (500, 1000):
                fr = [LR.fondeada(D[kf], s + r[1], retiro_min=rmin) for s, r in ev if r[0] and s + r[1] < len(D[kf])]
                cob = np.array([x[0] for x in fr]); n1 = np.mean([x[1] >= 1 for x in fr]); dF = np.mean([x[2] for x in fr])
                firsts = [x[3] for x in fr if x[3]]
                evacc = p * cob.mean() - L.FEE
                rows.append({"eval MNQ": ke, "fondeada MNQ": kf, "retiro": "$500" if rmin == 500 else "$1,000",
                             "pasa %": round(100 * p, 1), "ops a fondear": int(dp), "1+ retiro %": round(100 * n1, 1),
                             "ops al 1er retiro": int(np.median(firsts)) if firsts else None,
                             "cobran (total) %": round(100 * p * n1, 1), "ganancia/cuenta $": round(evacc),
                             "$/operación": round(evacc / (dE + p * dF), 2)})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(t.sort_values("ganancia/cuenta $", ascending=False).to_string(index=False))
    t.to_csv("backtest/resultados/lucid_nq.csv", index=False)


if __name__ == "__main__":
    main()
