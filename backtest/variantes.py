#!/usr/bin/env python3
"""Compara variantes de la estrategia: elige en 2024-2025 (dentro de muestra) y valida en 2026 (fuera de muestra).

    python3 backtest/variantes.py backtest/datos
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

VARIANTES = {
    "Actual (SL 9, R:R 2.5)": [],
    "TP2 a R:R 1.5": ["--rr", "1.5"],
    "TP2 a R:R 1.75": ["--rr", "1.75"],
    "TP2 a R:R 2": ["--rr", "2"],
    "Sin BE tras parcial": ["--no-be"],
    "SL 7": ["--sl", "7"],
    "SL 11": ["--sl", "11"],
    "SL 13": ["--sl", "13"],
    "Retroceso <= 15 min": ["--max-wait", "15"],
    "Tendencia >= 8 pts": ["--min-trend", "8"],
    "Rango perfil >= 7 pts": ["--min-range", "7"],
    "Ruptura solo cierre": ["--brk-mode", "cierre"],
    "Ventana hasta 11:00": ["--win-end", "11:00"],
    "R:R 1.5 + retroceso <= 15": ["--rr", "1.5", "--max-wait", "15"],
    "R:R 1.5 + tendencia >= 8": ["--rr", "1.5", "--min-trend", "8"],
    "R:R 1.5 + ret. <= 15 + tend. >= 8": ["--rr", "1.5", "--max-wait", "15", "--min-trend", "8"],
    "R:R 1.75 + ret. <= 15 + tend. >= 8": ["--rr", "1.75", "--max-wait", "15", "--min-trend", "8"],
    "SL 11, R:R 1.5": ["--sl", "11", "--rr", "1.5"],
}


def stats(tr):
    if tr.empty:
        return dict(ops=0)
    c = tr.result.value_counts()
    w, be, l = c.get("GANADA", 0), c.get("PARCIAL + BE", 0) + c.get("PARCIAL + SL", 0), c.get("PERDIDA", 0)
    cl = w + be + l
    pts = tr.pts
    gp, gl = pts[pts > 0].sum(), -pts[pts < 0].sum()
    eq = pts.cumsum()
    return dict(ops=len(tr), tp2=100 * w / cl, tp1=100 * (w + be) / cl, perd=100 * l / cl,
                pts=pts.sum(), pf=gp / gl if gl else float("nan"), dd=(eq - eq.cummax().clip(lower=0)).min())


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    base = pb.parse_args([data])
    df = pb.load_bars(base.csv, base.input_tz, base.tz, base.tf, base.nt_tz)
    df = df[df.index >= pd.Timestamp("2024-01-01", tz=base.tz)]
    rows = []
    for name, extra in VARIANTES.items():
        a = pb.parse_args([data] + extra)
        d, _ = pb.filter_days(df, a)
        tr, _ = pb.run(d, a)
        y = pd.to_datetime(tr.date).dt.year
        s_in, s_out = stats(tr[y <= 2025]), stats(tr[y == 2026])
        rows.append({"variante": name,
                     "IS ops": s_in["ops"], "IS %TP1": s_in["tp1"], "IS %TP2": s_in["tp2"], "IS %perd": s_in["perd"],
                     "IS pts": s_in["pts"], "IS PF": s_in["pf"],
                     "OOS ops": s_out["ops"], "OOS %TP1": s_out["tp1"], "OOS %TP2": s_out["tp2"],
                     "OOS pts": s_out["pts"], "OOS PF": s_out["pf"], "Total pts": s_in["pts"] + s_out["pts"],
                     "DD pts": stats(tr)["dd"]})
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print("IS = 2024-2025 (dentro de muestra), OOS = 2026 (fuera de muestra). Puntos por contrato.")
    print(out.round(1).to_string(index=False))
    out.to_csv(Path("backtest/resultados") / "variantes.csv", index=False)


if __name__ == "__main__":
    main()
