#!/usr/bin/env python3
"""Corre las dos estrategias (POC 9:00 salida única y entrada a mercado 11:00) en otros activos,
escalando SL/TP por la volatilidad relativa al ES (mediana del rango 00:00-14:30 UTC-6).

    python3 backtest/activos.py NQ GC
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

INFO = {"ES": {"tick": 0.25, "micro": "MES", "usd": 5.0, "com": 1.24},
        "NQ": {"tick": 0.25, "micro": "MNQ", "usd": 2.0, "com": 1.24},
        "GC": {"tick": 0.10, "micro": "MGC", "usd": 10.0, "com": 1.24},
        "YM": {"tick": 1.0, "micro": "MYM", "usd": 0.5, "com": 1.24},
        "CL": {"tick": 0.01, "micro": "MCL", "usd": 100.0, "com": 1.24}}
T0, T1 = pd.Timestamp("2024-01-01", tz="Etc/GMT+6"), pd.Timestamp("2026-11-07", tz="Etc/GMT+6")


def carpeta(r):
    return "backtest/datos" if r == "ES" else f"backtest/datos_{r}"


def rtick(x, t):
    return np.floor(x / t + 0.5) * t


def rango_mediano(df1):
    tm = df1.index.hour * 60 + df1.index.minute
    s = df1[tm < 14 * 60 + 30]
    g = s.groupby(s.index.date)
    return float((g.high.max() - g.low.min()).median())


def mercado(df1, tp, sl, tick, entry=11 * 60, close=14 * 60 + 30, contra=False):
    rows = []
    for day, g in df1.groupby(df1.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] != 0:
            continue
        i = int(np.searchsorted(tm, entry))
        if i >= len(g) or tm[i] != entry:
            continue
        O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        j7 = int(np.searchsorted(tm, 7 * 60)) - 1
        if j7 < 0:
            continue
        mv = C[j7] - O[0]
        if mv == 0:
            continue
        d = (1 if mv > 0 else -1) * (-1 if contra else 1)
        e = rtick(O[i], tick)
        tpL, slL = e + d * tp, e - d * sl
        res, pts = "CIERRE", None
        for k in range(i, len(g)):
            if tm[k] >= close:
                pts = (O[k] - e) * d
                break
            if (L[k] <= slL) if d == 1 else (H[k] >= slL):
                res, pts = "PERDIDA", -sl
                break
            if (H[k] >= tpL) if d == 1 else (L[k] <= tpL):
                res, pts = "GANADA", tp
                break
        if pts is None:
            pts = (C[-1] - e) * d
        rows.append({"date": day, "anio": day.year, "result": res, "pts": pts})
    return pd.DataFrame(rows)


def resumen(tr, sl, usd, com, label):
    tr = tr.copy()
    y = tr.anio if "anio" in tr else pd.to_datetime(tr.date).dt.year
    w, l = (tr.result == "GANADA").sum(), (tr.result == "PERDIDA").sum()
    R = tr.pts / sl
    money = tr.pts * usd - com
    return {"prueba": label, "ops": len(tr), "winrate": round(100 * w / (w + l), 1),
            "R 24-25": round(R[y <= 2025].sum(), 1), "R 2026": round(R[y == 2026].sum(), 1),
            "R total": round(R.sum(), 1), "R/op": round(R.mean(), 3), "$ 1 micro": round(money.sum())}


def main():
    raices = sys.argv[1:] or ["NQ", "GC"]
    es1 = pb.load_bars([carpeta("ES")], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    es1 = es1[(es1.index >= T0) & (es1.index < T1)]
    r_es = rango_mediano(es1)
    pd.set_option("display.width", 220)
    for r in ["ES"] + raices:
        inf = INFO[r]
        df1 = es1 if r == "ES" else pb.load_bars([carpeta(r)], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
        df1 = df1[(df1.index >= T0) & (df1.index < T1)]
        ratio = rango_mediano(df1) / r_es
        a1 = pb.parse_args([carpeta(r), "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
        d1, _ = pb.filter_days(df1, a1)
        df3 = df1.resample("3min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        rows = []
        print(f"\n===== {r} | rango típico {rango_mediano(df1):.2f} pts | x{ratio:.2f} del ES | micro {inf['micro']} ${inf['usd']}/pt =====")
        # Estrategia 1: POC 9:00, salida única
        sl0 = rtick(13 * ratio, inf["tick"])
        for mult in (0.7, 1.0, 1.3):
            sl = rtick(sl0 * mult, inf["tick"])
            for rr in (1.0, 1.25, 1.5):
                a = pb.parse_args([carpeta(r), "--single", "--sl", str(sl), "--rr", str(rr), "--mintick", str(inf["tick"])])
                d3, _ = pb.filter_days(df3, a)
                tr, _ = pb.run(d3, a)
                tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
                rows.append(resumen(tr, sl, inf["usd"], inf["com"], f"POC 9:00 SL {sl:g} R:R {rr}"))
        # Estrategia 2: entrada a mercado 11:00
        tp, sl = rtick(4 * ratio, inf["tick"]), rtick(20.75 * ratio, inf["tick"])
        for lab, c in (("tendencia", False), ("contraria", True)):
            tr = mercado(d1, tp, sl, inf["tick"], contra=c)
            s = resumen(tr, sl, inf["usd"], inf["com"], f"11:00 TP {tp:g}/SL {sl:g} ({lab})")
            s["equilibrio"] = round(100 * sl / (sl + tp), 1)
            rows.append(s)
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
