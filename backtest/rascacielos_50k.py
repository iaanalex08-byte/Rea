#!/usr/bin/env python3
"""¿Sirve el Rascacielos para cobrar en una cuenta fondeada de 50K? Comparado con el plan del NQ.

Cuenta fondeada tipo Lucid 50K Flex (de la captura del usuario; verificar): pérdida máx. $2,000 EOD (se fija en +$100),
retiro tras 5 días de >= $150. Supuesto de retiro: 50 % de la ganancia, mínimo $500, máximo $2,000, se cobra el 90 %.
Si se quema, se cuenta lo cobrado hasta ahí. 12 meses (252 días hábiles) desde cada día de inicio 2024-2026.

    python3 backtest/rascacielos_50k.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import roi_fondeada as R  # noqa: E402
from apertura_ny_fvg import load  # noqa: E402

DD, LOCK, MIN_DIA, MIN_RET, MAX_RET = 2000, 100, 150, 500, 2000
ALL = pd.bdate_range("2024-01-02", "2026-11-06").date


def rasca(tp, sl, q):
    nq = load("backtest/datos_NQ")
    c15 = nq.close.resample("15min", label="left", closed="left").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    tm = nq.index.hour * 60 + nq.index.minute
    w = nq[(tm >= 570) & (tm < 955)]
    out = {}
    for d, g in w.groupby(w.index.date):
        if d < pd.Timestamp("2024-01-01").date() or g.index[0].hour * 60 + g.index[0].minute != 570:
            continue
        k = c15.index.searchsorted(g.index[0]) - 1
        if k < 50:
            continue
        s = 1 if e20.iloc[k] > e50.iloc[k] else -1
        O, H, L, C = (g[c].to_numpy() for c in ("open", "high", "low", "close"))
        e = O[0]; r = None; mae = 0.0
        for i in range(len(O)):
            mae = max(mae, (e - (L[i] if s == 1 else H[i])) * s)
            if (L[i] <= e - s * sl) if s == 1 else (H[i] >= e - s * sl):
                r = -sl; break
            if (H[i] >= e + s * tp) if s == 1 else (L[i] <= e + s * tp):
                r = tp; break
        if r is None:
            r = (C[-1] - e) * s
        out[d] = ((r * 2 - 1.74) * q, (min(mae, sl) * 2 + 1.74) * q)
    return [out.get(d, (0.0, 0.0)) for d in ALL]


def fondeada(days):
    bal = peak = 0.0; good = 0; cobrado = 0.0; n = 0
    for k, (pnl, mae) in enumerate(days):
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return cobrado, n, True, k + 1
        bal += pnl; peak = max(peak, bal); good += pnl >= MIN_DIA
        if good >= 5 and bal > 0:
            req = min(0.5 * bal, MAX_RET)
            if req >= MIN_RET:
                cobrado += req * 0.9; n += 1; bal -= req; good = 0
    return cobrado, n, False, len(days)


def main():
    cases = {"Rascacielos TP 9.5 / SL 55.75, 9 MNQ": rasca(9.5, 55.75, 9),
             "Rascacielos TP 10 / SL 50.75, 9 MNQ": rasca(10, 50.75, 9),
             "Plan NQ (8:30 + 10:30 + SMC), 2 MNQ c/u": R.nq(2)}
    rows = []
    for nm, days in cases.items():
        res = [fondeada(days[s:s + 252]) for s in range(len(days) - 252)]
        c = np.array([r[0] for r in res]); n = np.array([r[1] for r in res]); b = np.array([r[2] for r in res]); life = np.array([r[3] for r in res])
        rows.append({"estrategia": nm, "cobrado en 12 meses (prom.)": round(c.mean()), "mediana": round(np.median(c)),
                     "retiros (prom.)": round(n.mean(), 1), "cobra al menos 1 vez %": round(100 * (n >= 1).mean(), 1),
                     "no cobra nada %": round(100 * (c == 0).mean(), 1), "se quema %": round(100 * b.mean(), 1),
                     "días que dura (mediana)": int(np.median(life))})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/rascacielos_50k.csv", index=False)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
