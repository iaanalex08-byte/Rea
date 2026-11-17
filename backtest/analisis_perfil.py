"""Modelo B + perfil de mercado: ¿qué días conviene saltar?

Uso:  python3 backtest/analisis_perfil.py datos/
(datos/ = carpeta con las velas de 1 minuto SPXUSD de HistData, igual que run.py)

Divide la muestra en 2025 (para buscar patrones) y 2026 (para comprobarlos).
Un filtro solo vale si mejora en los dos años.
"""
import sys
import numpy as np
import pandas as pd
from engine import load, run, stats
from perfil import rasgos


def tabla(R, col, orden=None):
    filas = []
    for k, g in R.groupby(col, dropna=False):
        fila = {col: k}
        for nombre, sub in [('2025', g[g.anio == 2025]), ('2026', g[g.anio == 2026]), ('total', g)]:
            if len(sub) == 0:
                continue
            s = stats(sub)
            fila[f'n {nombre}'] = s['n']
            fila[f'win {nombre}'] = round(s['wr'] * 100, 1)
            fila[f'PF {nombre}'] = round(s['pf'], 2)
            fila[f'$/op {nombre}'] = round(s['exp'], 0)
        filas.append(fila)
    t = pd.DataFrame(filas)
    return t.set_index(col).reindex(orden) if orden else t.set_index(col)


def cubeta_room(r):
    if r < 7.5:
        return '1 · obstáculo antes de TP1 (<7.5)'
    if r < 15:
        return '2 · obstáculo entre TP1 y TP2'
    return '3 · espacio libre (>15)'


def resumen(nombre, R, mask):
    a, b = R[mask & (R.anio == 2025)], R[mask & (R.anio == 2026)]
    sa, sb, st = stats(a), stats(b), stats(R[mask])
    print(f'{nombre:44s} ops {st["n"]:4d}  win {st["wr"]*100:5.1f}%  PF {st["pf"]:.2f}  neto {st["net"]:+10,.0f}  '
          f'DD {st["mdd"]:+9,.0f}  |  PF 2025 {sa["pf"]:.2f}  PF 2026 {sb["pf"]:.2f}')


if __name__ == '__main__':
    pd.set_option('display.width', 220)
    pd.set_option('display.max_columns', 30)
    df = load(sys.argv[1] if len(sys.argv) > 1 else 'datos')
    R = rasgos(run(df), df)
    R = R[R['loc'].notna()].copy()
    R['anio'] = pd.to_datetime(R.date).dt.year
    R['espacio'] = R.room.apply(cubeta_room)
    R['temporada'] = np.where(R.ny_min >= 660, 'verano (11:12 NY)', 'invierno (10:12 NY)')

    for col in ['loc', 'espacio', 'forma', 'ib', 'mig', 'apertura_dir', 'temporada']:
        print(f'\n=== {col} ===')
        print(tabla(R, col))

    print('\n=== Filtros (elegidos con 2025, comprobados con 2026) ===')
    dentro = R['loc'] == 'dentro del valor'
    forma_fav = R.forma == 'a favor (P/b)'
    ext_fav = R.ib == 'extensión a favor'
    resumen('Modelo B sin filtro', R, R['loc'].notna())
    resumen('A: saltar si entra dentro del valor de ayer', R, ~dentro)
    resumen('B: saltar extensión del IB a favor (verano)', R, ~ext_fav)
    resumen('C: saltar perfil P/b a favor', R, ~forma_fav)
    resumen('A + C', R, ~dentro & ~forma_fav)
