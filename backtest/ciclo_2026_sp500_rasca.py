#!/usr/bin/env python3
"""Ciclo real en 2026 (Lucid 50K Flex), semana por semana:
  1) Evaluación ($80.50): SP500 9:00 a favor de la tendencia 00:00-9:00 (>= 20 pts), $1,000 de riesgo,
     SL 15 pts, TP 1:1.05 (~15.75 pts). Objetivo $3,000, pérdida máx. $2,000 EOD, consistencia 40 %.
  2) Fondeada: Rascacielos versión 50K (9 MNQ, TP 10, SL 105, entrada 9:30 NY). Pérdida máx. $2,000 EOD
     (se fija en +$100). Cada 5 días de >= $150 se retira el 50 % de la ganancia; se cobra el 90 % de eso.
  3) Si una cuenta se quema (evaluación o fondeada), se compra otra evaluación al día siguiente y se repite.
Una sola cuenta a la vez, desde el 2 de enero de 2026.

Salidas: backtest/resultados/ciclo_2026_semanal.csv y ciclo_2026_eventos.csv
    python3 backtest/ciclo_2026_sp500_rasca.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

FEE, SPLIT = 80.50, 0.90


def main():
    g.SALIDAS["1:1.05"] = ([(1, 1.05)], False)
    sp = {}
    for d, tm, O, H, L, C in g.prep(bars("backtest/datos")):
        if d.year < 2026:
            continue
        t = g.run([(d, tm, O, H, L, C)], 60, "1:1.05", 540, 20)
        if not t.empty:
            u = float(t.R.iloc[0]) * 1000
            sp[d] = (u, -u if u <= 0 else 0.0)
    rz = pd.read_csv("backtest/resultados/rascacielos_2026.csv")
    rz = rz[rz.opero == "Sí"]
    rasca = {pd.Timestamp(f).date(): (u, (m * 18 + 15.66) if u > 0 else -u)
             for f, u, m in zip(rz.fecha, rz.usd_50k, rz.mae_50k)}
    days = list(pd.bdate_range("2026-01-02", "2026-11-06").date)
    ev = []
    fase, bal, peak, best, good, n_cuenta = "eval", 0.0, 0.0, 0.0, 0, 1
    ev.append((days[0], "Compra evaluación #1", -FEE))
    for d in days:
        if fase == "eval":
            if d not in sp:
                continue
            pnl, mae = sp[d]
            thr = min(peak - 2000, 100)
            if bal - mae <= thr or bal + pnl < thr:
                ev.append((d, f"Evaluación #{n_cuenta} quemada ({pnl:+,.0f})", 0.0))
                n_cuenta += 1
                ev.append((d, f"Compra evaluación #{n_cuenta}", -FEE))
                bal = peak = best = 0.0
                continue
            bal += pnl; peak = max(peak, bal); best = max(best, pnl)
            if bal >= 3000 and best <= 0.4 * bal:
                ev.append((d, f"Pasa evaluación #{n_cuenta} (+${bal:,.0f})", 0.0))
                fase, bal, peak, good = "fondeada", 0.0, 0.0, 0
        else:
            if d not in rasca:
                continue
            pnl, mae = rasca[d]
            thr = min(peak - 2000, 100)
            if bal - mae <= thr or bal + pnl < thr:
                ev.append((d, f"Fondeada #{n_cuenta} quemada por SL ({pnl:+,.0f})" if pnl <= 0 else f"Fondeada #{n_cuenta} quemada: el precio fue en contra y tocó el límite antes del TP", 0.0))
                n_cuenta += 1
                ev.append((d, f"Compra evaluación #{n_cuenta}", -FEE))
                fase, bal, peak, best = "eval", 0.0, 0.0, 0.0
                continue
            bal += pnl; peak = max(peak, bal); good += pnl >= 150
            if good >= 5 and bal > 0:
                req = 0.5 * bal
                ev.append((d, f"Retiro fondeada #{n_cuenta}: 50 % de ${bal:,.0f} = ${req:,.0f} → cobras ${req * SPLIT:,.0f}", req * SPLIT))
                bal -= req; good = 0
    E = pd.DataFrame(ev, columns=["fecha", "evento", "usd"])
    E["fecha"] = pd.to_datetime(E.fecha)
    E["semana"] = (E.fecha - pd.to_timedelta(E.fecha.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
    E.assign(fecha=E.fecha.dt.strftime("%Y-%m-%d")).to_csv("backtest/resultados/ciclo_2026_eventos.csv", index=False)
    weeks = pd.date_range("2025-12-29", "2026-11-06", freq="W-MON").strftime("%Y-%m-%d")
    W = pd.DataFrame({"semana": weeks})
    agg = E.groupby("semana").agg(costo=("usd", lambda s: -s[s < 0].sum()), cobrado=("usd", lambda s: s[s > 0].sum()),
                                  eventos=("evento", lambda s: " · ".join(s)))
    W = W.merge(agg, on="semana", how="left").fillna({"costo": 0.0, "cobrado": 0.0, "eventos": ""})
    W["neto"] = (W.cobrado - W.costo).round(2)
    W["neto_acumulado"] = W.neto.cumsum().round(2)
    W.insert(1, "semana_num", range(1, len(W) + 1))
    W.to_csv("backtest/resultados/ciclo_2026_semanal.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
    print(E.to_string(index=False))
    print(f"\nEvaluaciones compradas: {int((E.usd < 0).sum())}, costo ${-E.usd[E.usd < 0].sum():,.0f}, cobrado ${E.usd[E.usd > 0].sum():,.0f}, "
          f"neto ${E.usd.sum():,.0f}, semanas {len(W)}, neto/semana ${E.usd.sum() / len(W):,.0f}, semanas con cobro {(W.cobrado > 0).sum()}")


if __name__ == "__main__":
    main()
