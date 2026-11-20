#!/usr/bin/env python3
"""Ciclo completo: pasar evaluaciones Apex 25K con la SP500 9:00 (1:1.5, $1,000 de riesgo) y, ya fondeado,
operar el plan del NQ (8:30 + 10:30 + SMC, 1 MNQ c/u) o seguir con la SP500 (parcial + 2R, 2 MES).

Tanda: 10 evaluaciones, una nueva cada 5 días hábiles. Cada cuenta que pasa se fondea al día siguiente y opera 12 meses
(252 días hábiles) con las reglas de retiro tipo Lucid 25K (ver roi_fondeada.py). Costo por evaluación $16.70.
Se repite la tanda empezando en cada día hábil posible de 2024-2026 (cuando hay datos suficientes).

Salidas (backtest/resultados/): ciclo_tandas.csv, ciclo_cuentas.csv, ciclo_resumen.csv
    python3 backtest/ciclo_fondeo.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import roi_fondeada as R  # noqa: E402
import sp500_fondeo as f  # noqa: E402

FEE, N, GAP, YEAR = 16.70, 10, 5, 252


def main():
    ev_days = f.days_of("backtest/resultados/sp500_900_15_ops.csv", "1:1.5", 13)
    a = f.ACC["Apex 25K intradía"]
    funded = {"Plan NQ (1 MNQ c/u)": R.nq(1), "SP500 parcial + 2R (2 MES)": R.sp("backtest/resultados/sp500_0900_ops.csv", "Parcial 1:1 + BE + 2R", 2)}
    L.DD, L.LOCK = 1000, 100
    total = len(ev_days)
    tandas, cuentas = [], []
    for k in range(0, total - (N - 1) * GAP - 21 - YEAR):
        rec = {"inicio": str(pd.bdate_range("2024-01-02", "2026-11-06")[k].date()), "pasan": 0}
        for nm in funded:
            rec[nm] = 0.0
        for i in range(N):
            s = k + i * GAP
            ok, d = f.evaluacion(ev_days, s, a)
            if ok:
                rec["pasan"] += 1
                for nm, days in funded.items():
                    c, n, blown = L.fondeada(days[s + d:s + d + YEAR], 0, 100)
                    rec[nm] += c
                    if k % 5 == 0:
                        cuentas.append({"estrategia": nm, "cobrado": round(c, 2), "retiros": n, "quemada": blown, "dias_eval": d})
        tandas.append(rec)
    T = pd.DataFrame(tandas)
    cost = FEE * N
    for nm in funded:
        T[nm] = T[nm].round(2)
    T.to_csv("backtest/resultados/ciclo_tandas.csv", index=False)
    C = pd.DataFrame(cuentas); C.to_csv("backtest/resultados/ciclo_cuentas.csv", index=False)
    rows = []
    for nm in funded:
        x = T[nm] - cost
        rows.append({"fondeada_con": nm, "tandas": len(T), "costo_tanda": cost, "pasan_prom": round(T.pasan.mean(), 2),
                     "cobrado_prom": round(T[nm].mean()), "cobrado_mediana": round(T[nm].median()), "neto_prom": round(x.mean()),
                     "neto_p10": round(np.percentile(x, 10)), "neto_p90": round(np.percentile(x, 90)), "pierde_pct": round((x < 0).mean(), 4),
                     "roi_prom": round(x.mean() / cost, 2)})
    S = pd.DataFrame(rows); S.to_csv("backtest/resultados/ciclo_resumen.csv", index=False)
    pd.set_option("display.width", 220)
    print(S.to_string(index=False))
    print(T.pasan.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
