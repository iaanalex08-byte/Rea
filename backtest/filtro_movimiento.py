#!/usr/bin/env python3
"""Filtro: no operar si antes de la entrada (11:00) el mercado ya se movió mucho.
Entrada 11:00, tendencia 00:00->7:00, cierre 14:30, 8 MES, TP 4 / SL 20.75. Velas de 1 min.

    python3 backtest/filtro_movimiento.py backtest/datos
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid  # noqa: E402
import poc_backtest as pb  # noqa: E402
from ventanas_tendencia import sim  # noqa: E402

K, COM = 40, 9.92
UMBRALES = [None, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
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
        j7 = int(np.searchsorted(tm, 7 * 60)) - 1
        mv = C[j7] - O[0]
        if mv == 0:
            continue
        d = 1 if mv > 0 else -1
        r, p = sim(H, L, O, tm, i, d)
        j830 = int(np.searchsorted(tm, 8 * 60 + 30))
        mae = 0.0
        rows.append({"date": str(day), "anio": day.year, "r": r, "usd": p * K - COM,
                     "mae_usd": (20.75 * K + COM) if r == "L" else max(0.0, -p * K) + COM,
                     "mov_dia": abs(C[i - 1] - O[0]) / O[0] * 100,
                     "rango_dia": (H[:i].max() - L[:i].min()) / O[0] * 100,
                     "mov_ny": abs(C[i - 1] - O[j830]) / O[j830] * 100,
                     "contra": (C[i - 1] - O[0]) * d < 0})
    t = pd.DataFrame(rows)
    t.to_csv("backtest/resultados/filtro_movimiento.csv", index=False)
    cfg = SimpleNamespace(dd=1000, lock=100, objetivo=1250, min_dia=150, dias=5, tope=1000, min_retiro=500, split=0.9)

    def stats(x):
        w, l = (x.r == "W").sum(), (x.r == "L").sum()
        return w / (w + l) if w + l else np.nan, l

    out = []
    for medida in ["mov_dia", "rango_dia", "mov_ny"]:
        for u in UMBRALES:
            if u is None and medida != "mov_dia":
                continue
            s = t if u is None else t[t[medida] <= u]
            a1, _ = stats(s[s.anio <= 2025]); a2, _ = stats(s[s.anio == 2026]); at, l = stats(s)
            days = list(zip(s.usd.to_numpy(), s.mae_usd.to_numpy()))
            runs = [x for x in (lucid.account(days, k, cfg, False) for k in range(len(days))) if x]
            n = np.array([x[2] for x in runs])
            out.append({"filtro": "Sin filtro" if u is None else f"{medida} <= {u}%", "días": len(s),
                        "% días operados": round(100 * len(s) / len(t), 1), "acierto 24-25": round(100 * a1, 1),
                        "acierto 2026": round(100 * a2, 1), "acierto total": round(100 * at, 1), "SL": l,
                        "neto": round(s.usd.sum()), "P(5 TP antes SL)": round(100 * at ** 5, 1),
                        "cuentas con retiro %": round(100 * np.mean(n >= 1), 1)})
    o = pd.DataFrame(out)
    pd.set_option("display.width", 250)
    print(o.to_string(index=False))
    print("\nDías saltados con mov_dia > 1.5%:")
    big = t[t.mov_dia > 1.5]
    print(big.r.value_counts().to_dict(), "| de ellos, a favor/en contra de la regla:", big.contra.value_counts().to_dict())
    print("\nPor dirección del movimiento del día respecto a la operación:")
    for c, g in t.groupby("contra"):
        acc, l = stats(g); print(("Mañana en CONTRA de la operación" if c else "Mañana A FAVOR de la operación"), len(g), "días, acierto", round(100 * acc, 1), "SL", l)
    o.to_csv("backtest/resultados/filtro_movimiento_resumen.csv", index=False)


if __name__ == "__main__":
    main()
