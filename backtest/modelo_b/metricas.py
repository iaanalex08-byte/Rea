#!/usr/bin/env python3
"""Métricas completas del Modelo B en ES real a partir de backtest/resultados/modelo_b_dias_<versión>.csv.
    python3 backtest/modelo_b/metricas.py
"""
import numpy as np
import pandas as pd


def pf(u):
    return u[u > 0].sum() / -u[u <= 0].sum() if (u <= 0).any() else np.inf


def met(x):
    u = x.usd.values
    eq = np.cumsum(u)
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min()
    neg = pd.Series((u <= 0).astype(int)); pos = pd.Series((u > 0).astype(int))
    rn = neg.groupby((neg != neg.shift()).cumsum()).sum().max(); rp = pos.groupby((pos != pos.shift()).cumsum()).sum().max()
    mes = x.groupby(x.date.str[:7]).usd.sum()
    sal = x.salida.value_counts(normalize=True) * 100
    r = {"ops": len(u), "ganadoras %": (u > 0).mean() * 100, "PF": pf(u), "neto 2 ES": u.sum(), "por op": u.mean(),
         "gan. media": u[u > 0].mean(), "pérd. media": u[u <= 0].mean(), "caída máx": dd, "racha perdedora": rn, "racha ganadora": rp,
         "meses +": f"{(mes > 0).sum()}/{len(mes)}", "TP1+TP2 %": sal.get("TP1 + TP2", 0), "TP1+BE %": sal.get("TP1 + BE", 0),
         "TP1+cierre %": sal.get("TP1 + cierre", 0), "Stop %": sal.get("Stop (−2)", 0), "Cierre %": sal.get("Cierre 15:59", 0)}
    for a in ("2024", "2025", "2026"):
        v = x[x.date.str.startswith(a)].usd.values
        r[f"PF {a}"] = pf(v); r[f"neto {a}"] = v.sum(); r[f"ops {a}"] = len(v)
    return r


rows = {}
for v, nom in (("cdmx", "9:12 CDMX (regla escrita)"), ("ny", "10:12 NY (lo que midió el original)")):
    T = pd.read_csv(f"backtest/resultados/modelo_b_dias_{v}.csv")
    rows[f"{nom} · solo EMA"] = met(T)
    rows[f"{nom} · EMA + A + C"] = met(T[T.pasa])
    rows[f"{nom} · A + C + BOS 5m última hora"] = met(T[T.pasa & T["5m_BOS_60_favor"]])
    rows[f"{nom} · A + C + FVG 5m últimos 30 min"] = met(T[T.pasa & T["5m_FVG_30_favor"]])
R = pd.DataFrame(rows).T
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print(R.round(2).T.to_string())
R.to_csv("backtest/resultados/modelo_b_metricas.csv")
