#!/usr/bin/env python3
"""Evaluación Lucid 25K Flex con la 10:30 a ~$400 de riesgo (3 MNQ) y fondeada con SMC.

Usa las operaciones de backtest/resultados/tres_estrategias_ops.csv (correr antes tres_estrategias.py).
    python3 backtest/plan_400.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import lucid_rapidez as LR  # noqa: E402

PV, COM = 2.0, 1.24
T = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry", "exit"])
T["date"] = pd.to_datetime(T.date).dt.date
DATES = sorted(set(T.date))


def days(k, rule="sin solapar"):
    t = T[T.est.map(k) > 0].sort_values("entry")
    keep, busy = [], None
    for r in t.itertuples():
        if busy is not None and r.entry < busy:
            continue
        keep.append(r.Index); busy = r.exit
    t = t.loc[keep]
    q = t.est.map(k)
    x = pd.DataFrame({"date": t.date, "u": t.pts * PV * q - COM * q, "m": t.mae * PV * q + COM * q}).groupby("date").sum()
    x = x.reindex(DATES).fillna(0)
    return list(zip(x.u, x.m))


def evaluacion(k):
    D = days(k)
    ev = [(s, L.evaluacion(D, s)) for s in range(len(D))]
    ev = [(s, r) for s, r in ev if r[0] is not None]
    ok = [r for _, r in ev if r[0]]
    trades_to = []
    return D, ev, np.mean([r[0] for _, r in ev]), np.median([r[1] for r in ok]), np.median([r[1] for _, r in ev if not r[0]] or [0])


def fondeada(D, starts):
    fr = [LR.fondeada(D, s) for s in starts if s < len(D)]
    n1 = np.mean([f[1] >= 1 for f in fr]); cob = np.mean([f[0] for f in fr])
    first = [f[3] for f in fr if f[3]]
    return n1, cob, (np.median(first) if first else np.nan)


K = lambda a=0, b=0, c=0: {"A 8:30": a, "B 10:30": b, "C SMC": c}
print("=== Evaluación (solo 10:30) ===")
evals = {}
for q in (1, 2, 3):
    D, ev, p, dpass, dfail = evaluacion(K(b=q))
    evals[q] = ev
    print(f"10:30 x{q} MNQ (riesgo ${66.5 * 2 * q:.0f}): pasa {100 * p:.1f}% | días hábiles para pasar (mediana) {dpass:.0f} | si se quema, a los {dfail:.0f} días")
print("\n=== Fondeada empezando el día siguiente a pasar con 10:30 x3 ===")
starts = [s + r[1] for s, r in evals[3] if r[0]]
p3 = np.mean([r[0] for _, r in evals[3]])
rows = []
for name, k in (("SMC x1", K(c=1)), ("SMC x2", K(c=2)), ("SMC x3", K(c=3)), ("10:30 x1", K(b=1)),
                ("8:30 + 10:30 + SMC x1", K(1, 1, 1)), ("8:30 + 10:30 x2", K(2, 2))):
    n1, cob, f1 = fondeada(days(k), starts)
    rows.append({"fondeada": name, "1+ retiro %": round(100 * n1, 1), "cobrado prom $": round(cob),
                 "días al 1er retiro": f1, "ganancia esperada por cuenta $": round(p3 * cob - L.FEE)})
print(pd.DataFrame(rows).to_string(index=False))
