#!/usr/bin/env python3
"""POC con salida única (SL 13): rejilla de hora de inicio del perfil x R:R. Velas de 3 min.
Resultados en R: 2024-2025 / 2026 (winrate total).

    python3 backtest/horario_rr_poc.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

HORAS = ["07:30", "08:30", "09:00", "09:30", "10:00", "10:30"]
RRS = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data])
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    cells, rows = {}, []
    for h in HORAS:
        hh, mm = map(int, h.split(":"))
        ws = hh * 60 + mm + 12
        hargs = ["--prof-hour", str(hh), "--prof-min", str(mm), "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--single"]
        d, _ = pb.filter_days(df, pb.parse_args([data] + hargs))
        for rr in RRS:
            a = pb.parse_args([data] + hargs + ["--rr", str(rr)])
            tr, _ = pb.run(d, a)
            y = pd.to_datetime(tr.date).dt.year
            w, l = (tr.result == "GANADA").sum(), (tr.result == "PERDIDA").sum()
            ri, ro = tr.pts[y <= 2025].sum() / a.sl, tr.pts[y == 2026].sum() / a.sl
            cells[(h, rr)] = f"{ri:+.0f}/{ro:+.0f} ({100 * w / (w + l):.0f}%)"
            eq = tr.pts.cumsum()
            rows.append({"hora": h, "rr": rr, "ops": len(tr), "winrate": round(100 * w / (w + l), 1),
                         "equilibrio": round(100 / (1 + rr), 1), "R_24_25": round(ri, 1), "R_2026": round(ro, 1),
                         "R_total": round(ri + ro, 1), "DD_R": round((eq - eq.cummax().clip(lower=0)).min() / a.sl, 1)})
    g = pd.Series(cells).unstack()
    g.index.name = "perfil \\ R:R"
    pd.set_option("display.width", 250)
    print("R 2024-25 / R 2026 (winrate)")
    print(g.to_string())
    out = pd.DataFrame(rows)
    out.to_csv("backtest/resultados/horario_rr_poc.csv", index=False)
    print("\nMejores por R total, positivas en ambos periodos:")
    print(out[(out.R_24_25 > 0) & (out.R_2026 > 0)].sort_values("R_total", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
