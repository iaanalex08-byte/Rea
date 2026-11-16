"""Modelo B (SL 45 · TP 30/60) por hora de entrada: 9:12 CDMX frente a horas NY fijas.

    python backtest/es_modelo_b_horario.py  ->  results/es/modelo_b_horario/operaciones_por_hora.csv
Datos del dashboard "Modelo B y el horario de verano".
"""
import os
import numpy as np
import pandas as pd
from es_analysis_config import trade_detail
from es_backtest import COST_T, ROOT, TICK_USD, day_paths, load, trend_series

MODOS = [("9:12 CDMX (como operas)", "9:12", "America/Mexico_City"), ("10:12 NY fijo", "10:12", "America/New_York"),
         ("11:12 NY fijo", "11:12", "America/New_York"), ("9:42 NY fijo", "9:42", "America/New_York")]


def temporada(d):
    return "Verano NY" if pd.Timestamp(d).tz_localize("America/New_York").utcoffset().total_seconds() == -4 * 3600 else "Invierno NY"


df = load(); e20 = trend_series(df)["EMA20 3m"]; rows = []
for modo, hm, tz in MODOS:
    for d, t0, g in day_paths(df, hm, tz):
        ref = e20.get(t0, np.nan)
        if np.isnan(ref):
            continue
        e = g["o"].iloc[0]; s = 1 if e > ref else -1
        x = trade_detail(e, s, g, 45, 30, 60)
        rows.append(dict(modo=modo, date=pd.Timestamp(d).strftime("%Y-%m-%d"), year=d.year, temporada=temporada(d),
                         hora_ny=t0.strftime("%H:%M"), lado="Compra" if s > 0 else "Venta", desenlace=x["outcome"],
                         usd=round(x["ticks"] * TICK_USD - 2 * COST_T * TICK_USD, 2)))
T = pd.DataFrame(rows)
out = os.path.join(ROOT, "results", "es", "modelo_b_horario"); os.makedirs(out, exist_ok=True)
T.to_csv(os.path.join(out, "operaciones_por_hora.csv"), index=False)
print(T.groupby(["modo", "temporada"], sort=False).usd.agg(["size", "sum"]).round(0))
