#!/usr/bin/env python3
"""Metodología del usuario en Lucid 50K Flex:
 1) Evaluación (objetivo $3,000, pérdida máx. $2,000 EOD, consistencia 40 %): SP500 9:00 con la tendencia
    (noche >= 20 pts, SL 15 pts), $400 de riesgo, una operación al día.
 2) Fondeada (pérdida máx. $2,000, retiro tras 5 días de >= $150, sin consistencia):
    a) "día fuerte": SP500 9:00, $500 de riesgo, mitad en 1:1 + BE, resto a 2R; se repite hasta tener un día ganador;
    b) días mínimos con el Rascacielos (TP 10 / SL 50.75, 9 MNQ) hasta juntar 5 días de >= $150;
    c) retiro (50 % o 100 % de la ganancia, sin mínimo ni máximo, se cobra el 90 %) y vuelve a (a). Hasta quemarse o 12 meses.
Se prueba empezando cada día hábil 2024-2026 y se compara con el plan del NQ (2 MNQ c/u) ya fondeado.

    python3 backtest/metodo_usuario.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import rascacielos_50k as RZ  # noqa: E402
import roi_fondeada as R  # noqa: E402

ALL = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
FEE = 80.50


def sp(var, riesgo):
    o = pd.read_csv("backtest/resultados/sp500_0900_ops.csv"); o = o[o.variante == var]
    k = riesgo / 150.0
    d = {pd.Timestamp(f).date(): (u * k, (-u * k if u <= 0 else 0.0)) for f, u in zip(o.fecha, o.usd)}
    return [d.get(x) for x in ALL]


def evaluacion(days, s):
    bal = peak = best = 0.0; n = 0
    for k in range(s, len(days)):
        if days[k] is None:
            continue
        pnl, mae = days[k]; n += 1
        thr = min(peak - 2000, 100)
        if bal - mae <= thr or bal + pnl < thr:
            return False, n, k
        bal += pnl; peak = max(peak, bal); best = max(best, pnl)
        if bal >= 3000 and best <= 0.4 * bal:
            return True, n, k
    return None, n, None


def fondeada(spd, rzd, s, frac, horizon=252):
    bal = peak = 0.0; good = 0; fase = "fuerte"; cobrado = 0.0; n = 0
    for k in range(s, min(len(ALL), s + horizon)):
        if fase == "fuerte":
            if spd[k] is None:
                continue
            pnl, mae = spd[k]
        else:
            pnl, mae = rzd[k]
        thr = min(peak - 2000, 100)
        if bal - mae <= thr or bal + pnl < thr:
            return cobrado, n, True
        bal += pnl; peak = max(peak, bal); good += pnl >= 150
        if fase == "fuerte" and pnl > 0:
            fase = "minimos"
        if good >= 5 and bal > 0:
            req = frac * bal
            cobrado += req * 0.9; n += 1; bal -= req; good = 0; fase = "fuerte"
    return cobrado, n, False


def main():
    rz = RZ.rasca(10, 50.75, 9)
    fuerte = sp("Parcial 1:1 + BE + 2R", 500)
    rows = []
    for var in ("1:2", "1:3", "Parcial 1:1 + BE + 2R", "Parcial 1:1 + BE + 3R"):
        ev = sp(var, 400)
        res = [evaluacion(ev, s) for s in range(len(ALL) - 150)]
        res = [r for r in res if r[0] is not None]
        ok = [r for r in res if r[0]]
        p = len(ok) / len(res)
        nops = [r[1] for r in ok]
        for frac in (0.5, 1.0):
            cash = []
            for r in ok:
                c, n, b = fondeada(fuerte, rz, r[2] + 1, frac)
                cash.append(c)
            cash = np.array(cash)
            neto = p * cash.mean() - FEE
            rows.append({"evaluación SP500 $400": var, "pasa %": round(100 * p, 1),
                         "operaciones para pasar (prom.)": round(np.mean(nops), 1),
                         "pasa en <= 3 operaciones %": round(100 * np.mean([x <= 3 for x in nops]) * p, 1),
                         "retira": f"{int(frac * 100)} %", "cobrado por cuenta fondeada": round(cash.mean()),
                         "no cobra nada %": round(100 * (cash == 0).mean(), 1),
                         "neto esperado por evaluación comprada": round(neto)})
    T = pd.DataFrame(rows)
    # comparación: misma evaluación, pero ya fondeado con el plan del NQ (2 MNQ c/u)
    nq = R.nq(2)
    ev = sp("1:3", 400)
    res = [evaluacion(ev, s) for s in range(len(ALL) - 150)]; res = [r for r in res if r[0] is not None]
    ok = [r for r in res if r[0]]; p = len(ok) / len(res)
    for frac in (0.5,):
        cash = []
        for r in ok:
            s = r[2] + 1; bal = peak = 0.0; good = 0; c = 0.0
            for pnl, mae in nq[s:s + 252]:
                thr = min(peak - 2000, 100)
                if bal - mae <= thr or bal + pnl < thr:
                    break
                bal += pnl; peak = max(peak, bal); good += pnl >= 150
                if good >= 5 and bal > 0:
                    c += frac * bal * 0.9; bal -= frac * bal; good = 0
            cash.append(c)
        cash = np.array(cash)
        T.loc[len(T)] = {"evaluación SP500 $400": "1:3 → fondeado con plan NQ 2 MNQ", "pasa %": round(100 * p, 1),
                         "operaciones para pasar (prom.)": None, "pasa en <= 3 operaciones %": None, "retira": "50 %",
                         "cobrado por cuenta fondeada": round(cash.mean()), "no cobra nada %": round(100 * (cash == 0).mean(), 1),
                         "neto esperado por evaluación comprada": round(p * cash.mean() - FEE)}
    T.to_csv("backtest/resultados/metodo_usuario.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
