#!/usr/bin/env python3
"""Días hábiles promedio para el primer retiro, por estrategia y combinadas (NQ 2024-2026).

A) Lucid 25K Flex fondeada, 1 MNQ por estrategia: retiro = 5 días de >= $100 y >= $1,000 de ganancia
   sin tocar la caída de $1,000 (EOD, se fija en +$100). Se prueba empezando cada día hábil posible.
B) Cuenta propia con $500 de riesgo por operación: días para juntar +$1,000 y +$2,500 de ganancia.

    python3 backtest/dias_retiro.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import retiro_rapido as rr  # noqa: E402

COM = 1.24
CASOS = {"8:30 sola": ["8:30 contra Londres"], "10:30 sola": ["10:30 con tendencia"], "SMC sola": ["SMC 5 min"],
         "8:30 + 10:30": ["8:30 contra Londres", "10:30 con tendencia"],
         "8:30 + 10:30 + SMC": ["8:30 contra Londres", "10:30 con tendencia", "SMC 5 min"]}


def main():
    o = pd.read_csv("backtest/resultados/ops_3_estrategias.csv")
    risk = (o.pts / o.R.replace(0, np.nan)).abs().fillna(66.5)
    o["mae1"] = np.where(o.usd <= 0, risk * 2 + COM, 0.0)
    o["q500"] = np.clip(np.floor(500 / (risk * 2 + COM)), 1, 50)
    o["usd500"] = o.usd * o.q500
    allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
    o["d"] = pd.to_datetime(o.fecha).dt.date
    rows = []
    for nm, ests in CASOS.items():
        x = o[o.estrategia.isin(ests)]
        g = {d: [] for d in allday}
        for r in x.itertuples():
            g[r.d].append((r.estrategia, r.usd, r.mae1))
        days = [g[d] for d in allday]
        res = [rr.sim(days, lambda bal, e: 1, s) for s in range(0, len(days) - 120)]
        res = [r for r in res if r[0] is not None]
        ok = [n for f, n in res if f]
        day500 = pd.Series({d: 0.0 for d in allday})
        for d, v in x.groupby("d").usd500.sum().items():
            day500[d] = v
        v = day500.to_numpy()
        def reach(target):  # noqa: E306
            out = []
            for s in range(0, len(v) - 120):
                c = np.cumsum(v[s:])
                hit = np.flatnonzero(c >= target)
                if len(hit):
                    out.append(hit[0] + 1)
            return out
        r1, r2 = reach(1000), reach(2500)
        rows.append({"estrategia": nm, "Lucid: llega al 1er retiro %": round(100 * len(ok) / len(res), 1),
                     "Lucid: días (mediana)": int(np.median(ok)), "Lucid: días (promedio)": round(np.mean(ok)),
                     "Lucid: días (peor 10 %)": int(np.percentile(ok, 90)),
                     "$500: días a +$1,000 (mediana)": int(np.median(r1)), "$500: promedio": round(np.mean(r1)),
                     "$500: días a +$2,500 (mediana)": int(np.median(r2)), "$500: promedio ": round(np.mean(r2))})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/dias_retiro.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
