#!/usr/bin/env python3
"""Ya fondeado (cuenta de 25K con pérdida máx. $1,000): ¿conviene seguir con la SP500 9:00 o pasar al plan del NQ?

Cuenta fondeada modelada como Lucid 25K Flex (verificar las reglas de tu firma): pérdida máx. $1,000 EOD (se fija
en +$100); retiro tras 5 días de >= $100 de ganancia: se retira el 50 % de la ganancia (mín. $500, máx. $1,000) y se
cobra el 90 %. Se mide, empezando cada día hábil, lo cobrado en 12 meses (252 días hábiles) y si la cuenta se quema.

    python3 backtest/roi_fondeada.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402

ALL = pd.bdate_range("2024-01-02", "2026-11-06").date


def daylist(df):
    g = df.groupby(pd.to_datetime(df.fecha).dt.date).agg(p=("p", "sum"), m=("m", "sum")).reindex(ALL, fill_value=0.0)
    return list(zip(g.p.to_numpy(), g.m.to_numpy()))


def nq(k):
    o = pd.read_csv("backtest/resultados/ops_3_estrategias.csv")
    risk = (o.pts / o.R.replace(0, np.nan)).abs().fillna(66.5)
    return daylist(o.assign(p=o.usd * k, m=np.where(o.usd <= 0, (risk * 2 + 1.24) * k, 0.0)))


def sp(path, var, mes):
    o = pd.read_csv(path); o = o[o.variante == var]
    return daylist(o.assign(p=o.usd * mes / 2, m=np.where(o.usd <= 0, -o.usd * mes / 2, 0.0)))


def main():
    cases = {"Plan NQ (8:30 + 10:30 + SMC), 1 MNQ c/u": nq(1),
             "SP500 9:00 parcial + 2R, 1 MES": sp("backtest/resultados/sp500_0900_ops.csv", "Parcial 1:1 + BE + 2R", 1),
             "SP500 9:00 parcial + 2R, 2 MES": sp("backtest/resultados/sp500_0900_ops.csv", "Parcial 1:1 + BE + 2R", 2),
             "SP500 9:00 1:1.5, 2 MES": sp("backtest/resultados/sp500_900_15_ops.csv", "1:1.5", 2),
             "SP500 9:00 1:1.5, 13 MES ($1,000 de riesgo)": sp("backtest/resultados/sp500_900_15_ops.csv", "1:1.5", 13)}
    L.DD, L.LOCK = 1000, 100
    rows = []
    for nm, days in cases.items():
        res = []
        for s in range(0, len(days) - 252):
            c, n, blown = L.fondeada(days[s:s + 252], 0, 100)
            res.append((c, n, blown))
        c = np.array([r[0] for r in res]); n = np.array([r[1] for r in res]); b = np.array([r[2] for r in res])
        rows.append({"estrategia en la fondeada": nm, "cobrado en 12 meses (prom.)": round(c.mean()), "mediana": round(np.median(c)),
                     "retiros (prom.)": round(n.mean(), 1), "llega a 1 retiro %": round(100 * (n >= 1).mean(), 1),
                     "se quema en el año %": round(100 * b.mean(), 1), "cobra $0 %": round(100 * (c == 0).mean(), 1)})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/roi_fondeada.csv", index=False)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
