#!/usr/bin/env python3
"""Superficies de sensibilidad (para el modelo 3D del dashboard). NQ 2024-2026, 1 MNQ con comisión.

  8:30 contra Londres (noche >= 40 pts): SL x R:R
  10:30 con tendencia (sin el filtro de días malos): SL x R:R
  SMC 5 min: TP fijo en R x riesgo máximo permitido (pts)
Salida: backtest/resultados/superficie_3est.csv [estrategia, x_nombre, x, y_nombre, y, ops, winrate, neto, r_op, caida, actual]

    python3 backtest/superficie_3est.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import busqueda_total as bt  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

COM = 1.24
SLS = [30, 45, 55, 66.5, 80, 90, 110]
RRS = [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


def row(est, xn, x, yn, y, usd, R, actual):
    eq = usd.cumsum()
    return {"estrategia": est, "x_nombre": xn, "x": x, "y_nombre": yn, "y": y, "ops": len(usd), "winrate": round(float((usd > 0).mean()), 4),
            "neto": round(float(usd.sum()), 2), "r_op": round(float(np.mean(R)), 4), "caida": round(float((eq.cummax().clip(lower=0) - eq).max()), 2),
            "actual": actual}


def main():
    night, judas = bt.night_moves()
    rows = []
    for est, h, modo, filt, cur in (("8:30 contra Londres", "08:30", "contra Londres", True, (66.5, 1.25)),
                                    ("10:30 con tendencia", "10:30", "a favor", False, (66.5, 1.0))):
        for sl in SLS:
            for rr in RRS:
                t = bt.poc(h, sl, rr, modo, judas)
                if filt:
                    t = t[[night.get(d, 0) >= 40 for d in t.date]]
                rows.append(row(est, "SL (pts)", sl, "R:R", rr, (t.pts * 2 - COM).reset_index(drop=True), t.R, (sl, rr) == cur))
        print(est, "listo", file=sys.stderr, flush=True)
    m5 = resample(load("backtest/datos_NQ"), 5)
    old = sm.MAX_RISK
    for mx in (40, 60, 80, 100, 120, 150):
        sm.MAX_RISK = mx
        for tp in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
            s = sm.run(m5, 180, "FVG", False, f"{tp:g}", 0, entry_from=570)
            rows.append(row("SMC 5 min", "TP (R)", tp, "Riesgo máx. (pts)", mx, (s.R * s.risk * 2 - COM).reset_index(drop=True), s.R, False))
    sm.MAX_RISK = old
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/superficie_3est.csv", index=False)
    pd.set_option("display.width", 200)
    for e, g in T.groupby("estrategia"):
        print(e); print(g.pivot(index="y", columns="x", values="neto").round().to_string())


if __name__ == "__main__":
    main()
