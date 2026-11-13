#!/usr/bin/env python3
"""Búsqueda amplia por activo: POC (temporalidad x inicio del perfil x SL x R:R, salida única)
y entrada a mercado (hora x TP x SL). SL/TP escalados por volatilidad relativa al ES.
Se marcan robustas las combinaciones positivas en 2024-2025 y en 2026.

    python3 backtest/busqueda_activos.py GC
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from activos import INFO, T0, T1, carpeta, rango_mediano, rtick, mercado  # noqa: E402

TFS = {1: 12, 3: 12, 5: 15}
PERFILES = ["07:30", "08:30", "09:00", "09:30", "10:00", "10:30"]
SL_ES = [9, 13, 17]
RRS = [1.0, 1.25, 1.5, 2.0]
ENTRADAS = ["08:30", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00"]
TP_ES = [2, 3, 4, 5, 6]
SLM_ES = [15, 20.75, 25]


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def main():
    r = sys.argv[1]
    inf = INFO[r]
    es1 = pb.load_bars([carpeta("ES")], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    es1 = es1[(es1.index >= T0) & (es1.index < T1)]
    df1 = es1 if r == "ES" else pb.load_bars([carpeta(r)], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    df1 = df1[(df1.index >= T0) & (df1.index < T1)]
    ratio = rango_mediano(df1) / rango_mediano(es1)
    print(f"{r}: x{ratio:.2f} del ES", file=sys.stderr)
    poc = []
    for tf, dur in TFS.items():
        dft = df1 if tf == 1 else df1.resample(f"{tf}min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        for p in PERFILES:
            ws = hm(p) + dur
            base = ["--tf", str(tf), "--prof-hour", p[:2], "--prof-min", p[3:], "--prof-dur", str(dur),
                    "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--single", "--mintick", str(inf["tick"])]
            d, _ = pb.filter_days(dft, pb.parse_args([carpeta(r)] + base))
            for sle in SL_ES:
                sl = rtick(sle * ratio, inf["tick"])
                for rr in RRS:
                    a = pb.parse_args([carpeta(r)] + base + ["--sl", str(sl), "--rr", str(rr)])
                    tr, _ = pb.run(d, a)
                    tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
                    if tr.empty:
                        continue
                    y = pd.to_datetime(tr.date).dt.year
                    R = tr.pts / sl
                    poc.append({"tf": tf, "perfil": p, "SL(ES)": sle, "SL": sl, "RR": rr, "ops": len(tr),
                                "winrate": round(100 * (tr.result == "GANADA").mean(), 1),
                                "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
                                "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
            print(f"  POC tf {tf} perfil {p} listo", file=sys.stderr)
    P = pd.DataFrame(poc)
    a1 = pb.parse_args([carpeta(r), "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    d1, _ = pb.filter_days(df1, a1)
    mk = []
    for e in ENTRADAS:
        for tpe in TP_ES:
            for sle in SLM_ES:
                tp, sl = rtick(tpe * ratio, inf["tick"]), rtick(sle * ratio, inf["tick"])
                tr = mercado(d1, tp, sl, inf["tick"], entry=hm(e))
                y = tr.anio
                w, l = (tr.result == "GANADA").sum(), (tr.result == "PERDIDA").sum()
                R = tr.pts / sl
                mk.append({"entrada": e, "TP(ES)": tpe, "SL(ES)": sle, "TP": tp, "SL": sl, "ops": len(tr),
                           "winrate": round(100 * w / (w + l), 1), "equilibrio": round(100 * sl / (sl + tp), 1),
                           "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
                           "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
        print(f"  mercado {e} listo", file=sys.stderr)
    M = pd.DataFrame(mk)
    P.to_csv(f"backtest/resultados/busqueda_poc_{r}.csv", index=False)
    M.to_csv(f"backtest/resultados/busqueda_mercado_{r}.csv", index=False)
    pd.set_option("display.width", 220)
    for name, T in (("POC", P), ("ENTRADA A MERCADO", M)):
        rob = T[(T.R_IS > 0) & (T.R_OOS > 0)]
        print(f"\n===== {r} {name}: {len(rob)} de {len(T)} combinaciones positivas en ambos periodos =====")
        print(rob.sort_values("R_op", ascending=False).head(12).to_string(index=False))
    # resúmenes por dimensión (promedio de R por operación)
    print(f"\n{r} POC: R/op promedio por temporalidad y perfil")
    print(P.pivot_table(index="perfil", columns="tf", values="R_op", aggfunc="mean").round(3).to_string())
    print(f"\n{r} POC: R/op promedio por SL y R:R")
    print(P.pivot_table(index="SL(ES)", columns="RR", values="R_op", aggfunc="mean").round(3).to_string())
    print(f"\n{r} MERCADO: R/op promedio por hora y TP")
    print(M.pivot_table(index="entrada", columns="TP(ES)", values="R_op", aggfunc="mean").round(3).to_string())


if __name__ == "__main__":
    main()
