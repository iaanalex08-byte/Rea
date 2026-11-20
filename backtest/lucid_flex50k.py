#!/usr/bin/env python3
"""Lucid 50K Flex con 8:30 + 10:30 + SMC (y solo 8:30 + 10:30), varios tamaños. NQ 2024-2026.

Reglas (de la captura del usuario; verificar en Lucid):
  Evaluación: objetivo $3,000; pérdida máxima $2,000 EOD (se supone que se fija en +$100); límite diario $1,200
              (se corta el día en -$1,200); consistencia 40 % (mejor día <= 40 % de la ganancia al pasar); máx. 40 micros.
  Fondeada:   pérdida máxima $2,000; límite diario $1,200; sin consistencia; retiro tras 5 días de >= $150 de ganancia.
              Se supone primer retiro con >= $1,000 de ganancia (retiro del 50 %, mínimo $500, como en la 25K).
              No se modela el plan de escalado (puede limitar contratos al inicio).
Pérdida no realizada: en las perdedoras se toma el SL completo.

    python3 backtest/lucid_flex50k.py
"""
import numpy as np
import pandas as pd

DD, LOCK, TARGET, CONS, DLL, MAXMIC = 2000, 100, 3000, 0.40, 1200, 40
COM = 1.24
ALL = ["8:30 contra Londres", "10:30 con tendencia", "SMC 5 min"]


def days_for(o, ests, sizer):
    x = o[o.estrategia.isin(ests)].copy()
    q = sizer(x)
    x["p"] = x.usd * q; x["m"] = np.where(x.usd <= 0, x.per * q, 0.0)
    g = x.groupby("d").agg(p=("p", "sum"), m=("m", "sum"))
    allday = pd.bdate_range("2024-01-02", "2026-11-06").date
    g = g.reindex(allday, fill_value=0.0)
    p = np.maximum(g.p.to_numpy(), -DLL); m = np.minimum(g.m.to_numpy(), DLL)
    return list(zip(p, m))


def evaluacion(days, s):
    bal = peak = best = 0.0
    for k in range(s, len(days)):
        pnl, mae = days[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - s + 1
        bal += pnl; peak = max(peak, bal); best = max(best, pnl)
        if bal >= TARGET and best <= CONS * bal:
            return True, k - s + 1
    return None, None


def fondeada(days, s, max_days=400):
    bal = peak = 0.0; good = 0
    for k in range(s, min(len(days), s + max_days)):
        pnl, mae = days[k]
        thr = min(peak - DD, LOCK)
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - s + 1
        bal += pnl; peak = max(peak, bal); good += pnl >= 150
        if good >= 5 and bal >= 1000:
            return True, k - s + 1
    return None, None


def main():
    o = pd.read_csv("backtest/resultados/ops_3_estrategias.csv")
    risk = (o.pts / o.R.replace(0, np.nan)).abs().fillna(66.5)
    o["per"] = risk * 2 + COM
    o["d"] = pd.to_datetime(o.fecha).dt.date
    fixed = lambda k: (lambda x: pd.Series(k, index=x.index))  # noqa: E731
    budget = lambda b: (lambda x: np.clip(np.floor(b / x.per), 1, 24))  # noqa: E731
    sizes = {"1 MNQ c/u": fixed(1), "2 MNQ c/u": fixed(2), "3 MNQ c/u": fixed(3), "4 MNQ c/u": fixed(4),
             "$500 repartidos ($167 c/u)": budget(500 / 3), "$250 por operación": budget(250), "$500 por operación": budget(500)}
    rows = []
    for setn, ests in (("8:30 + 10:30 + SMC", ALL), ("8:30 + 10:30", ALL[:2])):
        for sn, sz in sizes.items():
            days = days_for(o, ests, sz)
            ev = [evaluacion(days, s) for s in range(len(days) - 150)]; ev = [e for e in ev if e[0] is not None]
            fd = [fondeada(days, s) for s in range(len(days) - 150)]; fd = [f for f in fd if f[0] is not None]
            okE = [n for f, n in ev if f]; okF = [n for f, n in fd if f]
            p = np.array([d[0] for d in days]); eq = np.cumsum(p); dd = (np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()
            rows.append({"estrategias": setn, "tamaño": sn, "neto/año": round(p.sum() / 2.85), "caída máx": round(dd), "peor día": round(p.min()),
                         "pasa eval %": round(100 * len(okE) / len(ev), 1), "días eval (med)": int(np.median(okE)) if okE else None,
                         "días eval (prom)": round(np.mean(okE)) if okE else None,
                         "1er retiro %": round(100 * len(okF) / len(fd), 1), "días retiro (med)": int(np.median(okF)) if okF else None,
                         "días retiro (prom)": round(np.mean(okF)) if okF else None})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/lucid_flex50k.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
