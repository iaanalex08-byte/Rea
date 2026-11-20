#!/usr/bin/env python3
"""Ciclo combinado en Lucid 50K Flex: Modelo B "Más dinero" (10:12 NY) + SP500 9:00 CDMX con confirmación.

Evaluación: meta +3,000, caída 2,000 al cierre del día que sigue al saldo más alto y se congela en +100,
  consistencia 40 % (el mejor día no puede pasar del 40 % de la ganancia). Sin límite de días.
Fondeada (supuestos, verificar con Lucid): misma caída; retiro cuando hay 5 días con +150 o más desde el último
  retiro y saldo positivo; se retira el 50 % de la ganancia y el trader cobra el 90 % de eso. 12 meses o hasta quemarse.
Tamaño: Modelo B en MES (riesgo 30 ticks) y SP500 en MES (riesgo 60 ticks = 15 pts, el doble por contrato),
  así que la SP500 lleva la mitad de MES para arriesgar lo mismo.
Variantes: solo Modelo B; combinado; combinado con tamaño según el gap (completo si el gap ya se cerró antes de
  entrar, la mitad si no). Si los dos dan señal el mismo día se toman los dos (pueden estar abiertos a la vez).
Se arranca una cuenta en cada día hábil de 2024-01 a 2025-11 (para tener 12 meses después).

    python3 backtest/modelo_b/lucid50_combinado.py
Salida: backtest/resultados/lucid50_combinado.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
import confirmaciones as cf  # noqa: E402
import sp500_0912_grid as g  # noqa: E402
import gap as gp  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402
from sp500_0912 import bars  # noqa: E402

DD, LOCK, META, CONS = 2000.0, 100.0, 3000.0, 0.40
FEE = 80.50


def operaciones():
    raw = bars(str(HERE.parent / "datos"))
    G = gp.gaps(raw)
    ops = {}
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    f = pd.DataFrame([V[d["date"]] for d in F])
    m = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    for d, x in zip(F, m):
        if not x:
            continue
        t0 = pd.Timestamp(f"{d['date']} {d['hm'][0]:02d}:{d['hm'][1]:02d}", tz="America/Mexico_City").tz_convert("America/New_York")
        r = gp.rasgos(G, pd.Timestamp(d["date"]).date(), t0, d["dir"])
        ticks = (rf.bracket(d, 30, 40, 160, be=False) + 34) / 12.5
        ops.setdefault(pd.Timestamp(d["date"]).date(), []).append(("B", ticks, bool(r and r["Gap cerrado antes de entrar"])))
    Fx = cf.features(raw)
    Fx = Fx[(Fx.entrada == 540) & Fx["Últimos 12 min a favor"] & Fx["Noche 20-50 pts"]]
    days = {x[0]: x for x in g.prep(raw)}
    for r in Fx.itertuples():
        t = g.run([days[r.fecha]], 60, "parcial 1:1 + BE + 2R", 540, 20)
        if not len(t):
            continue
        t0 = pd.Timestamp(f"{r.fecha} 09:00", tz="America/Mexico_City").tz_convert("America/New_York")
        z = gp.rasgos(G, r.fecha, t0, r.s)
        ops.setdefault(r.fecha, []).append(("S", float(t.R.iloc[0]), bool(z and z["Gap cerrado antes de entrar"])))
    return ops


def pnl_dia(lst, mb, sp, por_gap):
    tot = 0.0
    for mod, v, cerrado in lst:
        k = 1.0 if (not por_gap or cerrado) else 0.5
        if mod == "B" and mb:
            n = mb * k
            tot += v * (n / 2) * 1.25 - n * 2.49
        elif mod == "S" and sp:
            n = sp * k
            tot += v * 75.0 * n          # R por MES: riesgo 15 pts x 5 USD, comisión ya incluida en R
    return tot


def evaluacion(dias, ops, i0, mb, sp, por_gap):
    bal = hwm = mx = 0.0
    for k in range(i0, len(dias)):
        if dias[k] not in ops:
            continue
        u = pnl_dia(ops[dias[k]], mb, sp, por_gap)
        bal += u; mx = max(mx, u); hwm = max(hwm, bal)
        if bal <= min(hwm - DD, LOCK):
            return "pierde", k
        if bal >= META and mx <= CONS * bal:
            return "pasa", k
    return "no termina", len(dias) - 1


def fondeada(dias, ops, i0, mb, sp, por_gap):
    bal = hwm = 0.0; buenos = 0; cobrado = 0.0; primero = None; nret = 0
    for k in range(i0, min(len(dias), i0 + 252)):
        if dias[k] not in ops:
            continue
        u = pnl_dia(ops[dias[k]], mb, sp, por_gap)
        bal += u; hwm = max(hwm, bal); buenos += u >= 150
        if bal <= min(hwm - DD, LOCK):
            return cobrado, primero, nret, True
        if buenos >= 5 and bal > 0:
            retiro = bal * 0.5
            cobrado += retiro * 0.9; bal -= retiro; buenos = 0; nret += 1
            if primero is None:
                primero = k - i0 + 1
    return cobrado, primero, nret, False


def main():
    ops = operaciones()
    dias = list(pd.bdate_range("2024-01-02", "2026-11-04").date)
    starts = [i for i, d in enumerate(dias) if d <= pd.Timestamp("2025-11-04").date()]
    variantes = [("Solo Modelo B", (8, 0, False), (6, 0, False)),
                 ("Combinado", (8, 4, False), (6, 3, False)),
                 ("Combinado + tamaño por gap", (8, 4, True), (6, 3, True)),
                 ("Combinado + tamaño por gap (más grande)", (12, 6, True), (8, 4, True))]
    filas = []
    for nom, ev, fo in variantes:
        res = [evaluacion(dias, ops, i, *ev) for i in starts]
        pasa = [(i, k) for i, (r, k) in zip(starts, res) if r == "pasa"]
        fin = [r for r, _ in res if r != "no termina"]
        F = [fondeada(dias, ops, k + 1, *fo) for _, k in pasa]
        prim = [x[1] for x in F if x[1] is not None]
        p = len(pasa) / len(res)
        cob = np.mean([x[0] for x in F]) if F else 0
        filas.append(dict(variante=nom, mes_eval=f"{ev[0]} B + {ev[1]} SP", mes_fondeada=f"{fo[0]} B + {fo[1]} SP",
                          pasa_eval_pct=round(100 * p, 1), pierde_eval_pct=round(100 * sum(r == "pierde" for r in fin) / len(res), 1),
                          pasa_de_las_que_terminan=round(100 * len(pasa) / len(fin), 1) if fin else None,
                          dias_habiles_para_pasar=int(np.median([k - i + 1 for i, k in pasa])) if pasa else None,
                          llega_1er_retiro_pct=round(100 * len(prim) / len(F), 1) if F else None,
                          dias_habiles_1er_retiro=int(np.median(prim)) if prim else None,
                          retiros_en_12_meses=round(np.mean([x[2] for x in F]), 1) if F else None,
                          se_quema_fondeada_pct=round(100 * np.mean([x[3] for x in F]), 1) if F else None,
                          cobrado_por_fondeada=round(cob), neto_por_eval=round(p * cob - FEE)))
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/lucid50_combinado.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
