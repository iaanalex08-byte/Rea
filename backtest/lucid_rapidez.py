#!/usr/bin/env python3
"""Lucid 25K Flex con POC 1:1 (SL 13): tamaño en evaluación x tamaño fondeado x política de retiro.
Mide probabilidad, rapidez, cobro y ganancia esperada por día de trading.

    python3 backtest/lucid_rapidez.py backtest/datos
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from lucid_flex25k import DD, LOCK, TARGET, CONS, FEE, evaluacion, poc_days  # noqa: E402


def fondeada(days, start, min_dia=100, n_dias=5, tope=1000, retiro_min=500, split=0.9, max_days=500):
    """Devuelve (cobrado, retiros, días usados, día del primer retiro)."""
    bal = peak = 0.0
    good, cob, ret, k, first = 0, 0.0, 0, start, None
    while k < len(days) and k - start < max_days:
        pnl, mae = days[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return cob, ret, k - start + 1, first
        bal += pnl
        peak = max(peak, bal)
        good += pnl >= min_dia
        k += 1
        if good >= n_dias and bal > 0:
            req = min(0.5 * bal, tope)
            if req >= retiro_min:
                cob += req * split
                ret += 1
                bal -= req
                good = 0
                first = first or (k - start)
    return cob, ret, k - start, first


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    D = {m: poc_days(data, m) for m in (2, 3, 4, 5, 6, 8, 10)}
    rows = []
    for me in (2, 3, 4, 5, 6, 8):
        ev = [evaluacion(D[me], s) for s in range(len(D[me]))]
        ev = [(s, r) for s, r in enumerate(ev) if r[0] is not None]
        p_pass = np.mean([r[0] for _, r in ev])
        d_eval = np.mean([r[1] for _, r in ev])           # días en evaluación (pase o falle)
        d_pass = np.median([r[1] for _, r in ev if r[0]])
        for mf in (2, 3, 4, 5, 6, 8, 10):
            for pol, rmin in (("al mínimo ($500)", 500), ("al máximo ($1,000)", 1000)):
                fr = [fondeada(D[mf], s + r[1], retiro_min=rmin) for s, r in ev if r[0] and s + r[1] < len(D[mf])]
                if not fr:
                    continue
                cob = np.array([x[0] for x in fr]); nret = np.array([x[1] for x in fr])
                dfund = np.mean([x[2] for x in fr])
                firsts = [x[3] for x in fr if x[3]]
                ev_acc = p_pass * cob.mean() - FEE
                days_acc = d_eval + p_pass * dfund
                rows.append({"eval MES": me, "fondeada MES": mf, "retiro": pol, "pasa %": round(100 * p_pass, 1),
                             "días a fondear (mediana)": int(d_pass),
                             "1+ retiro % (fondeada)": round(100 * np.mean(nret >= 1), 1),
                             "días al 1er retiro (mediana)": int(np.median(firsts)) if firsts else None,
                             "cobro prom. fondeada $": round(cob.mean()),
                             "ganancia esperada/cuenta $": round(ev_acc),
                             "$ por día de trading": round(ev_acc / days_acc, 2),
                             "cobra algo (del total) %": round(100 * p_pass * np.mean(nret >= 1), 1)})
    t = pd.DataFrame(rows)
    t.to_csv("backtest/resultados/lucid_rapidez.csv", index=False)
    pd.set_option("display.width", 260)
    print("Top por ganancia esperada por cuenta:")
    print(t.sort_values("ganancia esperada/cuenta $", ascending=False).head(12).to_string(index=False))
    print("\nTop por $ por día de trading:")
    print(t.sort_values("$ por día de trading", ascending=False).head(12).to_string(index=False))
    print("\nEvaluación sola:")
    print(t.drop_duplicates("eval MES")[["eval MES", "pasa %", "días a fondear (mediana)"]].to_string(index=False))


if __name__ == "__main__":
    main()
