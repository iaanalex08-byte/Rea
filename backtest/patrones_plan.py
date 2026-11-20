#!/usr/bin/env python3
"""¿Qué tienen en común las operaciones buenas y malas del plan (8:30 + 10:30 + SMC)? NQ 2024-2026.

Variables por día: día de la semana, noticia (CPI, NFP, PPI, FOMC), movimiento de 00:00 a 8:30 CDMX (tamaño y
si la operación va a favor), volatilidad (rango medio de 10 días vs. 60 días), gap de apertura, y el resultado de la
operación anterior del mismo día. Cada grupo con R/op en 2024-25 y 2026 por separado.

    python3 backtest/patrones_plan.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import noticias as nt  # noqa: E402
from apertura_ny_fvg import load  # noqa: E402

CDMX = "Etc/GMT+6"


def daily_features():
    nq = load("backtest/datos_NQ")
    nq.index = nq.index.tz_convert(CDMX)
    tm = nq.index.hour * 60 + nq.index.minute
    d = nq.index.date
    g = nq.groupby(d)
    f = pd.DataFrame({"o00": g.open.first()})
    pre = nq[tm < 510].groupby(d[tm < 510])
    f["c830"] = pre.close.last()
    rth = nq[(tm >= 510) & (tm < 900)].groupby(d[(tm >= 510) & (tm < 900)])
    f["rth_o"] = rth.open.first(); f["rth_h"] = rth.high.max(); f["rth_l"] = rth.low.min(); f["rth_c"] = rth.close.last()
    f = f.dropna()
    f["noche"] = f.c830 - f.o00
    rng = f.rth_h - f.rth_l
    f["vol_ratio"] = rng.shift(1).rolling(10).mean() / rng.shift(1).rolling(60).mean()
    f["gap"] = f.rth_o - f.rth_c.shift(1)
    f.index = pd.to_datetime(f.index)
    news = set(nt.FOMC + nt.CPI + nt.NFP + nt.PPI)
    f["noticia"] = [x.strftime("%Y-%m-%d") in news for x in f.index]
    return f


def tabla(T, col, titulo):
    g = T.groupby(col, observed=True)
    out = pd.DataFrame({"ops": g.size(), "acierto %": (100 * g.ganó.mean()).round(1), "R/op": g.R.mean().round(3),
                        "R/op 24-25": T[T.y <= 2025].groupby(col, observed=True).R.mean().round(3),
                        "R/op 2026": T[T.y == 2026].groupby(col, observed=True).R.mean().round(3),
                        "neto $": g.usd.sum().round()})
    print(f"\n{titulo}"); print(out.to_string())


def main():
    P = pd.read_csv("backtest/resultados/plan_final_ops.csv")
    P["f"] = pd.to_datetime(P.fecha)
    P["y"] = P.f.dt.year
    P["ganó"] = P.usd > 0
    P["dir"] = np.where(P.direccion == "Compra", 1, -1)
    F = daily_features()
    T = P.join(F, on="f")
    T["dow"] = T.f.dt.day_name().map({"Monday": "1 lun", "Tuesday": "2 mar", "Wednesday": "3 mié", "Thursday": "4 jue", "Friday": "5 vie"})
    T["a favor de la noche"] = np.where(np.sign(T.noche) == T.dir, "a favor", "en contra")
    T["tamaño noche"] = pd.qcut(T.noche.abs(), 3, labels=["chico", "medio", "grande"])
    T["volatilidad"] = pd.cut(T.vol_ratio, [0, 0.85, 1.15, 9], labels=["baja (<0.85)", "normal", "alta (>1.15)"])
    T["gap"] = pd.cut(T.gap.abs(), [-1, 50, 150, 1e9], labels=["< 50 pts", "50-150", "> 150"])
    T["noticia"] = np.where(T.noticia, "día de noticia", "normal")
    T = T.sort_values(["fecha", "hora"])
    T["anterior hoy"] = "primera del día"
    prev = T.groupby("fecha").usd.shift(1)
    T.loc[prev.notna(), "anterior hoy"] = np.where(prev[prev.notna()] > 0, "después de ganar", "después de perder")
    pd.set_option("display.width", 220)
    for col in ("estrategia", "dow", "noticia", "volatilidad", "gap", "anterior hoy"):
        tabla(T, col, f"Por {col}:")
    for est in T.estrategia.unique():
        x = T[T.estrategia == est]
        tabla(x, "a favor de la noche", f"{est} — dirección vs. movimiento 00:00-8:30:")
        tabla(x, "tamaño noche", f"{est} — tamaño del movimiento 00:00-8:30:")
        tabla(x, "volatilidad", f"{est} — volatilidad:")
        tabla(x, "anterior hoy", f"{est} — operación anterior del día:")
        tabla(x, "dow", f"{est} — día:")
    T.to_csv("backtest/resultados/patrones_plan.csv", index=False)


if __name__ == "__main__":
    main()
