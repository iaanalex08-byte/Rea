#!/usr/bin/env python3
"""Exporta los datos del tablero de la estrategia NQ 10:30 (operaciones, días, rejillas) a JSON.

    python3 backtest/dashboard_nq.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

ARGS = ["backtest/datos_NQ", "--prof-hour", "10", "--prof-min", "30", "--win-start", "10:42", "--win-end", "13:30",
        "--sl", "66.5", "--rr", "1.0", "--single"]
SL, PV, QTY, COM = 66.5, 2.0, 2, 1.24
CIERRE = 14 * 60 + 30


def main():
    a = pb.parse_args(ARGS)
    df = pb.load_bars(a.csv, a.input_tz, a.tz, a.tf, a.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]
    d, _ = pb.filter_days(df, a)
    tr, days = pb.run(d, a)
    O, C = d.open.to_numpy(), d.close.to_numpy()
    tm = (d.index.hour * 60 + d.index.minute).to_numpy()
    dates = d.index.date
    ops = []
    for t in tr.itertuples():
        dd = 1 if t.dir == "COMPRA" else -1
        res, pts = t.result, t.pts
        if res in ("SIN RESOLVER", "ABIERTA"):
            # cierre manual a las 14:30 (o al último precio del día)
            i = t.entry_idx
            while i + 1 < len(d) and dates[i + 1] == t.date and tm[i + 1] < CIERRE:
                i += 1
            px = O[i + 1] if i + 1 < len(d) and dates[i + 1] == t.date else C[i]
            res, pts = "CIERRE 14:30", round((px - t.entry) * dd, 2)
        ops.append({"f": str(t.date), "h": t.entry_time.strftime("%H:%M"), "d": "C" if dd == 1 else "V",
                    "e": t.entry, "r": {"GANADA": "G", "PERDIDA": "P"}.get(res, "M"), "p": round(float(pts), 2),
                    "s": t.exit_time.strftime("%H:%M"), "tp": round(float(t.trend_pts), 2),
                    "rg": round(float(t.prof_range), 2)})
    st = {"operó": "op", "sin ruptura": "nr", "ruptura sin retroceso": "nrt", "sin tendencia": "st"}
    dias = [{"f": str(x.date), "s": st.get(x.status, "nr")} for x in days.itertuples()]
    g = pd.read_csv("backtest/resultados/busqueda_poc_NQ.csv")
    g = g[g.tf == 3][["perfil", "SL", "RR", "ops", "winrate", "R_IS", "R_OOS", "R_total", "R_op"]]
    c = pd.read_csv("backtest/resultados/contratendencia_poc.csv")
    c = c[c.activo == "NQ"][["modo", "perfil", "SL", "RR", "ops", "winrate", "R_IS", "R_OOS", "R_total", "R_op"]]
    lu = pd.read_csv("backtest/resultados/lucid_nq.csv")
    out = {"config": {"sl": SL, "rr": 1.0, "pv": PV, "qty": QTY, "com": COM},
           "ops": ops, "dias": dias, "rejilla": g.to_dict("records"), "contra": c.to_dict("records"),
           "lucid": lu.to_dict("records")}
    Path("backtest/resultados/dashboard_nq.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    t = pd.DataFrame(ops)
    print(t.r.value_counts().to_dict(), "días", len(dias), "R", round(t.p.sum() / SL, 1))
    print(t[t.r == "M"].p.describe())


if __name__ == "__main__":
    main()
