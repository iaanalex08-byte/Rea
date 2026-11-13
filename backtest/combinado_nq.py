#!/usr/bin/env python3
"""NQ: POC 10:30 (3 min, SL 66.5, 1:1) sola vs combinada con un POC de 8:30 en el mismo día.

Cada operación sin TP ni SL se cierra a las 14:30. Si la de 8:30 sigue abierta cuando entra la de 10:30
se reporta como solapada; la regla "no_solapar" omite esa entrada de 10:30.

    python3 backtest/combinado_nq.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import analisis as an  # noqa: E402
import lucid_flex25k as L  # noqa: E402
import lucid_rapidez as LR  # noqa: E402
import poc_backtest as pb  # noqa: E402

T0, T1 = "2024-01-01", "2026-11-07"
PV, COM, SLIP = 2.0, 1.24, 0.25
CIERRE = 14 * 60 + 30
BASE = {"nombre": "10:30 · 3m · SL 66.5 · 1:1", "tf": 3, "ph": 10, "pm": 30, "dur": 12, "ws": "10:42", "sl": 66.5, "rr": 1.0}
OCHO = [
    {"nombre": "8:30 · 3m · SL 46 · 1:1", "tf": 3, "ph": 8, "pm": 30, "dur": 12, "ws": "08:42", "sl": 46.0, "rr": 1.0},
    {"nombre": "8:30 · 3m · SL 46 · 1:2", "tf": 3, "ph": 8, "pm": 30, "dur": 12, "ws": "08:42", "sl": 46.0, "rr": 2.0},
    {"nombre": "8:30 · 5m · SL 46 · 1:1.5", "tf": 5, "ph": 8, "pm": 30, "dur": 15, "ws": "08:45", "sl": 46.0, "rr": 1.5},
    {"nombre": "8:30 · 5m · SL 46 · 1:1.25", "tf": 5, "ph": 8, "pm": 30, "dur": 15, "ws": "08:45", "sl": 46.0, "rr": 1.25},
]
_cache = {}


def bars(tf):
    if tf not in _cache:
        a = pb.parse_args(["backtest/datos_NQ", "--tf", str(tf)])
        df = pb.load_bars(a.csv, a.input_tz, a.tz, tf, a.nt_tz)
        _cache[tf] = df[(df.index >= pd.Timestamp(T0, tz=a.tz)) & (df.index < pd.Timestamp(T1, tz=a.tz))]
    return _cache[tf]


def trades(c):
    a = pb.parse_args(["backtest/datos_NQ", "--tf", str(c["tf"]), "--prof-hour", str(c["ph"]), "--prof-min", str(c["pm"]),
                       "--prof-dur", str(c["dur"]), "--win-start", c["ws"], "--win-end", "13:30",
                       "--sl", str(c["sl"]), "--rr", str(c["rr"]), "--single"])
    d, _ = pb.filter_days(bars(c["tf"]), a)
    a.dir_map = c.get("dmap")
    tr, _ = pb.run(d, a)
    tr = an.excursions(d, tr)
    O, C = d.open.to_numpy(), d.close.to_numpy()
    tm = (d.index.hour * 60 + d.index.minute).to_numpy()
    dates = d.index.date
    rows = []
    for t in tr.itertuples():
        dd = 1 if t.dir == "COMPRA" else -1
        pts, ext, res = t.pts, t.exit_time, t.result
        if res not in ("GANADA", "PERDIDA") or ext.hour * 60 + ext.minute >= CIERRE:
            i = t.entry_idx
            while i + 1 < len(d) and dates[i + 1] == t.date and tm[i + 1] < CIERRE:
                i += 1
            nxt = i + 1 < len(d) and dates[i + 1] == t.date
            px = O[i + 1] if nxt else C[i]
            pts, res = (px - t.entry) * dd, "CIERRE"
            ext = d.index[i + 1] if nxt else d.index[i]
            mae = max(0.0, 0 if np.isnan(t.mae) else t.mae)
        else:
            mae = c["sl"] if res == "PERDIDA" else max(0.0, 0 if np.isnan(t.mae) else t.mae)
        slip = SLIP if res in ("GANADA", "PERDIDA") else 0
        rows.append({"date": t.date, "entry": t.entry_time, "exit": ext, "dir": dd, "res": res,
                     "pts": pts - slip, "R": pts / c["sl"], "mae": mae + slip})
    return pd.DataFrame(rows)


def money(df, k):
    return df.pts * PV * k - COM * k, df.mae * PV * k + COM * k


def lucid(days_eval, days_fund):
    ev = [(s, L.evaluacion(days_eval, s)) for s in range(len(days_eval))]
    ev = [(s, r) for s, r in ev if r[0] is not None]
    p = np.mean([r[0] for _, r in ev])
    fr = [LR.fondeada(days_fund, s + r[1], retiro_min=500) for s, r in ev if r[0] and s + r[1] < len(days_fund)]
    cob = np.array([x[0] for x in fr]); n1 = np.mean([x[1] >= 1 for x in fr])
    return p, p * n1, p * cob.mean() - L.FEE


def resumen(nombre, ops, k_eval=1, k_fund=2):
    ops = ops.sort_values("entry")
    y = pd.to_datetime(ops.date).dt.year
    wl = ops[ops.res.isin(["GANADA", "PERDIDA"])]
    usd, mae = money(ops, 2)
    g = pd.DataFrame({"date": ops.date, "usd": usd}).groupby("date").usd.sum()
    eq = g.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
    def days(k):
        u, m = money(ops, k)
        x = pd.DataFrame({"date": ops.date, "u": u, "m": m}).groupby("date").agg(u=("u", "sum"), m=("m", "sum"))
        return list(zip(x.u, x.m))
    p, cob, ev = lucid(days(k_eval), days(k_fund))
    return {"estrategia": nombre, "ops": len(ops), "dias_op": g.size, "acierto": round(100 * (wl.res == "GANADA").mean(), 1),
            "R_24_25": round(ops.R[y <= 2025].sum(), 1), "R_2026": round(ops.R[y == 2026].sum(), 1),
            "neto_2MNQ": round(usd.sum()), "max_dd_$": round(dd), "peor_dia_$": round(g.min()),
            "dias<-$600": int((g <= -600).sum()), "lucid_pasa%": round(100 * p, 1), "lucid_cobran%": round(100 * cob, 1),
            "lucid_$cuenta": round(ev)}


def main():
    base = trades(BASE)
    rows = [resumen(BASE["nombre"] + " (sola)", base)]
    extra = []
    for c in OCHO:
        o = trades(c)
        rows.append(resumen(c["nombre"] + " (sola)", o))
        # solapamiento: la de 8:30 sigue abierta cuando entra la de 10:30
        m = base.merge(o[["date", "exit", "dir"]], on="date", how="left", suffixes=("", "_8"))
        sol = m.exit_8.notna() & (m.exit_8 > m.entry)
        opp = sol & (m.dir_8 != m.dir)
        both = pd.concat([o, base])
        rows.append(resumen(c["nombre"] + " + 10:30", both))
        rows.append(resumen(c["nombre"] + " + 10:30 sin solapar", pd.concat([o, base[~sol.to_numpy()]])))
        a = o.groupby("date").R.sum(); b = base.groupby("date").R.sum()
        j = pd.concat([a, b], axis=1, keys=["r8", "r10"]).fillna(0)
        extra.append({"8:30": c["nombre"], "dias con ambas": int(((j.r8 != 0) & (j.r10 != 0)).sum()),
                      "solapadas": int(sol.sum()), "solapadas en contra": int(opp.sum()),
                      "correlación diaria": round(j.r8.corr(j.r10), 2)})
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(t.to_string(index=False))
    print()
    print(pd.DataFrame(extra).to_string(index=False))
    t.to_csv("backtest/resultados/combinado_nq.csv", index=False)


if __name__ == "__main__":
    main()
