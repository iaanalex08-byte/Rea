#!/usr/bin/env python3
"""Entrada 11:00 (cierre 14:30): regla de tendencia 00:00->7:00 vs 00:00->11:00.
Genera operaciones diarias y Monte Carlo (bandas de 1 año, resumen).

    python3 backtest/reglas_mc.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from ventanas_tendencia import sim  # noqa: E402

K, COM = 40, 9.92
REGLAS = {"00:00→7:00": 7 * 60, "00:00→11:00": 11 * 60}
DIAS_MC, SIMS = 250, 10000


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("backtest/resultados")
    a = pb.parse_args([data, "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    df = pb.load_bars([data], a.input_tz, a.tz, 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a.tz))]
    df, _ = pb.filter_days(df, a)
    rows = []
    for day, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] != 0:
            continue
        i = int(np.searchsorted(tm, 11 * 60))
        if i >= len(g) or tm[i] != 11 * 60:
            continue
        O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        res = {d: sim(H, L, O, tm, i, d) for d in (1, -1)}
        for rn, rt in REGLAS.items():
            j = int(np.searchsorted(tm, rt)) - 1
            mv = C[j] - O[0]
            if mv == 0:
                continue
            d = 1 if mv > 0 else -1
            r, p = res[d]
            rows.append({"regla": rn, "date": str(day), "dir": "COMPRA" if d == 1 else "VENTA",
                         "result": {"W": "GANADA", "L": "PERDIDA", "C": "CIERRE"}[r], "usd": round(p * K - COM, 2)})
    t = pd.DataFrame(rows)
    t.to_csv(out / "reglas_operaciones.csv", index=False)
    rng = np.random.default_rng(7)
    bands, summ = [], []
    for rn, g in t.groupby("regla", sort=False):
        u = g.usd.to_numpy()
        paths = rng.choice(u, size=(SIMS, DIAS_MC)).cumsum(axis=1)
        paths = np.concatenate([np.zeros((SIMS, 1)), paths], axis=1)
        q = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
        for k in range(0, DIAS_MC + 1, 5):
            bands.append({"regla": rn, "dia": k, "p5": round(q[0, k]), "p25": round(q[1, k]), "p50": round(q[2, k]),
                          "p75": round(q[3, k]), "p95": round(q[4, k])})
        dd = (paths - np.maximum.accumulate(paths, axis=1)).min(axis=1)
        w, l = (g.result == "GANADA").sum(), (g.result == "PERDIDA").sum()
        summ.append({"regla": rn, "dias": len(g), "acierto": round(w / (w + l), 4), "media_dia": round(u.mean(), 2),
                     "desv_dia": round(u.std(ddof=1), 2), "prob_ganar_1a": round((paths[:, -1] > 0).mean(), 4),
                     "neto_p5": round(np.percentile(paths[:, -1], 5)), "neto_p50": round(np.percentile(paths[:, -1], 50)),
                     "neto_p95": round(np.percentile(paths[:, -1], 95)), "caida_mediana": round(np.median(dd)),
                     "caida_peor5": round(np.percentile(dd, 5)), "prob_5tp_antes_sl": round((w / (w + l)) ** 5, 4)})
    pd.DataFrame(bands).to_csv(out / "reglas_mc_bandas.csv", index=False)
    S = pd.DataFrame(summ)
    S.to_csv(out / "reglas_mc_resumen.csv", index=False)
    print(S.to_string(index=False))
    print(t.groupby("regla").apply(lambda x: (x.dir.values != t[t.regla == '00:00→7:00'].set_index('date').reindex(x.date).dir.values).sum()))


if __name__ == "__main__":
    main()
