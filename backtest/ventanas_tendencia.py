#!/usr/bin/env python3
"""Compara ventanas para medir la tendencia (00:00 -> 7:00 / 10:00 / 10:30 / 11:00) para cada hora de entrada.
Entrada a mercado, 8 MES, TP 4 / SL 20.75, cierre 14:30, velas de 1 min.

    python3 backtest/ventanas_tendencia.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

TP, SL, K, COM, CLOSE = 4.0, 20.75, 40, 9.92, 14 * 60 + 30
VENTANAS = {"00:00→7:00 (actual)": 7 * 60, "00:00→10:00": 10 * 60, "00:00→10:30": 10 * 60 + 30, "00:00→11:00": 11 * 60}
ENTRADAS = {"10:00": 10 * 60, "10:30": 10 * 60 + 30, "11:00": 11 * 60}


def sim(H, L, O, tm, i, d):
    e = round(O[i] * 4) / 4
    tp, sl = e + d * TP, e - d * SL
    for k in range(i, len(H)):
        if tm[k] >= CLOSE:
            return "C", (O[k] - e) * d
        if (L[k] <= sl) if d == 1 else (H[k] >= sl):
            return "L", -SL
        if (H[k] >= tp) if d == 1 else (L[k] <= tp):
            return "W", TP
    return "C", 0.0


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    a = pb.parse_args([data, "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    df = pb.load_bars([data], a.input_tz, a.tz, 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a.tz))]
    df, _ = pb.filter_days(df, a)
    recs = []
    for day, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] != 0:
            continue
        O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        for en, et in ENTRADAS.items():
            i = int(np.searchsorted(tm, et))
            if i >= len(g) or tm[i] != et:
                continue
            res = {d: sim(H, L, O, tm, i, d) for d in (1, -1)}
            for vn, vt in VENTANAS.items():
                if vt > et:
                    continue  # no se puede medir después de entrar
                j = int(np.searchsorted(tm, vt)) - 1
                mv = C[j] - O[0]
                if mv == 0:
                    continue
                r, p = res[1 if mv > 0 else -1]
                recs.append({"entrada": en, "ventana": vn, "anio": day.year, "r": r, "usd": p * K - COM})
    t = pd.DataFrame(recs)
    rows = []
    for (en, vn), g in t.groupby(["entrada", "ventana"], sort=False):
        def acc(x):
            w, l = (x.r == "W").sum(), (x.r == "L").sum()
            return w / (w + l)
        p = acc(g)
        rows.append({"entrada": en, "tendencia medida": vn, "acierto 24-25": f"{100 * acc(g[g.anio <= 2025]):.1f}%",
                     "acierto 2026": f"{100 * acc(g[g.anio == 2026]):.1f}%", "acierto total": f"{100 * p:.1f}%",
                     "SL": int((g.r == "L").sum()), "neto": f"${g.usd.sum():,.0f}", "P(5 TP antes SL)": f"{100 * p ** 5:.0f}%"})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(out.to_string(index=False))
    out.to_csv("backtest/resultados/ventanas_tendencia.csv", index=False)


if __name__ == "__main__":
    main()
