#!/usr/bin/env python3
"""¿Qué estrategia (o combinación) rinde más con una caída máxima de $2,000? NQ 2024-2026, MNQ con comisión.

Para cada una: neto al año con 1 MNQ, caída máxima, peor día, neto/caída y cuántos MNQ caben con caída <= $2,000.

    python3 backtest/mejor_dd2000.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_1030_inversa as pi  # noqa: E402

PV, COM, YEARS, LIM = 2.0, 1.24, 2.85, 2000


def stats(name, fecha, usd):
    s = pd.DataFrame({"f": pd.to_datetime(fecha), "u": usd}).sort_values("f")
    eq = s.u.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    day = s.groupby(s.f.dt.date).u.sum()
    mon = s.groupby(s.f.dt.to_period("M")).u.sum()
    y = s.f.dt.year
    k = max(1, int(LIM // dd)) if dd > 0 else 10
    return {"estrategia": name, "ops/año": round(len(s) / YEARS), "acierto %": round(100 * (s.u > 0).mean(), 1),
            "neto/año 1 MNQ": round(s.u.sum() / YEARS), "caída máx": round(dd), "peor día": round(day.min()),
            "meses +": f"{(mon > 0).sum()}/{len(mon)}", "neto 2026": round(s.u[y == 2026].sum()),
            "neto/caída": round(s.u.sum() / YEARS / dd, 2), "MNQ con caída ≤ $2k": k,
            "neto/año con esos MNQ": round(k * s.u.sum() / YEARS), "caída con esos MNQ": round(k * dd)}


def main():
    P = pd.read_csv("backtest/resultados/plan_final_ops.csv")
    rows = [stats("Plan 3 estrategias (8:30 + 10:30 + SMC)", P.fecha, P.usd)]
    for e in P.estrategia.unique():
        x = P[P.estrategia == e]; rows.append(stats(e + " (dentro del plan)", x.fecha, x.usd))
    pos = P[P.estrategia != "SMC 5 min"]
    rows.append(stats("8:30 + 10:30 (sin SMC)", pos.fecha, pos.usd))
    D = pd.read_csv("backtest/resultados/estrategia_d_ops.csv")
    rows.append(stats("Primer extremo de la noche (D)", D.date, D.pts * PV - COM))
    for h, sl, rr in (("09:00", 66.5, 2.0), ("09:00", 66.5, 3.0), ("10:30", 66.5, 1.0), ("08:30", 30, 3.0)):
        t = pi.trades(h, sl, rr, "favor")
        rows.append(stats(f"POC {h} a favor SL {sl:g} 1:{rr:g} (sola)", t.date, t.pts * PV - COM))
    T = pd.DataFrame(rows).sort_values("neto/caída", ascending=False)
    T.to_csv("backtest/resultados/mejor_dd2000.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
