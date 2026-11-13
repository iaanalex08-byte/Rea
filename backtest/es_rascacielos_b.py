"""El Rascacielos (entrada 9:30 NY a favor del cruce EMA 20/50 de 15 min) operado en el ES
con la gestión del modelo B: SL 45 · TP1 30 · TP2 60 ticks, 2 contratos, break-even tras TP1.

- 2026: dirección tomada del dashboard "Rascacielos 2026 día por día" (archivo del usuario).
- 2025: dirección reconstruida con el cruce EMA 20/50 de 15 min del Nasdaq (coincide 93% en 2026).
Se compara con el modelo B (9:12 CDMX, EMA 20 de 3 min) con la misma gestión.

    python backtest/es_rascacielos_b.py RASCACIELOS_CSV
"""
import os
import sys

import numpy as np
import pandas as pd

from data import load_m1
from es_analysis_config import trade_detail
from es_backtest import COST_T, NEWS, ROOT, TICK_USD, load

OUT = os.path.join(ROOT, "results", "es", "rascacielos_modelo_b")
SL, TP1, TP2 = 45, 30, 60


def stats(u):
    u = np.asarray(u, float)
    eq = np.cumsum(u)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    bw = ww = rw = rl = 0
    for v in u:
        rw, rl = (rw + 1, 0) if v > 0 else (0, rl + 1)
        bw, ww = max(bw, rw), max(ww, rl)
    gl = -u[u < 0].sum()
    sd = u.std(ddof=1)
    return dict(n=len(u), winrate=(u > 0).mean(), pf=u[u > 0].sum() / gl if gl else np.nan, net=u.sum(), avg=u.mean(),
                maxdd=-dd.min(), best_streak=bw, worst_streak=ww, t=u.mean() / sd * np.sqrt(len(u)),
                avg_win=u[u > 0].mean(), avg_loss=u[u < 0].mean())


def main(rasca_csv):
    os.makedirs(OUT, exist_ok=True)
    es = load()                                     # S&P 500 1m, hora NY
    nq = load_m1(); nq.index = nq.index.tz_localize(None)
    c15 = nq.c.resample("15min").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    ras = pd.read_csv(rasca_csv)
    ras = ras[ras.opero == "Sí"].copy()
    ras["d"] = pd.to_datetime(ras.fecha)
    dir26 = dict(zip(ras.d, np.where(ras.direccion == "Compra", 1, -1)))
    news = set(pd.to_datetime(pd.read_csv(NEWS).date))

    rows = []
    for d, g in es.groupby(es.index.normalize()):
        if d.weekday() >= 5:
            continue
        t0 = d + pd.Timedelta(hours=9, minutes=30)
        if t0 not in g.index:
            continue
        gg = g.loc[t0:d + pd.Timedelta(hours=15, minutes=59)]
        if len(gg) < 30:
            continue
        if d in dir26:
            side, src = dir26[d], "Dashboard Rascacielos"
        elif d.year == 2025:
            k = c15.index[c15.index < t0]
            if not len(k):
                continue
            side, src = (1 if e20[k[-1]] > e50[k[-1]] else -1), "Reconstruida (EMA 20/50 15m)"
        else:
            continue
        e = gg["o"].iloc[0]
        x = trade_detail(e, side, gg, SL, TP1, TP2)
        rows.append(dict(date=d, year=d.year, side="Compra" if side > 0 else "Venta", fuente=src, outcome=x["outcome"],
                         tp1=x["x1"] == "TP1", mins=x["mins"], news=d in news,
                         usd=round(x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD, 2)))
    R = pd.DataFrame(rows)
    R["weekday"] = R.date.dt.weekday.map(dict(enumerate(["Lun", "Mar", "Mié", "Jue", "Vie"])))

    B = pd.read_csv(os.path.join(ROOT, "results", "es", "analisis_B_CDMX_45_30_60", "b45_operaciones.csv"))
    B["date"] = pd.to_datetime(B.date)
    M = R.merge(B[["date", "side", "usd", "outcome"]], on="date", suffixes=("_ras", "_b"))
    M["coinciden"] = M.side_ras == M.side_b

    out = {}
    out["Rascacielos + gestión B (9:30 NY)"] = stats(R.usd)
    for y in (2025, 2026):
        out[f"Rascacielos + gestión B · {y}"] = stats(R[R.year == y].usd)
    out["Modelo B (9:12 CDMX)"] = stats(B.usd)
    for y in (2025, 2026):
        out[f"Modelo B · {y}"] = stats(B[B.date.dt.year == y].usd)
    out["Rascacielos + B solo si coincide la dirección con el modelo B"] = stats(M[M.coinciden].usd_ras)
    out["Modelo B solo si coincide con el Rascacielos"] = stats(M[M.coinciden].usd_b)
    out["Rascacielos + B sin días de noticia"] = stats(R[~R.news].usd)
    S = pd.DataFrame(out).T
    S.to_csv(os.path.join(OUT, "resumen.csv"))
    R.to_csv(os.path.join(OUT, "operaciones.csv"), index=False)

    pd.set_option("display.width", 220)
    print(S[["n", "winrate", "pf", "net", "avg", "maxdd", "best_streak", "worst_streak", "t"]].round(3).to_string())
    print("\nDesenlaces:", R.outcome.value_counts().to_dict(), "| llegan a TP1:", round(R.tp1.mean(), 3))
    print("Coinciden direcciones con modelo B:", round(M.coinciden.mean(), 3))
    print(R.groupby("weekday").agg(n=("usd", "size"), tp1=("tp1", "mean"), net=("usd", "sum")).round(2).to_string())
    print(R.groupby("side").agg(n=("usd", "size"), tp1=("tp1", "mean"), net=("usd", "sum")).round(2).to_string())
    # Rascacielos original (MNQ) 2026 como referencia
    r26 = ras.copy()
    for k in ("80", "50k"):
        u = pd.to_numeric(r26[f"usd_{k}"], errors="coerce").dropna()
        print(f"Rascacielos original 2026 · {k}: n={len(u)} winrate={(u > 0).mean():.3f} neto={u.sum():.0f}")
    print("Comparación 2026 mismos días: Ras+B", round(R[R.year == 2026].usd.sum()))


if __name__ == "__main__":
    main(sys.argv[1])
