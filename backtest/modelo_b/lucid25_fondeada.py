#!/usr/bin/env python3
"""Lucid Flex 25K fondeada con el Modelo B "Más dinero" (10:12 NY, 30/40/160 sin BE), desde cada operación del backtest.
Supuestos (verificar con Lucid): caída 1,000 USD al cierre del día que sigue al saldo más alto y se congela en +100;
sin límite diario ni consistencia; retiro cuando hay 5 días con +100 o más y saldo positivo; se retira el 50 % de la ganancia.
Los días hábiles cuentan todos los días de mercado, opere o no el modelo.
    python3 backtest/modelo_b/lucid25_fondeada.py <operaciones.json del dashboard>
"""
import json, sys
import numpy as np, pandas as pd
ops = json.load(open(sys.argv[1]))["rows"]
fechas = pd.to_datetime([o["fecha"] for o in ops])
ticks = np.array([o["ticks"] for o in ops])
DD, LOCK = 1000.0, 100.0
filas = []
for n in (2, 3, 4, 6, 8):
    u = ticks * (n / 2) * 1.25 - n * 2.49
    res = []
    for i0 in range(len(u)):
        bal = hwm = 0.0; buenos = 0; r = None
        for k in range(i0, len(u)):
            bal += u[k]; hwm = max(hwm, bal); buenos += u[k] >= 100
            if bal <= min(hwm - DD, LOCK):
                r = ("quema", k); break
            if buenos >= 5 and bal > 0:
                r = ("retira", k); break
        if r is None:
            continue
        hab = len(pd.bdate_range(fechas[i0], fechas[r[1]]))
        res.append((r[0], r[1] - i0 + 1, hab, bal))
    ret = [x for x in res if x[0] == "retira"]
    filas.append(dict(mes=n, riesgo_stop=round(30 * 1.25 * n + 2.49 * n), cuentas=len(res), retira_pct=round(100 * len(ret) / len(res), 1),
                      ops_mediana=int(np.median([x[1] for x in ret])), dias_habiles_mediana=int(np.median([x[2] for x in ret])),
                      dias_habiles_promedio=round(np.mean([x[2] for x in ret]), 1), semanas_promedio=round(np.mean([x[2] for x in ret]) / 5, 1),
                      ganancia_al_retirar=round(np.median([x[3] for x in ret])), retiro_50pct=round(np.median([x[3] for x in ret]) / 2)))
T = pd.DataFrame(filas); T.to_csv("backtest/resultados/modelo_b_lucid25_fondeada.csv", index=False)
pd.set_option("display.width", 220); print(T.to_string(index=False))
