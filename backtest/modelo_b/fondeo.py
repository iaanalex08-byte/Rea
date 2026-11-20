#!/usr/bin/env python3
"""¿Qué versión del Modelo B (A + C por volumen, sin BOS en contra, VWAP a favor) conviene para una cuenta de fondeo?

Simula una evaluación Lucid 50K Flex empezando en cada operación del backtest (ES real, 10:12 NY):
  meta +3,000 USD; caída máxima 2,000 USD al cierre del día, que sigue al saldo más alto y se congela al llegar
  al saldo inicial + 100; regla de consistencia 40 % (el mejor día no puede pasar del 40 % de la ganancia al pasar,
  si no se sigue operando hasta cumplirla). Una operación por día.
Y la cuenta fondeada (misma caída de 2,000, sin consistencia): probabilidad de llegar a +1,000 USD antes de perderla.
Tamaño en MES (micro): la mitad sale en TP1 y la otra en TP2. Costo por MES: 1 tick de deslizamiento + 1.24 USD.

    python3 backtest/modelo_b/fondeo.py
Salida: backtest/resultados/modelo_b_fondeo.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402

VERSIONES = {"Winrate alto 50/20/120 BE": ((50, 20, 120, True), False), "Winrate alto 40/20/120 BE": ((40, 20, 120, True), False),
             "Equilibrio 35/30/120 BE": ((35, 30, 120, True), False), "Equilibrio + vol. relativo 35/30/120 BE": ((35, 30, 120, True), True),
             "Más dinero 30/40/160 sin BE": ((30, 40, 160, False), False)}
META, DD, CONS = 3000.0, 2000.0, 0.40
COSTO_MES = 1.25 + 1.24


def evaluacion(u, i0):
    """Desde la operación i0: ('pasa'|'pierde'|'sin datos', operaciones usadas)."""
    bal, hwm, mx = 0.0, 0.0, 0.0
    for k in range(i0, len(u)):
        bal += u[k]
        mx = max(mx, u[k])
        hwm = max(hwm, bal)
        piso = min(hwm - DD, 100.0)
        if bal <= piso:
            return "pierde", k - i0 + 1
        if bal >= META and mx <= CONS * bal:
            return "pasa", k - i0 + 1
    return "sin datos", len(u) - i0


def fondeada(u, i0, meta=1000.0):
    bal, hwm = 0.0, 0.0
    for k in range(i0, len(u)):
        bal += u[k]
        hwm = max(hwm, bal)
        if bal <= min(hwm - DD, 100.0):
            return "pierde", k - i0 + 1
        if bal >= meta:
            return "retira", k - i0 + 1
    return "sin datos", len(u) - i0


def main():
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    f = pd.DataFrame([V[d["date"]] for d in F])
    base = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    filas = []
    for nom, ((sl, t1, t2, be), rvol) in VERSIONES.items():
        m = base & (f["Volumen relativo alto"].values if rvol else True)
        dias = [d for d, k in zip(F, m) if k]
        ticks = np.array([(rf.bracket(d, sl, t1, t2, be=be) + 34) / 12.5 for d in dias])  # ticks de los dos tramos juntos
        for n in (2, 4, 6, 8, 10):
            u = ticks * (n / 2) * 1.25 - n * COSTO_MES
            ev = [evaluacion(u, i) for i in range(len(u))]
            fin = [e for e in ev if e[0] != "sin datos"]
            pasa = [k for r, k in fin if r == "pasa"]
            fo = [fondeada(u, i) for i in range(len(u))]
            fofin = [e for e in fo if e[0] != "sin datos"]
            filas.append(dict(version=nom, mes=n, riesgo_sl=round(n * sl * 1.25 + n * COSTO_MES), por_op=round(u.mean(), 1),
                              pasa_pct=round(100 * len(pasa) / len(fin), 1) if fin else None,
                              ops_para_pasar=int(np.median(pasa)) if pasa else None,
                              semanas_para_pasar=round(np.median(pasa) * 7 / (len(u) / (33 * 4.33) * 7), 1) if pasa else None,
                              ops_para_perder=int(np.median([k for r, k in fin if r == "pierde"])) if len(fin) > len(pasa) else None,
                              retira_1000_pct=round(100 * sum(r == "retira" for r, _ in fofin) / len(fofin), 1) if fofin else None,
                              intentos=len(fin)))
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/modelo_b_fondeo.csv", index=False)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
