#!/usr/bin/env python3
"""Días para pasar una evaluación de fondeo con la estrategia SP500 (entrada 9:00 o 9:12, SL 15 pts, tendencia >= 20 pts).

Cuentas (reglas de las capturas del usuario; verificar):
  Lucid 25K Flex: objetivo $1,250, pérdida máx. $1,000 EOD (se fija en +$100), consistencia 40 %.
  Lucid 50K Flex: objetivo $3,000, pérdida máx. $2,000 EOD (se fija en +$100), consistencia 40 %, límite diario $1,200.
  Apex 25K intradía: objetivo $1,500, pérdida máx. $1,000 que sigue el saldo (aquí al cierre del día, más la pérdida
                     abierta de las perdedoras), 30 días (~21 hábiles), sin consistencia.
Tamaños en MES ($5/pt). Se prueba empezando cada día hábil 2024-2026; días = días hábiles (con o sin operación).

    python3 backtest/sp500_fondeo.py
"""
import numpy as np
import pandas as pd

ACC = {"Lucid 25K Flex": dict(target=1250, dd=1000, lock=100, cons=0.40, dll=None, maxd=None),
       "Lucid 50K Flex": dict(target=3000, dd=2000, lock=100, cons=0.40, dll=1200, maxd=None),
       "Apex 25K intradía": dict(target=1500, dd=1000, lock=100, cons=None, dll=None, maxd=21)}
SIZES = {"Lucid 25K Flex": (2, 4), "Lucid 50K Flex": (4, 6), "Apex 25K intradía": (2, 4)}


def days_of(path, var, k):
    o = pd.read_csv(path); o = o[o.variante == var]
    o["p"] = o.usd * k / 2
    o["m"] = np.where(o.usd <= 0, -o.usd * k / 2, 0.0)
    g = o.groupby(pd.to_datetime(o.fecha).dt.date).agg(p=("p", "sum"), m=("m", "sum"))
    allday = pd.bdate_range("2024-01-02", "2026-11-06").date
    g = g.reindex(allday, fill_value=0.0)
    return list(zip(g.p.to_numpy(), g.m.to_numpy()))


def evaluacion(days, s, a):
    bal = peak = best = 0.0
    end = len(days) if a["maxd"] is None else min(len(days), s + a["maxd"])
    for k in range(s, end):
        pnl, mae = days[k]
        if a["dll"]:
            pnl = max(pnl, -a["dll"]); mae = min(mae, a["dll"])
        thr = min(peak - a["dd"], a["lock"])
        if bal - mae <= thr or bal + pnl < thr:
            return False, k - s + 1
        bal += pnl; peak = max(peak, bal); best = max(best, pnl)
        if bal >= a["target"] and (a["cons"] is None or best <= a["cons"] * bal):
            return True, k - s + 1
    return (False, end - s) if a["maxd"] else (None, None)


def main():
    rows = []
    for ent, path in (("9:00", "backtest/resultados/sp500_0900_ops.csv"), ("9:12", "backtest/resultados/sp500_912_ops.csv")):
        for var in ("Parcial 1:1 + BE + 2R", "1:2", "1:3"):
            for acc, a in ACC.items():
                for k in SIZES[acc]:
                    days = days_of(path, var, k)
                    res = [evaluacion(days, s, a) for s in range(len(days) - 150)]
                    res = [r for r in res if r[0] is not None]
                    ok = [d for f, d in res if f]; bad = [d for f, d in res if not f]
                    rows.append({"entrada": ent, "salida": var, "cuenta": acc, "MES": k, "riesgo/op": f"${k * 75}",
                                 "pasa %": round(100 * len(ok) / len(res), 1),
                                 "días prom (las que pasan)": round(np.mean(ok)) if ok else None,
                                 "días mediana": int(np.median(ok)) if ok else None,
                                 "días si te toca mal (peor 10 %)": int(np.percentile(ok, 90)) if ok else None,
                                 "se quema / vence %": round(100 * len(bad) / len(res), 1)})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/sp500_fondeo.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
