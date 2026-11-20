#!/usr/bin/env python3
"""¿Sirve el "Rascacielos" para juntar los días mínimos de Lucid 25K Flex (fondeada)?

Para el primer retiro hacen falta 5 días de >= $100 Y una ganancia >= $1,000 (el retiro es el 50 %, mínimo $500).
Se mide, desde cada día de inicio: probabilidad de llegar al primer retiro antes de tocar el drawdown
($1,000 al cierre del día, se fija en +$100) y cuántos días hábiles tarda.
Rascacielos: entrada 9:30 ET a favor de EMA 20/50 de 15 min, TP chico, SL grande, sin promediar, k MNQ
elegidos para que una ganadora pague >= $100 y una perdedora no pase de $600 (límite diario).

    python3 backtest/rascacielos_dias.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load  # noqa: E402

PV, COM, SLIP = 2.0, 1.24, 0.25
DD, LOCK = 1000.0, 100.0


def primer_retiro(D, start, max_days=400):
    bal = peak = 0.0
    good, k = 0, start
    while k < len(D) and k - start < max_days:
        pnl, mae = D[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - start + 1
        bal += pnl; peak = max(peak, bal); good += pnl >= 100; k += 1
        if good >= 5 and bal >= 1000:
            return True, k - start
    return None, None


def stats(D):
    r = [primer_retiro(D, s) for s in range(len(D) - 100)]
    r = [x for x in r if x[0] is not None]
    ok = [x[1] for x in r if x[0]]
    return 100 * np.mean([x[0] for x in r]), (np.median(ok) if ok else np.nan)


def main():
    nq = load("backtest/datos_NQ")
    c15 = nq.close.resample("15min", label="left", closed="left").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    tm = nq.index.hour * 60 + nq.index.minute
    w = nq[(tm >= 570) & (tm < 955)]
    days = []
    for d, g in w.groupby(w.index.date):
        if d < pd.Timestamp("2024-01-01").date() or g.index[0].hour * 60 + g.index[0].minute != 570:
            continue
        k = c15.index.searchsorted(g.index[0]) - 1
        days.append((d, 1 if e20.iloc[k] > e50.iloc[k] else -1, g.open.values, g.high.values, g.low.values, g.close.values))
    rows = []
    for tp in (13, 18, 26, 35, 52):
        k = int(np.ceil((100 + 1.74 * 8) / (tp * PV)))  # contratos para que la ganadora deje >= $100 neto
        for sl in (25, 50, 75, 100, 150, 270):
            if k * sl * PV > 600:
                continue
            D, wins = [], []
            for d, side, O, H, L, C in days:
                e = O[0]; tpp, slp = e + side * tp, e - side * sl; out, mae = None, 0.0
                for i in range(len(O)):
                    mae = max(mae, (e - (L[i] if side == 1 else H[i])) * side)
                    if (L[i] <= slp) if side == 1 else (H[i] >= slp):
                        out = -sl; break
                    if (H[i] >= tpp) if side == 1 else (L[i] <= tpp):
                        out = tp; break
                if out is None:
                    out = (C[-1] - e) * side
                usd = out * PV * k - (COM + SLIP * PV) * k
                D.append((usd, min(mae, sl) * PV * k + COM * k)); wins.append(out > 0)
            p, dmed = stats(D)
            u = np.array([x[0] for x in D])
            rows.append({"TP pts": tp, "SL pts": sl, "MNQ": k, "gana $": round(tp * PV * k - 1.74 * k), "pierde $": -round(sl * PV * k + 1.74 * k),
                         "acierto %": round(100 * np.mean(wins), 1), "días >= $100 %": round(100 * (u >= 100).mean(), 1),
                         "$/día": round(u.mean(), 1), "llega al 1er retiro %": round(p, 1), "días hábiles": dmed})
    T = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))
    T.to_csv("backtest/resultados/rascacielos_dias.csv", index=False)


if __name__ == "__main__":
    main()
