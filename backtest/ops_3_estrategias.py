#!/usr/bin/env python3
"""Operaciones del plan para el dashboard: 8:30 contra Londres (noche >= 40), 10:30 con tendencia ("Evitar días malos")
y SMC 5 min. 1 MNQ cada una, con comisión; cuenta propia (pueden estar abiertas al mismo tiempo).

Salida: backtest/resultados/ops_3_estrategias.csv  [estrategia, fecha, hora, direccion, resultado, pts, R, usd]
    python3 backtest/ops_3_estrategias.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import retroceso_1100 as rf  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

COM, CDMX = 1.24, "Etc/GMT+6"


def main():
    nq = rf.bars()
    tm = nq.index.hour * 60 + nq.index.minute
    o00 = nq.groupby(nq.index.date).open.first()
    c829 = nq[tm < 510].groupby(nq[tm < 510].index.date).close.last()
    night = (c829 - o00).abs()
    rows = []
    a = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry"])
    a = a[a.est == "A 8:30"]
    a = a[[night.get(pd.Timestamp(d).date(), 0) >= 40 for d in a.date]]
    rows.append(pd.DataFrame({"estrategia": "8:30 contra Londres", "t": pd.to_datetime(a.entry, utc=True), "dir": a.dir, "pts": a.pts, "R": a.R,
                              "resultado": np.where(a.R >= 1.2, "TP", np.where(a.R <= -0.99, "SL", "Cierre"))}))
    b = pd.read_csv("backtest/resultados/mejoras_1030_smc_ops.csv")
    bad = b["Último quiebre de 5 min en contra"].fillna(False).astype(bool) | b["ES diverge (SMT)"].fillna(False).astype(bool)
    b = b[~bad]
    rows.append(pd.DataFrame({"estrategia": "10:30 con tendencia", "t": pd.to_datetime(b.entry, utc=True), "dir": b.dir, "pts": b.pts, "R": b.R,
                              "resultado": np.where(b.R >= 0.99, "TP", np.where(b.R <= -0.99, "SL", "Cierre"))}))
    s = sm.run(resample(load("backtest/datos_NQ"), 5), 180, "FVG", False, "nuevo extremo", 1.5, entry_from=570)
    rows.append(pd.DataFrame({"estrategia": "SMC 5 min", "t": s.entry_time.dt.tz_convert("UTC"), "dir": s.side, "pts": s.R * s.risk, "R": s.R,
                              "resultado": s.how.map({"TP": "TP", "SL": "SL", "CIERRE": "Cierre"}).values}))
    T = pd.concat(rows, ignore_index=True).sort_values("t")
    loc = T.t.dt.tz_convert(CDMX)
    T["fecha"] = loc.dt.strftime("%Y-%m-%d"); T["hora"] = loc.dt.strftime("%H:%M")
    T["direccion"] = np.where(T.dir == 1, "Compra", "Venta")
    T["usd"] = (T.pts * 2 - COM).round(2); T["pts"] = T.pts.round(2); T["R"] = T.R.round(3)
    T["id"] = T.fecha + " " + T.hora + " " + T.estrategia
    out = T[["id", "estrategia", "fecha", "hora", "direccion", "resultado", "pts", "R", "usd"]]
    out.to_csv("backtest/resultados/ops_3_estrategias.csv", index=False)
    print(out.groupby("estrategia").usd.agg(["size", "sum"]).round())
    print("ids únicos:", out.id.is_unique)


if __name__ == "__main__":
    main()
