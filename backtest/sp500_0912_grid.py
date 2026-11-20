#!/usr/bin/env python3
"""Estrategia SP500 9:12 (tendencia 00:00-9:00, entrada a mercado): búsqueda de SL, salida, hora y filtro de tendencia.

Resultado en R real de toda la posición, CON comisión (2 MES: $2.48 por operación) y 1 tick de deslizamiento al entrar.
Salidas: 1:1, 1:1.5, 1:2, parcial (mitad a 1:1 + BE + resto a 2R o 3R), sin TP (cierre 15:00).
Robusta = gana en 2024, en 2025 y en 2026 por separado.

    python3 backtest/sp500_0912_grid.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from sp500_0912 import bars  # noqa: E402

TICK, PV, COM, SLIP = 0.25, 5.0, 2.48, 0.25
SALIDAS = {"1:1": ([(1, 1)], False), "1:1.5": ([(1, 1.5)], False), "1:2": ([(1, 2)], False),
           "parcial 1:1 + BE + 2R": ([(0.5, 1), (0.5, 2)], True), "parcial 1:1 + BE + 3R": ([(0.5, 1), (0.5, 3)], True),
           "sin TP (cierre 15:00)": ([(1, None)], False)}


def prep(df):
    days = []
    for d, g in df.groupby(df.index.date):
        if g.index[0].dayofweek >= 5:
            continue
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] > 5:
            continue
        days.append((d, tm, g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()))
    return days


def run(days, sl_t, salida, entry_min, min_trend):
    legs, be = SALIDAS[salida]
    out = []
    for d, tm, O, H, L, C in days:
        if (tm == entry_min).sum() == 0 or (tm < 540).sum() == 0:
            continue
        mv = C[tm < 540][-1] - O[0]
        if abs(mv) < max(min_trend, 0.01):
            continue
        s = 1 if mv > 0 else -1
        i = int(np.flatnonzero(tm == entry_min)[0])
        ent = O[i] + s * SLIP
        risk = sl_t * TICK
        stop = -risk
        open_legs = [[f, (None if r is None else r * risk)] for f, r in legs]
        pnl = 0.0
        for j in range(i, len(C)):
            if tm[j] >= 900:
                px = (O[j] - ent) * s
                pnl += sum(f for f, _ in open_legs) * px; open_legs = []; break
            hi = (H[j] - ent) * s if s == 1 else (ent - L[j])
            lo = (L[j] - ent) * s if s == 1 else (ent - H[j])
            if lo <= stop:  # conservador: primero el stop
                pnl += sum(f for f, _ in open_legs) * stop; open_legs = []; break
            hit = False
            for leg in list(open_legs):
                if leg[1] is not None and hi >= leg[1]:
                    pnl += leg[0] * leg[1]; open_legs.remove(leg); hit = True
            if hit and be:
                stop = max(stop, 0.0)
            if not open_legs:
                break
        if open_legs:
            pnl += sum(f for f, _ in open_legs) * (C[-1] - ent) * s
        r = pnl / risk - COM / (risk * PV * 2)
        out.append((d.year, r))
    return pd.DataFrame(out, columns=["y", "R"])


def main():
    days = prep(bars("backtest/datos"))
    rows = []
    for entry_min, en in ((552, "9:12"), (540, "9:00"), (570, "9:30"), (600, "10:00")):
        for min_trend in (0, 10, 20):
            for sl_t in (20, 30, 40, 60, 80, 120):
                for sal in SALIDAS:
                    t = run(days, sl_t, sal, entry_min, min_trend)
                    if len(t) < 100:
                        continue
                    y = {yy: t.R[t.y == yy].mean() for yy in (2024, 2025, 2026)}
                    eq = t.R.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
                    rows.append({"entrada": en, "tendencia mín (pts)": min_trend, "SL ticks": sl_t, "SL pts": sl_t * TICK, "salida": sal,
                                 "ops": len(t), "acierto %": round(100 * (t.R > 0).mean(), 1), "R/op": round(t.R.mean(), 3),
                                 "R/op 2024": round(y[2024], 3), "R/op 2025": round(y[2025], 3), "R/op 2026": round(y[2026], 3),
                                 "R total": round(t.R.sum(), 1), "caída R": round(dd, 1),
                                 "$/año 2 MES": round(t.R.sum() * sl_t * TICK * PV * 2 / 2.85)})
        print(en, "listo", file=sys.stderr, flush=True)
    T = pd.DataFrame(rows)
    T["robusta (3 años)"] = (T[["R/op 2024", "R/op 2025", "R/op 2026"]] > 0).all(axis=1)
    T.to_csv("backtest/resultados/sp500_0912_grid.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"{len(T)} versiones · ganan los 3 años: {T['robusta (3 años)'].sum()}")
    for col in ("entrada", "tendencia mín (pts)", "SL ticks", "salida"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g["robusta (3 años)"].sum(), "de": g.size(), "R/op prom": g["R/op"].mean().round(3),
                                                    "2024": g["R/op 2024"].mean().round(3), "2025": g["R/op 2025"].mean().round(3), "2026": g["R/op 2026"].mean().round(3)}).to_string())
    print("\nTu versión (9:12, sin filtro, 30 ticks, parcial + 2R):")
    print(T[(T.entrada == "9:12") & (T["tendencia mín (pts)"] == 0) & (T["SL ticks"] == 30) & (T.salida == "parcial 1:1 + BE + 2R")].to_string(index=False))
    print("\n9:12 sin filtro, 30 ticks, 1:1:")
    print(T[(T.entrada == "9:12") & (T["tendencia mín (pts)"] == 0) & (T["SL ticks"] == 30) & (T.salida == "1:1")].to_string(index=False))
    print("\nRobustas (ganan los 3 años), mejores:")
    print(T[T["robusta (3 años)"]].sort_values("R/op", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
