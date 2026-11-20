#!/usr/bin/env python3
"""Días mínimos para retiro: ¿qué tamaño, TP y SL maximizan la probabilidad de juntar N días
con ganancia >= mínimo antes de perder la cuenta?

Cuenta con drawdown que se arrastra con la ganancia no realizada (caso más estricto).
Cada día: entrada a mercado (regla de "POC Apertura CDMX - Entrada a mercado"), TP fijo en $, SL
fijo en $; si no se resuelve, se cierra a la hora de cierre. Velas de 1 minuto.

    python3 backtest/dias_minimos.py backtest/datos --min-dia 150 --dd 1000 --dias 5
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

# (ES, MES) -> $ por punto y comisión ida y vuelta (supuestos: ES $4.00, MES $1.24)
COMBOS = [(2, 0), (1, 5), (1, 0), (0, 8), (0, 6), (0, 5), (0, 4), (0, 3), (0, 2), (0, 1)]
COM_ES, COM_MES, TICK = 4.00, 1.24, 0.25


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def entries(df, prof, prof_dur, entry, direction):
    pS, pE, eS = hm(prof), hm(prof) + prof_dur, hm(entry)
    idx = df.index
    O, C = df.open.to_numpy(), df.close.to_numpy()
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    day = idx.day.to_numpy()
    out = []
    for i in range(len(df)):
        if i == 0 or day[i] != day[i - 1]:
            tO, tC, had, done, d, taken = O[i], C[i], False, False, 0, False
        if tm[i] < pS:
            tC = C[i]
        if pS <= tm[i] < pE:
            had = True
        if not done and had and tm[i] >= pE:
            done = True
            d = 1 if tC > tO else (-1 if tC < tO else 0)
        if not taken and done and d != 0 and tm[i] >= eS:
            taken = True
            dd = {"tendencia": d, "contraria": -d, "compra": 1, "venta": -1}[direction]
            out.append((i, dd))
    return out


def day_paths(df, ents, close_at):
    """Para cada entrada: arrays de high/low desde la entrada hasta el cierre del día."""
    idx = df.index
    H, L, O, C = df.high.to_numpy(), df.low.to_numpy(), df.open.to_numpy(), df.close.to_numpy()
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    day = idx.day.to_numpy()
    paths = []
    for i, d in ents:
        j = i
        while j + 1 < len(df) and day[j + 1] == day[i] and tm[j + 1] < close_at:
            j += 1
        paths.append((idx[i].date(), d, O[i], H[i:j + 1], L[i:j + 1], C[j]))
    return paths


def simulate_day(path, k, tp_pts, sl_pts, com):
    """Devuelve (resultado_$, peor caída desde el pico intradía en $, estado)."""
    date, d, e, H, L, cl = path
    tp = e + d * tp_pts
    sl = e - d * sl_pts
    peak = 0.0
    worst = 0.0
    for h, l in zip(H, L):
        fav = (h - e) * d if d == 1 else (e - l)
        adv = (e - l) if d == 1 else (h - e)
        hit_sl = (l <= sl) if d == 1 else (h >= sl)
        hit_tp = (h >= tp) if d == 1 else (l <= tp)
        if hit_sl:  # conservador: si toca ambos, primero el SL
            worst = max(worst, peak + sl_pts * k)
            return -sl_pts * k - com, worst, "SL"
        # pico no realizado antes de la caída de la misma vela (se asume primero el pico)
        peak = max(peak, min(fav, tp_pts) * k)
        worst = max(worst, peak + adv * k)
        if hit_tp:
            return tp_pts * k - com, worst, "TP"
    res = (cl - e) * d * k - com
    return res, worst, "CIERRE"


def campaign(results, start, dd, min_day, n_days):
    """Desde el día start: ¿se juntan n_days días >= min_day antes de romper el drawdown?"""
    bal, peak_bal, good, k = 0.0, 0.0, 0, start
    while k < len(results):
        pnl, worst_from_peak, _ = results[k]
        # el pico de la cuenta incluye la ganancia no realizada del día
        if worst_from_peak >= dd - (peak_bal - bal) and worst_from_peak > 0:
            # caída intradía medida desde el pico de la cuenta
            return False, k - start + 1
        bal += pnl
        peak_bal = max(peak_bal, bal)
        if bal < peak_bal - dd:
            return False, k - start + 1
        if pnl >= min_day:
            good += 1
            if good >= n_days:
                return True, k - start + 1
        k += 1
    return None, k - start


def main():
    p = argparse.ArgumentParser()
    p.add_argument("datos")
    p.add_argument("--min-dia", type=float, default=150)
    p.add_argument("--dd", type=float, default=1000)
    p.add_argument("--dias", type=int, default=5)
    p.add_argument("--prof", default="07:00")
    p.add_argument("--prof-dur", type=int, default=30)
    p.add_argument("--entry", default="08:30")
    p.add_argument("--direction", default="tendencia")
    p.add_argument("--close", default="14:00", help="Cierre forzado si no se resuelve (hora UTC-6)")
    a = p.parse_args()
    base = pb.parse_args([a.datos, "--tf", "1", "--prof-hour", a.prof[:2], "--prof-min", a.prof[3:],
                          "--prof-dur", str(a.prof_dur), "--win-end", "13:30"])
    df = pb.load_bars([a.datos], base.input_tz, base.tz, 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    df, _ = pb.filter_days(df, base)
    paths = day_paths(df, entries(df, a.prof, a.prof_dur, a.entry, a.direction), hm(a.close))
    rows = []
    for es, mes in COMBOS:
        k = es * 50 + mes * 5
        com = es * COM_ES + mes * COM_MES
        tp_pts = math.ceil((a.min_dia + com) / k / TICK) * TICK
        # SL lo más amplio posible sin que el SL + el pico no realizado (hasta el TP) rompan el drawdown
        sl_pts = math.floor((a.dd - tp_pts * k - com) / k / TICK) * TICK
        if sl_pts <= 0:
            continue
        res = [simulate_day(pp, k, tp_pts, sl_pts, com) for pp in paths]
        pnl = np.array([r[0] for r in res])
        st = [r[2] for r in res]
        out = [campaign(res, s, a.dd, a.min_dia, a.dias) for s in range(len(res))]
        done = [o for o in out if o[0] is not None]
        ok = sum(1 for o in done if o[0])
        days_ok = [o[1] for o in done if o[0]]
        rows.append({
            "tamaño": " + ".join(x for x in [f"{es} ES" if es else "", f"{mes} MES" if mes else ""] if x),
            "TP pts": tp_pts, "SL pts": sl_pts, "TP $": round(tp_pts * k - com), "SL $": round(-sl_pts * k - com),
            "%TP": 100 * st.count("TP") / len(st), "%SL": 100 * st.count("SL") / len(st),
            "%cierre": 100 * st.count("CIERRE") / len(st),
            "P 1 semana": 100 * sum(1 for o in done if o[0] and o[1] <= a.dias) / len(done),
            "P 2 semanas": 100 * sum(1 for o in done if o[0] and o[1] <= 2 * a.dias) / len(done),
            "P sin límite": 100 * ok / len(done), "días (mediana)": np.median(days_ok) if days_ok else np.nan,
            "neto/día $": pnl.mean(),
        })
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(f"Mínimo ${a.min_dia:g}/día, drawdown ${a.dd:g}, {a.dias} días | entrada {a.entry} ({a.direction}) | "
          f"{len(paths)} días de 2024-2026, velas de 1 min")
    print(out.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
