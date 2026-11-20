#!/usr/bin/env python3
"""Apex 25K con el Modelo B (ES real 1 min, 10:12 NY), contando la caída con las pérdidas ABIERTAS minuto a minuto.

1) Evaluación "todo en una": una sola operación que arriesga toda la caída (1,000 USD) para sacar la meta (1,500 USD)
   el mismo día. La caída de Apex sigue al saldo más alto incluyendo lo no realizado y se congela en +100, así que si
   el precio sube y regresa 1,000 desde su máximo, la cuenta se quema aunque no haya tocado el stop.
   Se prueba con 1, 2, 3 y 4 ES (más contratos = stop y objetivo más cortos) en dos grupos de días:
   los días que el Modelo B opera, y todos los días siguiendo solo la EMA 20 de 3 min.
2) Cuenta fondeada (PA): desde cada operación del modelo, probabilidad de juntar el colchón de 1,100 USD y después
   llegar a +1,600 (colchón + primer retiro de 500) antes de quemarla, por versión del bracket y número de MES.

    python3 backtest/modelo_b/apex.py
Salidas: backtest/resultados/modelo_b_apex_eval.csv y backtest/resultados/modelo_b_apex_fondeada.csv
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402

DD, META, LOCK = 1000.0, 1500.0, 100.0
COSTO_ES, COSTO_MES = 17.0, 2.49


def eval_todo(d, k):
    """Una operación con k ES: stop = toda la caída, objetivo = la meta. 'pasa', 'quema' o 'abierta' al cierre."""
    tv = 12.5 * k
    cost = COSTO_ES * k
    sl = math.floor((DD - cost) / tv) - 1          # ticks; un tick de margen
    tp = math.ceil((META + cost) / tv)
    ddt, lockt = DD / tv, LOCK / tv
    up, dn = d["up"], d["dn"]
    peak = 0.0
    for i in range(len(up)):
        piso = max(-sl, min(peak - ddt, lockt))
        if dn[i] <= piso:
            return "quema" if piso < 0 else "quema"
        if up[i] >= tp:
            return "pasa"
        peak = max(peak, up[i])
    return "abierta"


def fondeada(dias, i0, n, br, meta_retiro=1600.0, colchon=1100.0):
    """Cuenta PA desde la operación i0 con n MES. Devuelve (resultado, ops, llegó al colchón)."""
    sl, t1, t2, be = br
    tick = 1.25 * n / 2                                # USD por tick de cada mitad
    bal, peak, colchon_ok = 0.0, 0.0, False
    for k in range(i0, len(dias)):
        d = dias[k]
        up, dn = d["up"], d["dn"]
        legs = [True, True]; real = 0.0; stop = -sl
        for i in range(len(up)):
            abiertas = sum(legs)
            peor = bal + (real + abiertas * dn[i]) * tick
            piso = min(peak - DD, LOCK)
            if peor <= piso:
                return "quema", k - i0 + 1, colchon_ok
            if dn[i] <= stop:
                real += abiertas * stop; legs = [False, False]
            else:
                if legs[0] and up[i] >= t1:
                    real += t1; legs[0] = False
                    if be:
                        stop = 0
                if legs[1] and up[i] >= t2:
                    real += t2; legs[1] = False
            mejor = bal + (real + sum(legs) * up[i]) * tick
            peak = max(peak, mejor)
            if not any(legs):
                break
        if any(legs):
            real += sum(legs) * d["cl"]
        bal += real * tick - n * COSTO_MES
        peak = max(peak, bal)
        if bal <= min(peak - DD, LOCK):
            return "quema", k - i0 + 1, colchon_ok
        if bal >= colchon:
            colchon_ok = True
        if bal >= meta_retiro:
            return "retira", k - i0 + 1, True
    return "sin datos", len(dias) - i0, colchon_ok


def main():
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    f = pd.DataFrame([V[d["date"]] for d in F])
    m = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    modelo = [d for d, x in zip(F, m) if x]

    filas = []
    for grupo, dias in (("Días que opera el Modelo B", modelo), ("Todos los días, solo EMA", F)):
        for k in (1, 2, 3, 4):
            r = pd.Series([eval_todo(d, k) for d in dias]).value_counts()
            tv = 12.5 * k
            filas.append(dict(grupo=grupo, contratos_ES=k, stop_pts=round((math.floor((DD - COSTO_ES * k) / tv) - 1) * 0.25, 2),
                              objetivo_pts=round(math.ceil((META + COSTO_ES * k) / tv) * 0.25, 2), dias=len(dias),
                              pasa_pct=round(100 * r.get("pasa", 0) / len(dias), 1), quema_pct=round(100 * r.get("quema", 0) / len(dias), 1),
                              abierta_pct=round(100 * r.get("abierta", 0) / len(dias), 1)))
    E = pd.DataFrame(filas)
    E.to_csv("backtest/resultados/modelo_b_apex_eval.csv", index=False)
    pd.set_option("display.width", 220)
    print(E.to_string(index=False))

    versiones = {"Más dinero 30/40/160 sin BE": (30, 40, 160, False), "Equilibrio 35/30/120 con BE": (35, 30, 120, True),
                 "Winrate alto 40/20/120 con BE": (40, 20, 120, True), "Winrate alto 50/20/120 con BE": (50, 20, 120, True)}
    semanas = len(modelo) / (33 * 4.33)
    filas = []
    for nom, br in versiones.items():
        for n in (2, 4, 6, 8, 10):
            res = [fondeada(modelo, i, n, br) for i in range(len(modelo))]
            fin = [x for x in res if x[0] != "sin datos"]
            ret = [x for x in fin if x[0] == "retira"]
            filas.append(dict(version=nom, mes=n, riesgo_stop=round(br[0] * 1.25 * n + n * COSTO_MES),
                              retira_pct=round(100 * len(ret) / len(fin), 1) if fin else None,
                              colchon_pct=round(100 * sum(x[2] for x in fin) / len(fin), 1) if fin else None,
                              ops_para_retirar=int(np.median([x[1] for x in ret])) if ret else None,
                              semanas_para_retirar=round(np.median([x[1] for x in ret]) / semanas, 1) if ret else None,
                              cuentas=len(fin)))
    P = pd.DataFrame(filas)
    P.to_csv("backtest/resultados/modelo_b_apex_fondeada.csv", index=False)
    print(P.to_string(index=False))


if __name__ == "__main__":
    main()
