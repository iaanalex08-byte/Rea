#!/usr/bin/env python3
"""Compara horarios de inicio del perfil (dentro de muestra 2024-2025, fuera de muestra 2026).

    python3 backtest/horarios.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402
from variantes import stats  # noqa: E402

HORARIOS = {
    "9:00 UTC-6 (actual)": ["--prof-hour", "9", "--prof-min", "0", "--win-start", "09:12", "--win-end", "13:30"],
    "8:30 UTC-6": ["--prof-hour", "8", "--prof-min", "30", "--win-start", "08:42", "--win-end", "13:30"],
    "7:30 UTC-6": ["--prof-hour", "7", "--prof-min", "30", "--win-start", "07:42", "--win-end", "13:30"],
    "Apertura NY (9:30 ET, cambia con el horario de EE. UU.)":
        ["--tz", "America/New_York", "--prof-hour", "9", "--prof-min", "30", "--win-start", "09:42", "--win-end", "15:30"],
}
GESTION = {"SL 9 / R:R 2.5": ["--sl", "9", "--rr", "2.5"], "SL 13 / R:R 1.5": ["--sl", "13", "--rr", "1.5"]}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    raw = pb.load_bars([data], "Etc/GMT+6", "UTC", 3, "auto")
    rows, grids = [], {}
    for hname, hargs in HORARIOS.items():
        a0 = pb.parse_args([data] + hargs)
        df = raw.copy()
        df.index = df.index.tz_convert(a0.tz)
        df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a0.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a0.tz))]
        d, _ = pb.filter_days(df, a0)
        for gname, gargs in GESTION.items():
            a = pb.parse_args([data] + hargs + gargs)
            tr, _ = pb.run(d, a)
            y = pd.to_datetime(tr.date).dt.year
            si, so, st = stats(tr[y <= 2025]), stats(tr[y == 2026]), stats(tr)
            rows.append({"horario": hname, "gestión": gname, "ops": st["ops"], "%TP1": st["tp1"], "%TP2": st["tp2"],
                         "%perd": st["perd"], "R 24-25": si["pts"] / a.sl, "R 2026": so["pts"] / a.sl,
                         "R total": st["pts"] / a.sl, "PF": st["pf"], "DD R": st["dd"] / a.sl})
        g = {}
        for sl in [9, 11, 13, 15, 17]:
            for rr in [1.0, 1.25, 1.5, 2.0, 2.5]:
                a = pb.parse_args([data] + hargs + ["--sl", str(sl), "--rr", str(rr)])
                tr, _ = pb.run(d, a)
                y = pd.to_datetime(tr.date).dt.year
                g[(sl, rr)] = f"{tr.pts[y <= 2025].sum() / sl:+.0f}/{tr.pts[y == 2026].sum() / sl:+.0f}"
        grids[hname] = pd.Series(g).unstack()
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.round(1).to_string(index=False))
    for h, g in grids.items():
        g.index.name = "SL \\ R:R"
        print(f"\nR 2024-25 / R 2026 — {h}")
        print(g.to_string())
    out.to_csv("backtest/resultados/horarios.csv", index=False)


if __name__ == "__main__":
    main()
