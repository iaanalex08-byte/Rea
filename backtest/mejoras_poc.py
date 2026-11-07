#!/usr/bin/env python3
"""Mejoras a la estrategia de retroceso al POC (SL 13 / R:R 1.5): confirmación, filtro del día anterior,
salida única a 1R y perfil de 15 min. Dentro de muestra 2024-2025, fuera de muestra 2026. Resultados en R.

    python3 backtest/mejoras_poc.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from variantes import stats  # noqa: E402

VARS = {
    "Actual (SL 13, R:R 1.5)": [],
    "Confirmación (cierre a favor)": ["--confirm"],
    "Salida única a 1R (R:R 1.0)": ["--rr", "1.0"],
    "Perfil 15 min": ["--prof-dur", "15", "--win-start", "09:15"],
    "Filtro: rango de ayer <= 2 %": ["#prev2"],
    "Filtro: rango de ayer <= 1.5 %": ["#prev1.5"],
    "Confirmación + R:R 1.0": ["--confirm", "--rr", "1.0"],
    "R:R 1.0 + rango de ayer <= 2 %": ["--rr", "1.0", "#prev2"],
    "Perfil 15 + rango de ayer <= 2 %": ["--prof-dur", "15", "--win-start", "09:15", "#prev2"],
}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data])
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[(df.index >= pd.Timestamp("2023-12-20", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    daily = df.groupby(df.index.date).agg(o=("open", "first"), h=("high", "max"), l=("low", "min"))
    prev = ((daily.h - daily.l) / daily.o * 100).shift(1)
    df = df[df.index >= pd.Timestamp("2024-01-01", tz=base.tz)]
    rows = []
    for name, extra in VARS.items():
        flt = [x for x in extra if x.startswith("#prev")]
        args = [x for x in extra if not x.startswith("#")]
        a = pb.parse_args([data] + args)
        d, _ = pb.filter_days(df, a)
        tr, _ = pb.run(d, a)
        if flt:
            lim = float(flt[0][5:])
            tr = tr[tr.date.map(lambda x: prev.get(x, 0) <= lim)]
        y = pd.to_datetime(tr.date).dt.year
        si, so, st = stats(tr[y <= 2025]), stats(tr[y == 2026]), stats(tr)
        rows.append({"variante": name, "ops": st["ops"], "%TP1": round(st["tp1"], 1), "%TP2": round(st["tp2"], 1),
                     "%SL": round(st["perd"], 1), "R 24-25": round(si["pts"] / a.sl, 1), "R 2026": round(so["pts"] / a.sl, 1),
                     "R total": round(st["pts"] / a.sl, 1), "PF": round(st["pf"], 2), "DD R": round(st["dd"] / a.sl, 1)})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.to_string(index=False))
    out.to_csv("backtest/resultados/mejoras_poc.csv", index=False)


if __name__ == "__main__":
    main()
