#!/usr/bin/env python3
"""Lucid 50K Flex: días promedio para pasar la evaluación y para cobrar $1,000, más todas las métricas.

Retiro de $1,000: 5 días de >= $150 y ganancia suficiente. Dos supuestos:
  "50 %": Lucid paga el 50 % de la ganancia -> hace falta +$2,000 para cobrar $1,000.
  "100 %": se puede retirar toda la ganancia -> hace falta +$1,000.

    python3 backtest/lucid50k_metricas.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex50k as L  # noqa: E402


def fondeada(days, s, need, max_days=500):
    bal = peak = 0.0; good = 0
    for k in range(s, min(len(days), s + max_days)):
        pnl, mae = days[k]
        thr = min(peak - L.DD, L.LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - s + 1
        bal += pnl; peak = max(peak, bal); good += pnl >= 150
        if good >= 5 and bal >= need:
            return True, k - s + 1
    return None, None


def main():
    o = pd.read_csv("backtest/resultados/ops_3_estrategias.csv").sort_values(["fecha", "hora"]).reset_index(drop=True)
    risk = (o.pts / o.R.replace(0, np.nan)).abs().fillna(66.5)
    o["per"] = risk * 2 + L.COM; o["d"] = pd.to_datetime(o.fecha).dt.date
    yrs = 2.85
    rows = []
    for setn, ests in (("8:30 + 10:30 + SMC", L.ALL), ("8:30 + 10:30", L.ALL[:2])):
        for k in (1, 2, 3):
            days = L.days_for(o, ests, lambda x: pd.Series(k, index=x.index))
            n = len(days) - 150
            ev = [L.evaluacion(days, s) for s in range(n)]; ev = [e for e in ev if e[0] is not None]
            okE = [d for f, d in ev if f]
            res = {}
            for lab, need in (("50 %", 2000), ("100 %", 1000)):
                fd = [fondeada(days, s, need) for s in range(n)]; fd = [f for f in fd if f[0] is not None]
                ok = [d for f, d in fd if f]
                res[lab] = (100 * len(ok) / len(fd), np.mean(ok), np.median(ok))
            x = o[o.estrategia.isin(ests)]; u = x.usd * k
            eq = u.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
            run = w = 0
            for v in u:
                run = run + 1 if v <= 0 else 0; w = max(w, run)
            day = u.groupby(x.fecha).sum(); mo = u.groupby(x.fecha.str[:7]).sum(); wk = u.groupby(pd.to_datetime(x.fecha).dt.to_period("W-FRI")).sum()
            rows.append({
                "estrategias": setn, "MNQ c/u": k,
                "pasa eval %": round(100 * len(okE) / len(ev), 1), "días eval prom": round(np.mean(okE)), "días eval med": int(np.median(okE)),
                "cobra $1k (50 %) %": round(res["50 %"][0], 1), "días a $1k prom (50 %)": round(res["50 %"][1]), "días a $1k med (50 %)": int(res["50 %"][2]),
                "cobra $1k (100 %) %": round(res["100 %"][0], 1), "días a $1k prom (100 %)": round(res["100 %"][1]),
                "total eval + $1k prom (50 %)": round(np.mean(okE) + res["50 %"][1]),
                "operaciones/año": round(len(u) / yrs), "winrate %": round(100 * (u > 0).mean(), 1),
                "factor de beneficio": round(u[u > 0].sum() / -u[u <= 0].sum(), 2), "$ por operación": round(u.mean()),
                "ganancia media": round(u[u > 0].mean()), "pérdida media": round(u[u <= 0].mean()), "peor racha": w,
                "neto/año": round(u.sum() / yrs), "ROI anual sobre $2,000 de DD": f"{round(100 * u.sum() / yrs / 2000)} %",
                "caída máx": round(dd), "margen vs $2,000": round(2000 - dd), "peor día": round(day.min()), "peor semana": round(wk.min()),
                "peor mes": round(mo.min()), "mes medio": round(mo.median()), "% meses +": round(100 * (mo > 0).mean()),
                "% semanas +": round(100 * (wk > 0).mean()), "desv. por operación": round(u.std()), "varianza por operación": round(u.var()),
                "desv. mensual": round(mo.std())})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/lucid50k_metricas.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
    print(T.set_index(["estrategias", "MNQ c/u"]).T.to_string())


if __name__ == "__main__":
    main()
