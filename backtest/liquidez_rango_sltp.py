#!/usr/bin/env python3
"""Rango de acumulación + ruptura + OB/FVG: búsqueda amplia de SL y TP (con validación fuera de muestra).

Entradas iguales a liquidez_rango.py. SL: POI, pierna, mitad del rango, fijo 10-80 pts.
TP: 0.5R-4R o cierre a las 15:00 ET; con o sin breakeven (SL a la entrada al llegar a +1R).
Se elige con 2024-2025 y se comprueba en 2026 (fuera de muestra).

    python3 backtest/liquidez_rango_sltp.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from liquidez_rango import BUF, COST, fills_for  # noqa: E402

SLS = ("POI", "pierna", "mitad rango", "10", "15", "20", "30", "40", "60", "80")
TPS = ("0.5", "0.75", "1", "1.5", "2", "3", "4", "cierre")


def evaluate(df, fills, sl_mode, tp_mode, be):
    H, L, O = df.high.to_numpy(), df.low.to_numpy(), df.open.to_numpy()
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    out, busy = [], -1
    for (i, s, edge, far, leg, mid) in fills:
        if i <= busy:
            continue
        stop = {"POI": far - s * BUF, "pierna": leg - s * BUF, "mitad rango": mid}.get(sl_mode)
        if stop is None:
            stop = edge - s * float(sl_mode)
        risk = (edge - stop) * s
        if risk < 4 or risk > 120:
            continue
        tgt = None if tp_mode == "cierre" else edge + s * float(tp_mode) * risk
        j, res, st = i, None, stop
        if (L[i] <= st) if s == 1 else (H[i] >= st):
            res = -risk
        else:
            j = i + 1
            while j < len(H):
                if dates[j] != dates[i] or tm[j] >= 900:
                    res = (O[j] - edge) * s; break
                if (L[j] <= st) if s == 1 else (H[j] >= st):
                    res = (st - edge) * s; break
                if tgt is not None and ((H[j] >= tgt) if s == 1 else (L[j] <= tgt)):
                    res = (tgt - edge) * s; break
                if be and ((H[j] - edge) * s >= risk if s == 1 else (edge - L[j]) >= risk):
                    st = edge
                j += 1
        if res is None:
            continue
        busy = j
        out.append((idx[i], res - COST, risk))
    return pd.DataFrame(out, columns=["t", "pts", "risk"])


def main():
    nq = load("backtest/datos_NQ")
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq, tf)
        for W in (10, 20):
            for M in (2.0, 3.0, 4.0):
                for poi in ("FVG", "OB", "cualquiera"):
                    fl = fills_for(df, W, M, poi)
                    for slm in SLS:
                        for tpm in TPS:
                            for be in (False, True):
                                if be and tpm in ("0.5", "0.75", "1"):
                                    continue
                                t = evaluate(df, fl, slm, tpm, be)
                                if len(t) < 60:
                                    continue
                                R = t.pts / t.risk; y = t.t.dt.year
                                eq = (t.pts * 2).cumsum()
                                rows.append({"tf": tf, "W": W, "M": M, "POI": poi, "SL": slm, "TP": tpm, "BE": be,
                                             "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.pts > 0).mean(), 1),
                                             "R/op": round(R.mean(), 3), "R/op 24-25": round(R[y <= 2025].mean(), 3),
                                             "R/op 2026": round(R[y == 2026].mean(), 3), "n 2026": int((y == 2026).sum()),
                                             "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85), "peor DD $": round((eq.cummax() - eq).max())})
            print(f"{tf} min W={W} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/liquidez_rango_sltp.csv", index=False)
    pd.set_option("display.width", 250)
    T["robusta"] = (T["R/op 24-25"] > 0) & (T["R/op 2026"] > 0)
    print(f"{len(T)} versiones · robustas: {T.robusta.sum()} ({100 * T.robusta.mean():.1f} %)")
    for col in ("SL", "TP", "BE"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "acierto": g["acierto %"].mean().round(1),
                                                    "R/op 24-25": g["R/op 24-25"].mean().round(3), "R/op 2026": g["R/op 2026"].mean().round(3)}).to_string())
    # Fuera de muestra: las 20 mejores de 2024-25 (>= 30 ops/año), ¿cómo les fue en 2026?
    top = T[T["ops/año"] >= 30].sort_values("R/op 24-25", ascending=False).head(20)
    print("\nTop 20 elegidas con 2024-25 -> resultado en 2026:")
    print(top.drop(columns=["robusta"]).to_string(index=False))
    print(f"\nPromedio R/op de esas 20 en 2026: {top['R/op 2026'].mean():.3f}; positivas: {(top['R/op 2026'] > 0).sum()}/20")


if __name__ == "__main__":
    main()
