#!/usr/bin/env python3
"""Filtros para subir el winrate de la estrategia del POC 1:1 (SL 13, salida única). 2024-25 vs 2026.

    python3 backtest/filtros_poc11.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import noticias as nw  # noqa: E402
import poc_backtest as pb  # noqa: E402

BASE = ["--single", "--rr", "1.0"]
VARS = {
    "Actual": [],
    "Retroceso en <= 15 min": ["--max-wait", "15"],
    "Retroceso en <= 30 min": ["--max-wait", "30"],
    "Retroceso en <= 60 min": ["--max-wait", "60"],
    "Tendencia >= 5 pts": ["--min-trend", "5"],
    "Tendencia >= 8 pts": ["--min-trend", "8"],
    "Tendencia >= 12 pts": ["--min-trend", "12"],
    "Ventana hasta 11:00": ["--win-end", "11:00"],
    "Ventana hasta 12:00": ["--win-end", "12:00"],
    "Sin días FOMC": ["#fomc"],
    "Sin días CPI/NFP": ["#cpinfp"],
    "Sin FOMC, CPI, NFP ni PPI": ["#todas"],
    "Tendencia >= 8 + retroceso <= 30": ["--min-trend", "8", "--max-wait", "30"],
    "Tendencia >= 8 + sin FOMC": ["--min-trend", "8", "#fomc"],
}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data] + BASE)
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    excl = {"#fomc": set(nw.FOMC), "#cpinfp": set(nw.CPI) | set(nw.NFP),
            "#todas": set(nw.FOMC) | set(nw.CPI) | set(nw.NFP) | set(nw.PPI)}
    rows = []
    for name, extra in VARS.items():
        flags = [x for x in extra if x.startswith("#")]
        a = pb.parse_args([data] + BASE + [x for x in extra if not x.startswith("#")])
        d, _ = pb.filter_days(df, a)
        tr, _ = pb.run(d, a)
        for f in flags:
            tr = tr[~tr.date.astype(str).isin(excl[f])]
        tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
        y = pd.to_datetime(tr.date).dt.year
        wr = lambda s: 100 * (s.result == "GANADA").mean()
        rows.append({"filtro": name, "ops": len(tr), "winrate 24-25": round(wr(tr[y <= 2025]), 1),
                     "winrate 2026": round(wr(tr[y == 2026]), 1), "winrate total": round(wr(tr), 1),
                     "R total": round(tr.pts.sum() / 13, 1)})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(out.to_string(index=False))
    out.to_csv("backtest/resultados/filtros_poc11.csv", index=False)


if __name__ == "__main__":
    main()
