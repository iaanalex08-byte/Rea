"""Corre el Modelo B · Más dinero sobre los contratos de NinjaTrader y muestra resultados por año.

Uso:  python3 backtest/run_mas_dinero.py backtest/datos
"""
import sys

import pandas as pd

import mas_dinero as M


def year_table(trades, col='usd_8mes'):
    rows = []
    for y, g in trades.groupby(pd.to_datetime(trades.fecha).dt.year):
        s = M.stats(g, col)
        rows.append({'año': y, 'ops': s['n'], 'gana %': round(100 * s['wr'], 1), 'PF': round(s['pf'], 2),
                     'neto': round(s['net']), 'caída máx': round(s['mdd'])})
    return pd.DataFrame(rows)


def main(folder):
    contracts = M.load_contracts(folder)
    chosen = M.choose_contracts(contracts)
    prep = M.prepare(contracts)
    trades, _ = M.run(prep, chosen)
    print(year_table(trades).to_string(index=False))
    for col in ('usd_8mes', 'usd_2es'):
        s = M.stats(trades, col)
        print(f"Total {col}: ops {s['n']}  gana {100 * s['wr']:.1f}%  PF {s['pf']:.2f}  "
              f"neto {s['net']:+,.0f}  caída {s['mdd']:+,.0f}  racha {s['racha']}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
