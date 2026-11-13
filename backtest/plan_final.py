#!/usr/bin/env python3
"""Datos del plan final para el tablero: 8:30 contra Londres, 10:30 con tendencia ("Evitar días malos") y SMC 5 min
(desde la apertura de NY, R:R mínimo 1.5), 1 MNQ cada una, una posición a la vez. Más el resumen de Lucid 25K Flex.

Requiere: backtest/resultados/tres_estrategias_ops.csv y mejoras_1030_smc_ops.csv.
Salida: backtest/resultados/plan_final_ops.csv y plan_final_lucid.csv
    python3 backtest/plan_final.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import retiro_rapido as rr  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

PV, COM = 2.0, 1.24
CDMX = "Etc/GMT+6"


def main():
    a = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry", "exit"])
    a = a[a.est == "A 8:30"].copy()
    a["estrategia"] = "8:30 contra Londres"
    a["resultado"] = np.where(a.R >= 1.2, "TP", np.where(a.R <= -0.99, "SL", "Cierre"))
    b = pd.read_csv("backtest/resultados/mejoras_1030_smc_ops.csv", parse_dates=["entry", "exit"])
    bad = b["Último quiebre de 5 min en contra"].fillna(False).astype(bool) | b["ES diverge (SMT)"].fillna(False).astype(bool)
    aplus = b["Último quiebre de 5 min es CHoCH a favor"].fillna(False).astype(bool) | \
        b["POC dentro de un FVG a favor"].fillna(False).astype(bool) | b["POC dentro de un OB"].fillna(False).astype(bool)
    b["aplus"] = aplus & ~bad
    b = b[~bad].copy()
    b["estrategia"] = "10:30 con tendencia"
    b["resultado"] = np.where(b.R >= 0.99, "TP", np.where(b.R <= -0.99, "SL", "Cierre"))
    nq = load("backtest/datos_NQ")
    s = sm.run(resample(nq, 5), 180, "FVG", False, "nuevo extremo", 1.5, entry_from=570)
    c = pd.DataFrame({"entry": s.entry_time.dt.tz_convert("UTC"), "exit": s.exit_time.dt.tz_convert("UTC"), "dir": s.side,
                      "pts": s.R * s.risk, "R": s.R, "mae": s.risk})
    c["estrategia"] = "SMC 5 min"
    c["resultado"] = s.how.map({"TP": "TP", "SL": "SL", "CIERRE": "Cierre"}).values
    for x in (a, b):
        x["entry"] = pd.to_datetime(x.entry, utc=True); x["exit"] = pd.to_datetime(x.exit, utc=True)
    cols = ["estrategia", "entry", "exit", "dir", "resultado", "pts", "R", "mae"]
    T = pd.concat([a[cols], b[cols], c[cols]], ignore_index=True).sort_values("entry").reset_index(drop=True)
    keep, busy = [], None
    for r in T.itertuples():
        ok = busy is None or r.entry >= busy
        keep.append(ok)
        if ok:
            busy = r.exit
    T["tomada"] = keep
    T["usd"] = (T.pts * PV - COM).round(2)
    T["fecha"] = T.entry.dt.tz_convert(CDMX).dt.strftime("%Y-%m-%d")
    T["hora"] = T.entry.dt.tz_convert(CDMX).dt.strftime("%H:%M")
    T["direccion"] = np.where(T.dir == 1, "Compra", "Venta")
    T["temporada"] = np.where(T.entry.dt.tz_convert("America/New_York").map(lambda x: x.utcoffset() == pd.Timedelta(hours=-4)), "Verano", "Invierno")
    out = T[T.tomada][["fecha", "hora", "estrategia", "direccion", "resultado", "pts", "R", "usd", "temporada"]].copy()
    out["pts"] = out.pts.round(2); out["R"] = out.R.round(3)
    out.to_csv("backtest/resultados/plan_final_ops.csv", index=False)
    print(out.groupby("estrategia").agg(ops=("usd", "size"), acierto=("usd", lambda u: round(100 * (u > 0).mean(), 1)),
                                         neto=("usd", "sum"), R_op=("R", "mean")).round(2).to_string())
    print("Total", len(out), "neto", round(out.usd.sum()))

    # Lucid: fondeada (las tres x1) y evaluación (10:30 x1, x3 "Solo A+")
    allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
    T["d"] = pd.to_datetime(T.fecha).dt.date

    def daylist(t, k):
        g = {d: [] for d in allday}
        for r in t.itertuples():
            if r.d in g:
                g[r.d].append(("x", (r.pts * PV - COM) * k, (r.mae * PV + COM) * k))
        return [g[d] for d in allday]

    rows = []
    bt = T[T.tomada]
    b_all = b.assign(d=pd.to_datetime(b.entry).dt.tz_convert(CDMX).dt.date)
    for name, t, k in (("Fondeada: las tres ×1 MNQ", bt, 1), ("Evaluación: 10:30 ×1 MNQ", b_all, 1),
                       ("Evaluación: 10:30 ×3 MNQ, solo A+", b_all[b_all.aplus], 3)):
        dl = daylist(t, k)
        DD = [(sum(p for _, p, _ in o), sum(m for _, _, m in o)) for o in dl]
        ev = [(s_, L.evaluacion(DD, s_)) for s_ in range(len(DD))]; ev = [(s_, r_) for s_, r_ in ev if r_[0] is not None]
        fr = [rr.sim(dl, lambda bb, e: 1, s_) for s_ in range(0, len(dl) - 120)]; fr = [f for f in fr if f[0] is not None]
        ok = [f[1] for f in fr if f[0]]
        rows.append({"plan": name, "pasa_evaluacion_pct": round(100 * np.mean([r_[0] for _, r_ in ev]), 1),
                     "dias_para_pasar": float(np.median([r_[1] for _, r_ in ev if r_[0]])),
                     "llega_1er_retiro_pct": round(100 * np.mean([f[0] for f in fr]), 1),
                     "dias_1er_retiro": float(np.median(ok)) if ok else None})
    Lc = pd.DataFrame(rows)
    Lc.to_csv("backtest/resultados/plan_final_lucid.csv", index=False)
    print(Lc.to_string(index=False))


if __name__ == "__main__":
    main()
