#!/usr/bin/env python3
"""SP500 entrada 9:00 a favor de la tendencia 00:00-9:00 (>= 20 pts), SL 60 ticks (15 pts), con R:R 1:2 y 1:3.
Variantes: TP completo a 2R / 3R, y parcial (mitad a 1:1 + BE) con el resto a 2R / 3R.
2 MES por operación ($150 de riesgo), comisión $2.48 y 1 tick de deslizamiento incluidos.

Salida: backtest/resultados/sp500_0900_ops.csv  [variante, fecha, direccion, R, usd]
    python3 backtest/sp500_0900_ops.py [552]   (552 = entrada 9:12)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

g.SALIDAS["1:3"] = ([(1, 3)], False)
VARS = {"1:2": "1:2", "1:3": "1:3", "Parcial 1:1 + BE + 2R": "parcial 1:1 + BE + 2R", "Parcial 1:1 + BE + 3R": "parcial 1:1 + BE + 3R"}
SL_T = 60
ENTRY = int(sys.argv[1]) if len(sys.argv) > 1 else 540  # minutos CDMX: 540 = 9:00, 552 = 9:12


def main():
    days = g.prep(bars("backtest/datos"))
    rows = []
    for nm, key in VARS.items():
        legs, be = g.SALIDAS[key]
        for d, tm, O, H, L, C in days:
            sub = [(d, tm, O, H, L, C)]
            t = g.run(sub, SL_T, key, ENTRY, 20)
            if t.empty:
                continue
            mv = C[tm < 540][-1] - O[0]
            r = float(t.R.iloc[0])
            rows.append({"variante": nm, "fecha": d.isoformat(), "direccion": "Compra" if mv > 0 else "Venta",
                         "R": round(r, 4), "usd": round(r * SL_T * g.TICK * g.PV * 2, 2)})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/sp500_0900_ops.csv" if ENTRY == 540 else f"backtest/resultados/sp500_{ENTRY // 60}{ENTRY % 60:02d}_ops.csv", index=False)
    for nm, x in T.groupby("variante"):
        eq = x.usd.cumsum(); print(nm, len(x), round(x.R.mean(), 3), round(x.usd.sum()), "caída", round((eq.cummax().clip(lower=0) - eq).max()))


if __name__ == "__main__":
    main()
