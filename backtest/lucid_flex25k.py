#!/usr/bin/env python3
"""Probabilidades para una cuenta Lucid 25K Flex con las estrategias del repo.

Reglas modeladas (de la captura del usuario y fuentes públicas; verificar en Lucid):
- Evaluación: objetivo $1,250; pérdida máxima $1,000 con arrastre de fin de día (se fija en +$100);
  límite de pérdida diaria $600 (ninguna configuración probada lo supera); consistencia 40 %
  (el mejor día no puede ser más del 40 % de la ganancia total al pasar); máximo 20 micros.
- Fondeada: mismo drawdown; retiro tras 5 días con ganancia >= mínimo; se retira el 50 % de la ganancia
  (máx. $1,000, mín. $500) y se cobra el 90 %.
Se rompe la cuenta si el saldo menos la peor pérdida no realizada del día cae por debajo del límite.

    python3 backtest/lucid_flex25k.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import analisis as an  # noqa: E402
import poc_backtest as pb  # noqa: E402

DD, LOCK, TARGET, CONS, FEE = 1000, 100, 1250, 0.40, 45.5
SLIP, COM_MES = 0.25, 1.24


def evaluacion(days, start):
    bal = peak = best = 0.0
    k = start
    while k < len(days):
        pnl, mae = days[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - start + 1
        bal += pnl
        peak = max(peak, bal)
        best = max(best, pnl)
        k += 1
        if bal >= TARGET and best <= CONS * bal:
            return True, k - start
    return None, None


def fondeada(days, start, min_dia, n_dias=5, tope=1000, min_retiro=500, split=0.9):
    bal = peak = 0.0
    good, cobrado, retiros, k = 0, 0.0, 0, start
    while k < len(days):
        pnl, mae = days[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return cobrado, retiros, True
        bal += pnl
        peak = max(peak, bal)
        good += pnl >= min_dia
        k += 1
        if good >= n_dias and bal > 0:
            req = min(0.5 * bal, tope)
            if req >= min_retiro:
                cobrado += req * split
                retiros += 1
                bal -= req
                good = 0
    return cobrado, retiros, False


def poc_days(data, mes):
    a = pb.parse_args([data, "--single", "--rr", "1.0"])
    df = pb.load_bars(a.csv, a.input_tz, a.tz, a.tf, a.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a.tz))]
    d, _ = pb.filter_days(df, a)
    tr, _ = pb.run(d, a)
    tr = an.excursions(d, tr)
    out = []
    for t in tr.itertuples():
        pts = t.pts - (SLIP if t.result in ("GANADA", "PERDIDA") else 0)
        pnl = pts * 5 * mes - COM_MES * mes
        mae = (13 + SLIP) * 5 * mes + COM_MES * mes if t.result == "PERDIDA" else max(0.0, (0 if np.isnan(t.mae) else t.mae)) * 5 * mes + COM_MES * mes
        out.append((pnl, mae))
    return out


def mercado_days(df, mes, tp, sl, entry=11 * 60, close=14 * 60 + 30):
    out = []
    for day, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] != 0:
            continue
        i = int(np.searchsorted(tm, entry))
        if i >= len(g) or tm[i] != entry:
            continue
        O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        j7 = int(np.searchsorted(tm, 7 * 60)) - 1
        mv = C[j7] - O[0]
        if mv == 0:
            continue
        d = 1 if mv > 0 else -1
        e = round(O[i] * 4) / 4
        mae, pts = 0.0, None
        for k in range(i, len(g)):
            if tm[k] >= close:
                pts = (O[k] - e) * d
                break
            adv = (e - L[k]) if d == 1 else (H[k] - e)
            if adv >= sl:
                pts, mae = -(sl + SLIP), sl + SLIP
                break
            mae = max(mae, adv)
            if ((H[k] - e) if d == 1 else (e - L[k])) >= tp:
                pts = tp
                break
        if pts is None:
            pts = (C[-1] - e) * d
        out.append((pts * 5 * mes - COM_MES * mes, mae * 5 * mes + COM_MES * mes))
    return out


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    a1 = pb.parse_args([data, "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    df1 = pb.load_bars([data], a1.input_tz, a1.tz, 1, "auto")
    df1 = df1[(df1.index >= pd.Timestamp("2024-01-01", tz=a1.tz)) & (df1.index < pd.Timestamp("2026-11-05", tz=a1.tz))]
    df1, _ = pb.filter_days(df1, a1)

    print("=== EVALUACIÓN (objetivo $1,250, consistencia 40 %) ===")
    ev = {}
    cands = [(f"POC 1:1 SL 13, {m} MES", ("poc", m)) for m in (2, 3, 4, 5, 6, 8)]
    cands += [("11:00, 5 MES, TP 6 / SL 20.75", ("mkt", 5, 6.0, 20.75)),
              ("11:00, 8 MES, TP 4 / SL 14.75", ("mkt", 8, 4.0, 14.75)),
              ("11:00, 4 MES, TP 8 / SL 20.75", ("mkt", 4, 8.0, 20.75))]
    cache = {}
    for name, c in cands:
        days = poc_days(data, c[1]) if c[0] == "poc" else mercado_days(df1, *c[1:])
        cache[name] = days
        res = [evaluacion(days, s) for s in range(len(days))]
        res = [r for r in res if r[0] is not None]
        p = np.mean([r[0] for r in res])
        med = np.median([r[1] for r in res if r[0]])
        worst = min(x[0] for x in days)
        ev[name] = p
        print(f"{name:34s} pasa {100 * p:5.1f}%  | operaciones hasta pasar (mediana) {med:5.0f} | peor día ${worst:,.0f}")

    print("\n=== FONDEADA: días mínimos (retiro tras 5 días >= mínimo) ===")
    fund = {}
    for name, (mes, tp, sl), md in [("11:00, 8 MES, TP 4 / SL 14.75 (mín. $150)", (8, 4.0, 14.75), 150),
                                    ("11:00, 5 MES, TP 6 / SL 20.75 (mín. $150)", (5, 6.0, 20.75), 140),
                                    ("11:00, 6 MES, TP 4 / SL 18 (mín. $100)", (6, 4.0, 18.0), 100),
                                    ("11:00, 8 MES, TP 4 / SL 20.75 (sin límite diario)", (8, 4.0, 20.75), 150)]:
        days = mercado_days(df1, mes, tp, sl)
        res = [fondeada(days, s, md) for s in range(len(days))]
        cob = np.array([r[0] for r in res]); n = np.array([r[1] for r in res])
        w = sum(1 for x in days if x[0] > 0) / len(days)
        fund[name] = cob.mean()
        print(f"{name:46s} día ganado {100 * w:4.1f}% | 1+ retiro {100 * np.mean(n >= 1):5.1f}% | 2+ {100 * np.mean(n >= 2):5.1f}% | "
              f"3+ {100 * np.mean(n >= 3):5.1f}% | cobro promedio ${cob.mean():,.0f}")
    print("\n=== POC 1:1 también en la fondeada (mín. $100) ===")
    for m in (3, 4, 5):
        days = cache[f"POC 1:1 SL 13, {m} MES"]
        res = [fondeada(days, s, 100) for s in range(len(days))]
        cob = np.array([r[0] for r in res]); n = np.array([r[1] for r in res])
        print(f"POC 1:1 SL 13, {m} MES: 1+ retiro {100 * np.mean(n >= 1):5.1f}% | 2+ {100 * np.mean(n >= 2):5.1f}% | cobro promedio ${cob.mean():,.0f}")


if __name__ == "__main__":
    main()
