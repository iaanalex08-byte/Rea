#!/usr/bin/env python3
"""
Simulación Monte Carlo a N años a partir de las operaciones reales de un backtest.

Remuestrea (con reemplazo) los resultados en puntos de `operaciones.csv` para generar
miles de trayectorias posibles de 3 años y mide la distribución del neto y del drawdown.

    python3 backtest/montecarlo.py backtest/resultados/operaciones.csv --trades-per-year 170
"""
import argparse

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("operaciones")
    p.add_argument("--years", type=float, default=3)
    p.add_argument("--trades-per-year", type=float, required=True)
    p.add_argument("--sims", type=int, default=10000)
    p.add_argument("--qty", type=float, default=50)
    p.add_argument("--point-value", type=float, default=5.0)
    p.add_argument("--commission", type=float, default=0.0, help="$ ida y vuelta por contrato")
    p.add_argument("--slippage", type=float, default=0.0, help="puntos por operación")
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()

    pts = pd.read_csv(a.operaciones)["pts"].to_numpy(float)
    usd = (pts - a.slippage) * a.point_value * a.qty - a.commission * a.qty
    n = int(round(a.years * a.trades_per_year))
    rng = np.random.default_rng(a.seed)
    paths = rng.choice(usd, size=(a.sims, n), replace=True).cumsum(axis=1)
    final = paths[:, -1]
    peak = np.maximum.accumulate(np.concatenate([np.zeros((a.sims, 1)), paths], axis=1), axis=1)[:, 1:]
    mdd = (paths - peak).min(axis=1)

    q = lambda x, k: np.percentile(x, k)
    print(f"Muestra: {len(usd)} operaciones reales, esperanza {usd.mean():,.2f} $/operación")
    print(f"Simulación: {a.sims:,} trayectorias de {n} operaciones (~{a.years:g} años), "
          f"{a.qty:g} contratos × ${a.point_value:g}/pt, comisión ${a.commission:g}, slippage {a.slippage:g} pts")
    print(f"  Prob. de terminar en ganancia: {100 * (final > 0).mean():.1f}%")
    print(f"  Neto final  P5 / P50 / P95:   ${q(final, 5):,.0f} / ${q(final, 50):,.0f} / ${q(final, 95):,.0f}")
    print(f"  Máx. drawdown mediana / peor 5%: ${q(mdd, 50):,.0f} / ${q(mdd, 5):,.0f}")


if __name__ == "__main__":
    main()
