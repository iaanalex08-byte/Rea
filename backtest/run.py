"""Corre el Modelo B en velas de 1 y 3 minutos y las variantes de dirección.

Uso:
  1. Descarga de histdata.com las velas de 1 minuto SPXUSD (ASCII, M1) de 2025 y de cada mes de 2026
     y descomprime los CSV en una carpeta, por ejemplo datos/.
  2. python3 backtest/run.py datos/
"""
import sys
from engine import load, run, stats

df = load(sys.argv[1] if len(sys.argv) > 1 else 'datos')
for nombre, kw in [('1 min', dict(exec_tf=1)), ('3 min', dict(exec_tf=3)),
                   ('3 min · EMA 50', dict(exec_tf=3, ema_len=50)), ('3 min · EMA 10', dict(exec_tf=3, ema_len=10)),
                   ('3 min · siempre compra', dict(exec_tf=3, side_mode='1')), ('3 min · siempre vende', dict(exec_tf=3, side_mode='-1')),
                   ('3 min · al revés de la EMA', dict(exec_tf=3, side_mode='inv'))]:
    s = stats(run(df, **kw))
    print(f"{nombre:28s} ops {s['n']:4d}  win {s['wr']*100:5.1f}%  PF {s['pf']:.3f}  neto {s['net']:+10,.2f}  DD {s['mdd']:+10,.2f}")
