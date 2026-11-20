#!/usr/bin/env python3
"""Plan 8:30 + 10:30 + SMC arriesgando hasta $500 por operación (MNQ = $2/pt, comisión $1.24 por contrato).

Contratos = los que caben sin pasar de $500 de riesgo (SL x $2 + comisión por contrato).
POC: SL 66.5 -> 3 MNQ ($403 de riesgo). SMC: varía con su SL (mecha), máx. 50 MNQ.

    python3 backtest/riesgo_500.py
"""
import numpy as np
import pandas as pd

RIESGO, MAXQ = 500, 50


def main():
    o = pd.read_csv("backtest/resultados/ops_3_estrategias.csv").sort_values(["fecha", "hora"]).reset_index(drop=True)
    risk_pts = (o.pts / o.R.replace(0, np.nan)).abs().fillna(66.5)
    per = risk_pts * 2 + 1.24
    o["q"] = np.clip(np.floor(RIESGO / per), 1, MAXQ).astype(int)
    o["riesgo $"] = (o.q * per).round()
    o["usd500"] = (o.usd * o.q).round(2)
    yrs = (pd.Timestamp(o.fecha.iloc[-1]) - pd.Timestamp(o.fecha.iloc[0])).days / 365.25
    def st(r):  # noqa: E306
        u = r.usd500; eq = u.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
        run = w = 0; lrun = lw = 0.0
        for v in u:
            run = run + 1 if v <= 0 else 0; w = max(w, run)
            lrun = lrun + v if v <= 0 else 0; lw = min(lw, lrun)
        day = r.groupby("fecha").usd500.sum(); mo = r.groupby(r.fecha.str[:7]).usd500.sum()
        wk = r.groupby(pd.to_datetime(r.fecha).dt.to_period("W-FRI")).usd500.sum()
        return {"contratos": f"{r.q.min()}-{r.q.max()} (med {int(r.q.median())})", "riesgo medio $": round(r["riesgo $"].mean()),
                "ops": len(r), "winrate %": round(100 * (u > 0).mean(), 1), "neto": round(u.sum()), "neto/año": round(u.sum() / yrs),
                "ganancia media": round(u[u > 0].mean()), "pérdida media": round(u[u <= 0].mean()), "caída máx": round(dd),
                "peor racha": w, "peor racha $": round(lw), "peor día": round(day.min()), "peor semana": round(wk.min()), "peor mes": round(mo.min()),
                "mes medio": round(mo.median()), "% meses +": round(100 * (mo > 0).mean()), "neto 2026": round(u[o.fecha.loc[r.index].str[:4] == "2026"].sum())}
    rows = {e: st(o[o.estrategia == e]) for e in o.estrategia.unique()}
    rows["Plan completo"] = st(o)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).to_string())
    mo = o.groupby(o.fecha.str[:7]).usd500.sum()
    print("\nMeses del plan:"); print(mo.round().to_string())


if __name__ == "__main__":
    main()
