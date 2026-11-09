#!/usr/bin/env python3
"""Rascacielos 2026 día por día (todos los días hábiles): entrada 9:30 NY a favor de la EMA 20/50 de 15 min,
TP 10.5 pts, 6 MNQ, con SL 50, 80 (lo que aguanta una 25K) y 700. Cierre 15:55 NY. Comisión $1.24 + 1 tick por contrato.

Salida: backtest/resultados/rascacielos_2026.csv
    python3 backtest/rascacielos_2026.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load  # noqa: E402

TP, Q = 10.5, 6
SLS = (50, 80, 700)


def main():
    nq = load("backtest/datos_NQ")
    c15 = nq.close.resample("15min", label="left", closed="left").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    tm = nq.index.hour * 60 + nq.index.minute
    w = nq[(tm >= 570) & (tm < 955)]
    trades = {}
    for d, g in w.groupby(w.index.date):
        if d < pd.Timestamp("2026-01-01").date() or g.index[0].hour * 60 + g.index[0].minute != 570:
            continue
        k = c15.index.searchsorted(g.index[0]) - 1
        s = 1 if e20.iloc[k] > e50.iloc[k] else -1
        O, H, L, C = (g[c].to_numpy() for c in ("open", "high", "low", "close"))
        e = O[0]
        rec = {"direccion": "Compra" if s == 1 else "Venta", "entrada": round(e, 2)}
        mae = 0.0
        for sl in SLS:
            r, how = None, "Cierre 15:55"
            for i in range(len(O)):
                if (L[i] <= e - s * sl) if s == 1 else (H[i] >= e - s * sl):
                    r, how = -sl, "SL"; break
                if (H[i] >= e + s * TP) if s == 1 else (L[i] <= e + s * TP):
                    r, how = TP, "TP"; break
            if r is None:
                r = (C[-1] - e) * s
            rec[f"res_{sl}"] = how
            rec[f"pts_{sl}"] = round(r, 2)
            rec[f"usd_{sl}"] = round((r * 2 - 1.74) * Q, 2)
        # peor punto en contra en el día (para ver qué tan cerca estuvo del SL)
        rec["max_en_contra"] = round(float(max((e - L.min()) if s == 1 else (H.max() - e), 0)), 2)
        trades[d] = rec
    rows = []
    for d in pd.bdate_range("2026-01-01", "2026-11-06").date:
        r = {"fecha": d.isoformat(), "dia": ["Lun", "Mar", "Mié", "Jue", "Vie"][d.weekday()], "mes": d.strftime("%Y-%m")}
        if d in trades:
            r.update(trades[d]); r["opero"] = "Sí"
        else:
            r["opero"] = "No (feriado o sin datos)"
        rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/rascacielos_2026.csv", index=False)
    x = T[T.opero == "Sí"]
    for sl in SLS:
        u = x[f"usd_{sl}"]
        print(f"SL {sl}: días {len(x)}, ganadas {int((u > 0).sum())}, perdidas {int((u <= 0).sum())}, neto ${u.sum():,.0f}")
    print("días hábiles:", len(T), "sin operación:", int((T.opero != 'Sí').sum()))


if __name__ == "__main__":
    main()
