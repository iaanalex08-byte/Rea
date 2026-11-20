#!/usr/bin/env python3
"""Reversión a las 9:00: tendencia 00:00 -> 9:00, perfil 9:00-9:09 (3 velas de 3 min) y entrada CONTRA la tendencia.
Compara con a favor, varias duraciones de perfil, SL y R:R, en NQ y ES (2024-2026, salida única).

    python3 backtest/reversion_900.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

T0, T1 = "2024-01-01", "2026-11-07"
ACT = {"NQ": ("backtest/datos_NQ", [46.0, 66.5, 87.0]), "ES": ("backtest/datos", [9.0, 13.0, 17.0])}
RRS = [1.0, 1.25, 1.5, 2.0]
DURS = [9, 12, 15]
MODOS = {"a favor": "no", "contra (invertida)": "dir", "contra (fade)": "fade"}


def main():
    rows = []
    for act, (path, sls) in ACT.items():
        a0 = pb.parse_args([path, "--tf", "3"])
        df = pb.load_bars(a0.csv, a0.input_tz, a0.tz, 3, a0.nt_tz)
        df = df[(df.index >= pd.Timestamp(T0, tz=a0.tz)) & (df.index < pd.Timestamp(T1, tz=a0.tz))]
        for dur in DURS:
            ws = 9 * 60 + dur
            argv = [path, "--tf", "3", "--prof-hour", "9", "--prof-min", "0", "--prof-dur", str(dur),
                    "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--single"]
            d, _ = pb.filter_days(df, pb.parse_args(argv))
            for modo, flag in MODOS.items():
                for sl in sls:
                    for rr in RRS:
                        a = pb.parse_args(argv + ["--sl", str(sl), "--rr", str(rr), "--contra", flag])
                        tr, _ = pb.run(d, a)
                        tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
                        y = pd.to_datetime(tr.date).dt.year
                        R = tr.pts / sl
                        rows.append({"activo": act, "perfil": f"9:00-{ws // 60}:{ws % 60:02d}", "modo": modo, "SL": sl, "RR": rr,
                                     "ops": len(tr), "acierto": round(100 * (tr.result == "GANADA").mean(), 1),
                                     "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
                                     "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
            print(f"{act} perfil {dur} min listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/reversion_900.csv", index=False)
    pd.set_option("display.width", 220)
    g = T.groupby(["activo", "perfil", "modo"])
    print(pd.DataFrame({"R/op prom": g.R_op.mean().round(3), "acierto prom": g.acierto.mean().round(1),
                        "positivas": g.R_total.apply(lambda s: (s > 0).sum()),
                        "robustas": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum())}).to_string())
    print("\nTu idea exacta: perfil 9:00-9:09, contra (invertida)")
    for act in ACT:
        print(T[(T.activo == act) & (T.perfil == "9:00-9:09") & (T.modo == "contra (invertida)")].to_string(index=False))
    print("\nMejores robustas por activo")
    for act in ACT:
        x = T[(T.activo == act) & (T.R_IS > 0) & (T.R_OOS > 0)].sort_values("R_total", ascending=False)
        print(x.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
