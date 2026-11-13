"""Corre el análisis detallado y la exportación del dashboard para cualquier SL/TP del modelo B.

    python backtest/es_run_config.py 60 15 30
"""
import os
import sys

import pandas as pd

import es_analysis_config as A


def run(sl, tp1, tp2, time="9:12"):
    name = f"B_CDMX_{sl}_{tp1}_{tp2}" + ("" if time == "9:12" else "_" + time.replace(":", ""))
    A.CFG = dict(A.CFG, name=name, sl=sl, tp1=tp1, tp2=tp2, time=time)
    A.OUT = os.path.join(A.ROOT, "results", "es", "analisis_" + name)
    t, out = A.main()
    t = t.copy()
    t["date"] = pd.to_datetime(t.date).dt.strftime("%Y-%m-%d")
    t["win"] = t.win.astype(int)
    cols = ["date", "entry_ny", "side", "usd", "win", "outcome", "news", "horario_ny", "vol", "weekday", "wom",
            "year", "mins", "mins_tp1", "mfe60", "mae60"]
    t[cols].round({"mfe60": 1, "mae60": 1}).to_csv(os.path.join(A.OUT, "cfg_operaciones.csv"), index=False)
    pd.DataFrame(out["sensitivity"]).round(4).to_csv(os.path.join(A.OUT, "cfg_sensibilidad.csv"), index=False)
    mc, bt = out["montecarlo"], out["bootstrap"]
    pd.DataFrame([
        dict(metrica="ci_low", etiqueta="Esperanza: límite inferior IC 95%", valor=round(bt["ci_avg"][0], 2)),
        dict(metrica="ci_high", etiqueta="Esperanza: límite superior IC 95%", valor=round(bt["ci_avg"][1], 2)),
        dict(metrica="p_le_0", etiqueta="Probabilidad de esperanza ≤ 0", valor=round(bt["p_avg_le_0"], 4)),
        dict(metrica="dd_p50", etiqueta="Drawdown mediano (reordenando)", valor=round(mc["dd_p50"], 2)),
        dict(metrica="dd_p95", etiqueta="Drawdown percentil 95", valor=round(mc["dd_p95"], 2)),
        dict(metrica="streak_p95", etiqueta="Peor racha percentil 95", valor=mc["streak_p95"]),
        dict(metrica="p_loss_100", etiqueta="Probabilidad de perder en 100 operaciones", valor=round(mc["p_loss_100"], 4)),
    ]).to_csv(os.path.join(A.OUT, "cfg_riesgo.csv"), index=False)
    return t, out


if __name__ == "__main__":
    sl, tp1, tp2 = map(int, sys.argv[1:4])
    t, out = run(sl, tp1, tp2)
    import json
    print(json.dumps({k: out[k] for k in ["stats", "bootstrap", "montecarlo", "timing", "excursion"]}, indent=1))
    for k in ["outcome", "side", "year", "horario_ny", "vol", "news", "weekday", "wom"]:
        print(k, [(r["k"], r["n"], round(r["winrate"], 2), round(r["net"])) for r in out[k]])
    print("sens", [(s["sl"], s["tp1"], s["tp2"], round(s["pf"], 2), round(s["net"]), round(s["t"], 2)) for s in out["sensitivity"]])
    u = t.usd.to_numpy(); b = r = 0
    for v in u:
        r = r + 1 if v > 0 else 0; b = max(b, r)
    print("mejor racha", b)
