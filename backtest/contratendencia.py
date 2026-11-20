#!/usr/bin/env python3
"""POC a favor vs contra tendencia en ES, NQ y GC (velas de 3 min, salida única, 2024-2026).

Modos:
  favor : la estrategia normal (dirección = medianoche -> inicio del perfil).
  dir   : dirección invertida (si el día es bajista se buscan compras: ruptura alcista y retroceso al POC).
  fade  : misma ruptura que la normal, pero en el retroceso se entra al revés.
También prueba la entrada a mercado de las 11:00 contra tendencia.

    python3 backtest/contratendencia.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from activos import INFO, T0, T1, carpeta, rango_mediano, rtick, mercado  # noqa: E402

PERFILES = ["07:30", "08:30", "09:00", "09:30", "10:00", "10:30"]
SL_ES = [9, 13, 17]
RRS = [1.0, 1.5, 2.0]
MODOS = {"favor": "no", "dir": "dir", "fade": "fade"}
ELEGIDA = {"ES": ("09:00", 13), "NQ": ("10:30", 13), "GC": ("07:30", 9)}  # configuración actual de cada activo


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def stats(tr, sl):
    tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
    if tr.empty:
        return None
    y = pd.to_datetime(tr.date).dt.year
    R = tr.pts / sl
    return {"ops": len(tr), "winrate": round(100 * (tr.result == "GANADA").mean(), 1),
            "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
            "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)}


def main():
    es1 = pb.load_bars([carpeta("ES")], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    es1 = es1[(es1.index >= T0) & (es1.index < T1)]
    rows, mk = [], []
    for r in ("ES", "NQ", "GC"):
        inf = INFO[r]
        df1 = es1 if r == "ES" else pb.load_bars([carpeta(r)], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
        df1 = df1[(df1.index >= T0) & (df1.index < T1)]
        ratio = rango_mediano(df1) / rango_mediano(es1)
        df3 = df1.resample("3min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        for p in PERFILES:
            ws = hm(p) + 12
            base = ["--tf", "3", "--prof-hour", p[:2], "--prof-min", p[3:], "--prof-dur", "12",
                    "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--single", "--mintick", str(inf["tick"])]
            d, _ = pb.filter_days(df3, pb.parse_args([carpeta(r)] + base))
            for sle in SL_ES:
                sl = rtick(sle * ratio, inf["tick"])
                for rr in RRS:
                    for modo, flag in MODOS.items():
                        a = pb.parse_args([carpeta(r)] + base + ["--sl", str(sl), "--rr", str(rr), "--contra", flag])
                        tr, _ = pb.run(d, a)
                        s = stats(tr, sl)
                        if s:
                            rows.append({"activo": r, "modo": modo, "perfil": p, "SL(ES)": sle, "SL": sl, "RR": rr, **s})
            print(f"{r} perfil {p} listo", file=sys.stderr)
        # entrada a mercado 11:00 (TP 4 / SL 20.75 del ES escalados), a favor y contra
        a1 = pb.parse_args([carpeta(r), "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
        d1, _ = pb.filter_days(df1, a1)
        tp, sl = rtick(4 * ratio, inf["tick"]), rtick(20.75 * ratio, inf["tick"])
        for modo, c in (("favor", False), ("contra", True)):
            tr = mercado(d1, tp, sl, inf["tick"], contra=c)
            w, l = (tr.result == "GANADA").sum(), (tr.result == "PERDIDA").sum()
            R = tr.pts / sl
            mk.append({"activo": r, "modo": modo, "TP": tp, "SL": sl, "ops": len(tr),
                       "winrate": round(100 * w / (w + l), 1), "R_IS": round(R[tr.anio <= 2025].sum(), 1),
                       "R_OOS": round(R[tr.anio == 2026].sum(), 1), "R_total": round(R.sum(), 1)})
    P, M = pd.DataFrame(rows), pd.DataFrame(mk)
    P.to_csv("backtest/resultados/contratendencia_poc.csv", index=False)
    M.to_csv("backtest/resultados/contratendencia_mercado.csv", index=False)
    pd.set_option("display.width", 220)
    print("\n===== Configuración actual de cada activo (RR 1) =====")
    for r, (p, sle) in ELEGIDA.items():
        print(P[(P.activo == r) & (P.perfil == p) & (P["SL(ES)"] == sle) & (P.RR == 1.0)].to_string(index=False))
    print("\n===== Resumen de la rejilla (54 combinaciones por modo) =====")
    g = P.groupby(["activo", "modo"])
    out = pd.DataFrame({"R/op promedio": g.R_op.mean().round(3),
                        "winrate prom": g.winrate.mean().round(1),
                        "positivas": g.R_total.apply(lambda s: (s > 0).sum()),
                        "robustas (IS y OOS > 0)": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum())})
    print(out.to_string())
    print("\n===== Mejores robustas por activo y modo =====")
    for (r, m), x in g:
        rob = x[(x.R_IS > 0) & (x.R_OOS > 0)].sort_values("R_op", ascending=False).head(3)
        if len(rob):
            print(rob.to_string(index=False))
    print("\n===== Entrada a mercado 11:00 =====")
    print(M.to_string(index=False))


if __name__ == "__main__":
    main()
