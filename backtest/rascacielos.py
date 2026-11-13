#!/usr/bin/env python3
"""Estrategia "Rascacielos" en NQ: TP chico, SL enorme, entrada a la apertura de NY a favor de la tendencia
(EMAs de 15 min) y promediado en contra. 2024-2026, hora ET real, cierre 15:55 ET si no toca nada.

  Dirección: EMA 20 vs EMA 50 de 15 min al cierre de la vela 9:15-9:30 ET.
  Entrada: 1 contrato a la apertura de 9:30 ET.
  Promediado: "sin": nada · "2 iguales": +1 contrato a 1/3 y 2/3 del SL · "martingala": +2 a 1/3 y +4 a 2/3.
  TP: X pts desde el precio promedio. SL: Y pts desde la primera entrada (todo se cierra ahí).
Resultados en $ por MNQ inicial ($2 / pt), con comisión de $1.24 por contrato y 1 tick de deslizamiento.

    python3 backtest/rascacielos.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
from apertura_ny_fvg import load  # noqa: E402

PV, COM, SLIP = 2.0, 1.24, 0.25
ADDS = {"sin": [], "2 iguales": [(1 / 3, 1), (2 / 3, 1)], "martingala": [(1 / 3, 2), (2 / 3, 4)]}


def main():
    nq = load("backtest/datos_NQ")
    c15 = nq.close.resample("15min", label="left", closed="left").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    tm = nq.index.hour * 60 + nq.index.minute
    days = {}
    for d, g in nq[(tm >= 570) & (tm < 955)].groupby(nq[(tm >= 570) & (tm < 955)].index.date):
        if d < pd.Timestamp("2024-01-01").date() or g.index[0].hour * 60 + g.index[0].minute != 570:
            continue
        k = c15.index.searchsorted(g.index[0]) - 1  # última vela de 15 min cerrada (9:15-9:30)
        if k < 50:
            continue
        side = 1 if e20.iloc[k] > e50.iloc[k] else -1
        days[d] = (side, g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy())
    print(f"{len(days)} días", file=sys.stderr)
    rows, keep = [], {}
    for tp in (10, 20, 40):
        for sl in (150, 300, 700):
            for add in ADDS:
                res = []
                for d, (side, O, H, Lw, C) in days.items():
                    e0 = O[0]; pos = [(e0, 1)]; pending = list(ADDS[add])
                    slp = e0 - side * sl
                    out, mae = None, 0.0
                    for i in range(len(O)):
                        # agregar contratos si el precio llega a las zonas de promediado
                        while pending and ((Lw[i] <= e0 - side * pending[0][0] * sl) if side == 1 else (H[i] >= e0 + side * 0 + pending[0][0] * sl)):
                            f, q = pending.pop(0); pos.append((e0 - side * f * sl, q))
                        qty = sum(q for _, q in pos); avg = sum(p * q for p, q in pos) / qty
                        worst = Lw[i] if side == 1 else H[i]
                        mae = max(mae, (avg - worst) * side * qty)
                        if (Lw[i] <= slp) if side == 1 else (H[i] >= slp):
                            out = ((slp - avg) * side * qty, qty); break
                        tpp = avg + side * tp
                        if (H[i] >= tpp) if side == 1 else (Lw[i] <= tpp):
                            out = (tp * qty, qty); break
                    if out is None:
                        qty = sum(q for _, q in pos); avg = sum(p * q for p, q in pos) / qty
                        out = ((C[-1] - avg) * side * qty, qty)
                    pts, qty = out
                    usd = pts * PV - (COM + SLIP * PV) * qty
                    res.append({"date": d, "usd": usd, "mae": mae * PV + COM * qty, "qty": qty, "win": usd > 0})
                t = pd.DataFrame(res)
                y = pd.to_datetime(t.date).dt.year
                keep[(tp, sl, add)] = t
                rows.append({"TP pts": tp, "SL pts": sl, "promediado": add, "ops": len(t), "acierto %": round(100 * t.win.mean(), 1),
                             "gana prom $": round(t.usd[t.win].mean()), "pierde prom $": round(t.usd[~t.win].mean()),
                             "peor op $": round(t.usd.min()), "neto 24-25 $": round(t.usd[y <= 2025].sum()),
                             "neto 2026 $": round(t.usd[y == 2026].sum()), "$/op": round(t.usd.mean(), 1),
                             "pérdida máx posible $": round(sl * PV * (1 + sum(q for _, q in ADDS[add])))})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/rascacielos.csv", index=False)
    pd.set_option("display.width", 250)
    print("Por 1 MNQ inicial:")
    print(T.to_string(index=False))
    # Lucid 25K Flex: solo cabe si la pérdida máxima posible es < $1,000
    print("\nLucid 25K Flex (1 MNQ inicial, solo configuraciones cuya pérdida máxima cabe en el drawdown de $1,000):")
    lr = []
    for (tp, sl, add), t in keep.items():
        maxloss = sl * PV * (1 + sum(q for _, q in ADDS[add]))
        if maxloss >= 1000:
            continue
        D = list(zip(t.usd, t.mae))
        ev = [(s, L.evaluacion(D, s)) for s in range(len(D))]
        ev = [(s, r) for s, r in ev if r[0] is not None]
        lr.append({"TP": tp, "SL": sl, "promediado": add, "pérdida máx $": maxloss,
                   "eval pasa %": round(100 * np.mean([r[0] for _, r in ev]), 1),
                   "días para pasar": float(np.median([r[1] for _, r in ev if r[0]] or [np.nan]))})
    print(pd.DataFrame(lr).to_string(index=False))


if __name__ == "__main__":
    main()
