#!/usr/bin/env python3
"""Ciclo de fondeo semana a semana: cuánto se cobra (retiros) y cuánto se gana operando cada semana.

Mismas reglas que ciclo_fondeo.py. Para cada tanda de 10 evaluaciones (una cada 5 días hábiles) se registra:
  - el costo de cada evaluación en su semana,
  - cada retiro cobrado (90 %) en la semana en que se pide,
  - la ganancia de trading de las cuentas fondeadas vivas (aún no retirada).
Semanas contadas desde el inicio de la tanda (semana 1 = primera compra), hasta 70 semanas.

Salida: backtest/resultados/ciclo_semanal.csv
    python3 backtest/ciclo_semanal.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import roi_fondeada as R  # noqa: E402
import sp500_fondeo as f  # noqa: E402

FEE, N, GAP, YEAR, WEEKS = 16.70, 10, 5, 252, 70


def fondeada_flujo(days, s0):
    """Como lucid_flex25k.fondeada, pero devuelve [(día, cobro, pnl)] por día."""
    DD, LOCK = 1000, 100
    bal = peak = 0.0; good = 0; out = []
    for k, (pnl, mae) in enumerate(days):
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            out.append((s0 + k, 0.0, max(thr - bal, -mae)))
            break
        bal += pnl; peak = max(peak, bal); good += pnl >= 100
        cobro = 0.0
        if good >= 5 and bal > 0:
            req = min(0.5 * bal, 1000)
            if req >= 500:
                cobro = req * 0.9; bal -= req; good = 0
        out.append((s0 + k, cobro, pnl))
    return out


def main():
    ev = f.days_of("backtest/resultados/sp500_900_15_ops.csv", "1:1.5", 13)
    a = f.ACC["Apex 25K intradía"]
    nq = R.nq(1)
    total = len(ev)
    W = np.zeros((0, 3, WEEKS))
    rows = []
    for k in range(0, total - (N - 1) * GAP - 21 - YEAR):
        w = np.zeros((3, WEEKS))  # costo, cobros, trading
        for i in range(N):
            s = k + i * GAP
            w[0, (s - k) // 5] += FEE
            ok, d = f.evaluacion(ev, s, a)
            if ok:
                for day, cobro, pnl in fondeada_flujo(nq[s + d:s + d + YEAR], s + d):
                    wk = (day - k) // 5
                    if wk < WEEKS:
                        w[1, wk] += cobro; w[2, wk] += pnl
        rows.append(w)
    A = np.array(rows)
    m = A.mean(axis=0)
    D = pd.DataFrame({"semana": np.arange(1, WEEKS + 1), "costo": m[0].round(2), "cobrado": m[1].round(2), "trading": m[2].round(2),
                      "pct_tandas_cobran": ((A[:, 1, :] > 0).mean(axis=0)).round(4),
                      "neto_cobrado_acum": np.cumsum(m[1] - m[0]).round(2)})
    D.to_csv("backtest/resultados/ciclo_semanal.csv", index=False)
    pd.set_option("display.width", 200)
    print(D.head(60).to_string(index=False))
    print("\nPromedio semanas 1-52: cobrado/semana", round(m[1][:52].mean()), "trading/semana", round(m[2][:52].mean()),
          "costo/semana", round(m[0][:52].mean()), "| semanas 11-52:", round(m[1][10:52].mean()))
    print("Semanas con cobro (1-52, prom. por tanda):", round((A[:, 1, :52] > 0).sum(axis=1).mean(), 1))


if __name__ == "__main__":
    main()
