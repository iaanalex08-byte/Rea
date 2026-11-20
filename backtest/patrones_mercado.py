#!/usr/bin/env python3
"""Patrones de la estrategia de entrada a mercado (días mínimos). Velas de 1 min.

    python3 backtest/patrones_mercado.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

TP, SL, TICK = 4.0, 20.75, 0.25
HORAS = ["07:45", "08:00", "08:15", "08:30", "08:45", "09:00", "09:15", "09:30", "10:00", "10:30", "11:00"]


def outcome(H, L, e, d, close_idx):
    tp, sl = e + d * TP, e - d * SL
    for k in range(len(H)):
        if k > close_idx:
            break
        s = L[k] <= sl if d == 1 else H[k] >= sl
        t = H[k] >= tp if d == 1 else L[k] <= tp
        if s:
            return -1
        if t:
            return 1
    return 0


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    a = pb.parse_args([data, "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    df = pb.load_bars([data], a.input_tz, a.tz, 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a.tz))]
    df, _ = pb.filter_days(df, a)
    rows = []
    for day, g in df.groupby(df.index.date):
        tm = g.index.hour * 60 + g.index.minute
        pre = g[tm < 7 * 60]
        if pre.empty or g.iloc[0].name.hour != 0:
            continue
        trend = pre.close.iloc[-1] - g.open.iloc[0]
        if trend == 0:
            continue
        dirT = 1 if trend > 0 else -1
        H, L, O = g.high.to_numpy(), g.low.to_numpy(), g.open.to_numpy()
        close_idx = int(np.searchsorted(tm.to_numpy(), 14 * 60)) - 1
        ny = g.index[0].tz_convert("America/New_York")
        rec = {"date": day, "anio": day.year, "dirT": dirT, "trend_abs": abs(trend),
               "dst": bool(ny.dst()), "dia": pd.Timestamp(day).day_name()}
        on = g[tm < 8 * 60 + 30]
        rec["rango_noche"] = on.high.max() - on.low.min()
        m = g[(tm >= 7 * 60 + 30) & (tm < 8 * 60 + 30)]
        rec["mov_previo"] = (m.close.iloc[-1] - m.open.iloc[0]) * dirT if len(m) else np.nan
        for h in HORAS:
            hh, mm = map(int, h.split(":"))
            i = int(np.searchsorted(tm.to_numpy(), hh * 60 + mm))
            if i >= len(g):
                continue
            e = round(O[i] / TICK) * TICK
            rec[f"L_{h}"] = outcome(H[i:], L[i:], e, 1, close_idx - i)
            rec[f"S_{h}"] = outcome(H[i:], L[i:], e, -1, close_idx - i)
        rows.append(rec)
    t = pd.DataFrame(rows)
    t.to_csv("backtest/resultados/patrones_mercado.csv", index=False)

    def stat(res):
        res = np.asarray(res)
        w, l = (res == 1).sum(), (res == -1).sum()
        acc = w / (w + l) if w + l else np.nan
        return acc, w, l

    def p5(res):
        res = list(res)
        seq = [all(r == 1 for r in res[k:k + 5]) for k in range(len(res) - 4)]
        return np.mean(seq)

    def rule(df_, h, kind):
        if kind == "tendencia":
            return np.where(df_.dirT == 1, df_[f"L_{h}"], df_[f"S_{h}"])
        if kind == "contraria":
            return np.where(df_.dirT == 1, df_[f"S_{h}"], df_[f"L_{h}"])
        if kind == "compra":
            return df_[f"L_{h}"].to_numpy()
        return df_[f"S_{h}"].to_numpy()

    pd.set_option("display.width", 250)
    print(f"{len(t)} días. TP {TP} / SL {SL}. Equilibrio {100 * SL / (SL + TP):.1f}%")
    print("\n--- Hora de entrada y dirección (acierto % 2024-25 / 2026 | P(5 seguidos) total) ---")
    out = []
    for h in HORAS:
        r = {"hora": h}
        for kind in ["tendencia", "contraria", "compra", "venta"]:
            a_ = stat(rule(t[t.anio <= 2025], h, kind))[0]
            b_ = stat(rule(t[t.anio == 2026], h, kind))[0]
            r[kind] = f"{100 * a_:.1f} / {100 * b_:.1f} | {100 * p5(rule(t, h, kind)):.0f}%"
        out.append(r)
    print(pd.DataFrame(out).to_string(index=False))

    base = rule(t, "08:30", "tendencia")
    t["base"] = base

    def by(col, bins=None, name=None):
        x = pd.qcut(t[col], bins) if bins else t[col]
        g = t.groupby(x, observed=True).base
        print(f"\n--- {name or col} (8:30, tendencia) ---")
        print(pd.DataFrame({"días": g.size(), "acierto %": g.apply(lambda s: 100 * stat(s)[0]),
                            "perdidas": g.apply(lambda s: stat(s)[2])}).round(1).to_string())

    by("dst", name="Horario de verano EE. UU. (True = 8:30 CDMX es 10:30 NY; False = 9:30 NY, apertura)")
    by("trend_abs", 4, "Fuerza de la tendencia 00:00-7:00 (pts)")
    by("rango_noche", 4, "Rango 00:00-8:30 (pts)")
    by("mov_previo", 4, "Movimiento 7:30-8:30 a favor de la tendencia (pts)")
    by("dia", name="Día de la semana")


if __name__ == "__main__":
    main()
