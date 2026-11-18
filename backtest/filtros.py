"""Prueba filtros de volatilidad sobre el Modelo B (velas de 1 minuto).

Cada filtro deja de operar los días en que una medida de volatilidad, conocida antes de la
entrada de las 9:12 CDMX, pasa de un umbral (o queda por debajo, según el sentido).
El umbral se elige solo con 2025 (en muestra) y se comprueba en 2026 (fuera de muestra),
para no sobreajustar.

Uso: python3 backtest/filtros.py datos/   (misma carpeta de HistData que run.py)
Escribe backtest/filtros_resultados.csv con cada operación y sus medidas.
"""
import os, sys
import numpy as np, pandas as pd
from engine import load, run, features, stats

MEDIDAS = {
    'rango_apertura': 'Rango 9:30 NY → entrada',
    'rel_apertura': 'Rango de apertura / ATR10',
    'rango_ayer': 'Rango del día anterior',
    'atr10': 'ATR de 10 sesiones',
    'gap': 'Gap de apertura',
    'dist_ema': 'Distancia entrada–EMA20',
}
CUANTILES = [0.6, 0.7, 0.8, 0.9]  # umbral = cuantil de 2025
MIN_OPS = 0.5  # el filtro debe conservar al menos la mitad de las operaciones de 2025


def fila(u):
    u = np.asarray(u)
    if len(u) == 0:
        return dict(n=0, pf=np.nan, net=0.0, mdd=0.0)
    gp, gl = u[u > 0].sum(), -u[u <= 0].sum()
    eq = np.cumsum(u)
    return dict(n=len(u), pf=gp / gl if gl else np.inf, net=u.sum(),
                mdd=(eq - np.maximum.accumulate(np.maximum(eq, 0))).min())


def fmt(s):
    return f"{s['n']:4d} ops  PF {s['pf']:.2f}  neto {s['net']:+9,.0f}  DD {s['mdd']:+9,.0f}"


def main(folder):
    df = load(folder)
    T = run(df)
    T = T.merge(features(df, T), on='date')
    T['año'] = T.date.str[:4]
    ins, oos = T[T.año == '2025'], T[T.año == '2026']

    print('Base (sin filtro)')
    print(f"  2025 {fmt(fila(ins.usd))}\n  2026 {fmt(fila(oos.usd))}\n  todo {fmt(fila(T.usd))}\n")

    print('Stop completo según cuartil de cada medida (todo el periodo)')
    for m, nombre in MEDIDAS.items():
        q = pd.qcut(T[m], 4, labels=['Q1 bajo', 'Q2', 'Q3', 'Q4 alto'])
        g = T.groupby(q, observed=True)
        stop = g.out.apply(lambda s: (s == 'Stop (−2)').mean())
        pf = g.usd.apply(lambda u: fila(u)['pf'])
        print(f"  {nombre:28s} " + '  '.join(f"{k}: stop {stop[k]:.0%} PF {pf[k]:.2f}" for k in stop.index))
    print()

    res = []
    for m, nombre in MEDIDAS.items():
        for sentido in ('alto', 'bajo'):
            for qq in CUANTILES:
                thr = ins[m].quantile(qq if sentido == 'alto' else 1 - qq)
                keep = (lambda X: X[m] <= thr) if sentido == 'alto' else (lambda X: X[m] >= thr)
                a, b = fila(ins[keep(ins)].usd), fila(oos[keep(oos)].usd)
                if a['n'] < MIN_OPS * len(ins):
                    continue
                res.append(dict(medida=m, nombre=nombre, quita=f"{'>' if sentido == 'alto' else '<'} {thr:.2f}" if m == 'rel_apertura' else f"{'>' if sentido == 'alto' else '<'} {thr:.1f} pts",
                                pf25=a['pf'], net25=a['net'], n25=a['n'], pf26=b['pf'], net26=b['net'], n26=b['n'],
                                dd_todo=fila(T[keep(T)].usd)['mdd']))
    R = pd.DataFrame(res).sort_values('pf25', ascending=False)
    print('Filtros (umbral elegido en 2025, ordenados por PF de 2025)')
    print(f"  {'medida':28s} {'no opera si':>14s} | {'2025 ops':>8s} {'PF':>5s} {'neto':>8s} | {'2026 ops':>8s} {'PF':>5s} {'neto':>8s} | {'DD todo':>8s}")
    for r in R.itertuples():
        print(f"  {r.nombre:28s} {r.quita:>14s} | {r.n25:8d} {r.pf25:5.2f} {r.net25:+8,.0f} | {r.n26:8d} {r.pf26:5.2f} {r.net26:+8,.0f} | {r.dd_todo:+8,.0f}")

    T.to_csv(os.path.join(os.path.dirname(__file__), 'filtros_resultados.csv'), index=False, float_format='%.3f')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
