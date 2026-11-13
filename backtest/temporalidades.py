#!/usr/bin/env python3
"""Perfil a las 9:00 UTC-6: compara temporalidades y duraciones del perfil.
Dentro de muestra 2024-2025, fuera de muestra 2026. Resultados en R.

    python3 backtest/temporalidades.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from variantes import stats  # noqa: E402

DURACIONES = {1: [3, 6, 9, 12, 15, 18, 24, 30], 3: [3, 6, 9, 12, 15, 18, 24, 30],
              5: [5, 10, 15, 20, 25, 30], 6: [6, 12, 18, 24, 30], 9: [9, 18, 27]}
GESTION = {"SL 9 / R:R 2.5": ["--sl", "9", "--rr", "2.5"], "SL 13 / R:R 1.5": ["--sl", "13", "--rr", "1.5"]}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    raw = pb.load_bars([data], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    raw = raw[(raw.index >= pd.Timestamp("2024-01-01", tz="Etc/GMT+6")) & (raw.index < pd.Timestamp("2026-11-05", tz="Etc/GMT+6"))]
    rows = []
    for tf, durs in DURACIONES.items():
        bars = raw if tf == 1 else raw.resample(f"{tf}min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        for dur in durs:
            ws = 9 * 60 + dur
            hargs = ["--tf", str(tf), "--prof-dur", str(dur), "--win-start", f"{ws // 60:02d}:{ws % 60:02d}"]
            d, _ = pb.filter_days(bars, pb.parse_args([data] + hargs))
            for gname, gargs in GESTION.items():
                a = pb.parse_args([data] + hargs + gargs)
                tr, _ = pb.run(d, a)
                y = pd.to_datetime(tr.date).dt.year
                si, so, st = stats(tr[y <= 2025]), stats(tr[y == 2026]), stats(tr)
                rows.append({"vela": f"{tf} min", "perfil": f"{dur} min", "gestión": gname, "ops": st["ops"],
                             "%TP1": st["tp1"], "%TP2": st["tp2"], "R 24-25": si["pts"] / a.sl,
                             "R 2026": so["pts"] / a.sl, "R total": st["pts"] / a.sl, "PF": st["pf"],
                             "DD R": st["dd"] / a.sl})
            print(f"vela {tf} min, perfil {dur} min listo", file=sys.stderr)
    out = pd.DataFrame(rows)
    out.to_csv("backtest/resultados/temporalidades.csv", index=False)
    pd.set_option("display.width", 250)
    for g in GESTION:
        print(f"\n=== {g} ===")
        print(out[out["gestión"] == g].drop(columns="gestión").round(1).to_string(index=False))


if __name__ == "__main__":
    main()
