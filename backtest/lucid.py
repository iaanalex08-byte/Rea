#!/usr/bin/env python3
"""ROI por cuenta de fondeo con la estrategia de entrada a mercado (resultados diarios del backtest).

Reglas modeladas (LucidFlex, según fuentes públicas; verificar en Lucid):
- Drawdown de fin de día con arrastre: límite = máx(saldo al cierre) - DD; se fija en +100 cuando llega ahí.
  Se rompe si durante el día el saldo + la peor pérdida no realizada cae por debajo del límite.
- Evaluación (opcional): llegar a +objetivo antes de romper el drawdown.
- Cuenta fondeada: tras N días con ganancia >= mínimo (no tienen que ser seguidos) y saldo positivo,
  se retira el 50 % de la ganancia (máx. tope, mín. 500) y se cobra el 90 %. Se repite hasta perder la cuenta.

    python3 backtest/lucid.py backtest/resultados/mercado_1m.csv --costo 45
"""
import argparse

import numpy as np
import pandas as pd


def account(days, start, a, with_eval):
    """Recorre días desde start. Devuelve (pasó_eval, cobros_netos, n_retiros, días_usados)."""
    k = start
    if with_eval:
        bal, peak = 0.0, 0.0
        while True:
            if k >= len(days):
                return None
            pnl, mae = days[k]
            thr = min(peak - a.dd, a.lock)
            if bal - mae <= thr or bal + pnl < thr:
                return (False, 0.0, 0, k - start + 1)
            bal += pnl
            peak = max(peak, bal)
            k += 1
            if bal >= a.objetivo:
                break
    bal, peak, good, cobrado, retiros = 0.0, 0.0, 0, 0.0, 0
    while k < len(days):
        pnl, mae = days[k]
        thr = min(peak - a.dd, a.lock)
        if bal - mae <= thr or bal + pnl < thr:
            return (True, cobrado, retiros, k - start + 1)
        bal += pnl
        peak = max(peak, bal)
        if pnl >= a.min_dia:
            good += 1
        k += 1
        if good >= a.dias and bal > 0:
            req = min(0.5 * bal, a.tope)
            if req >= a.min_retiro:
                cobrado += req * a.split
                retiros += 1
                bal -= req
                good = 0
    return (True, cobrado, retiros, None)  # sigue viva al final de los datos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ops", help="CSV de backtest/mercado.py")
    p.add_argument("--costo", type=float, default=45)
    p.add_argument("--dd", type=float, default=1000)
    p.add_argument("--lock", type=float, default=100)
    p.add_argument("--objetivo", type=float, default=1250)
    p.add_argument("--min-dia", type=float, default=150)
    p.add_argument("--dias", type=int, default=5)
    p.add_argument("--tope", type=float, default=1000)
    p.add_argument("--min-retiro", type=float, default=500)
    p.add_argument("--split", type=float, default=0.9)
    p.add_argument("--comision", type=float, default=0.0, help="$ por día (ida y vuelta, todos los contratos)")
    p.add_argument("--usd-por-punto", type=float, default=100, help="2 ES = 100")
    a = p.parse_args()
    t = pd.read_csv(a.ops)
    pnl = t.usd.to_numpy() - np.where(t.res.isin(["GANADA", "PERDIDA"]), a.comision, 0)
    mae = np.where(t.res == "PERDIDA", -pnl, t.mae.to_numpy() * a.usd_por_punto + a.comision)
    days = list(zip(pnl, mae))
    # 5 ganados seguidos (lo que planteaste)
    res = t.res.tolist()
    seq = [all(r == "GANADA" for r in res[k:k + a.dias]) for k in range(len(res) - a.dias + 1)]
    print(f"{len(t)} días | ganada ${pnl[t.res == 'GANADA'].mean():,.0f}  perdida ${pnl[t.res == 'PERDIDA'].mean():,.0f} | "
          f"{a.dias} días ganados SEGUIDOS: {100 * np.mean(seq):.1f}%")
    for with_eval in (False, True):
        runs = [account(days, s, a, with_eval) for s in range(len(days))]
        runs = [r for r in runs if r is not None]
        cobros = np.array([r[1] for r in runs])
        n = np.array([r[2] for r in runs])
        passed = np.mean([r[0] for r in runs])
        roi = (cobros.mean() - a.costo) / a.costo
        lbl = "Incluyendo pasar la evaluación" if with_eval else "Ya fondeado (sin evaluación)"
        print(f"\n=== {lbl} ===")
        if with_eval:
            print(f"Pasa la evaluación: {100 * passed:.1f}%")
        print(f"Cuentas con al menos 1 retiro: {100 * np.mean(n >= 1):.1f}%   con 2+: {100 * np.mean(n >= 2):.1f}%   "
              f"con 3+: {100 * np.mean(n >= 3):.1f}%")
        print(f"Cobro neto promedio por cuenta: ${cobros.mean():,.0f}  (mediana ${np.median(cobros):,.0f})")
        print(f"Costo por cuenta: ${a.costo:,.0f}  ->  ganancia esperada ${cobros.mean() - a.costo:,.0f} por cuenta, ROI {100 * roi:,.0f}%")
        print(f"Cuentas necesarias por cada retiro (promedio): {1 / max(1e-9, np.mean(n >= 1)):.1f}")


if __name__ == "__main__":
    main()
