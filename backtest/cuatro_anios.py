"""Prueba fuera de muestra: Modelo B en 2023 y 2024, años que no se usaron para elegir nada.

Uso:  python3 backtest/cuatro_anios.py datos_2023_2025/ datos/ cuatro_anios.json

datos_2023_2025/ = velas SPXUSD 1 min de HistData de 2023, 2024 y 2025 (2025 solo para el perfil del día anterior)
datos/           = las de 2025 y 2026 que usa el resto del backtest
Compara solo EMA contra EMA + A + C, EMA 20 de 3 y de 5 min y cinco brackets, año por año.
"""
import json
import sys
import numpy as np
from engine import load
import rejilla_filtro as rf
from mejoras import con_filtros

ANIOS = ['2023', '2024', '2025', '2026']


def main(viejos, nuevos, salida):
    sets = {}
    for carpeta, anios in [(viejos, ('2023', '2024')), (nuevos, ('2025', '2026'))]:
        df = load(carpeta)
        for clave, kw in [('EMA 20 de 3 min', {}), ('EMA 20 de 5 min', dict(ema_len=20, ema_tf=5))]:
            F = con_filtros(df, rf.dias(df, **kw))
            sets.setdefault(clave, []).extend(d for d in F if d['date'][:4] in anios)
    rows = []
    for ema, F in sets.items():
        for ac in (False, True):
            ds = [d for d in F if d['pasa']] if ac else F
            for br in [(45, 30, 60), (35, 30, 120), (30, 30, 100), (25, 30, 160), (45, 30, 120)]:
                r = dict(version='EMA + perfil A + C' if ac else 'Solo EMA', ema=ema, bracket='%d / %d / %d' % br)
                r['clave'] = f"{r['version']} · {ema} · {r['bracket']}"
                todo = []
                for y in ANIOS:
                    x = np.array([rf.bracket(d, *br) for d in ds if d['date'].startswith(y)])
                    r['pf_' + y] = round(float(x[x > 0].sum() / -x[x <= 0].sum()), 2)
                    r['n_' + y] = int(len(x))
                    todo += list(x)
                x = np.array(todo)
                e = np.cumsum(x)
                r.update(ops=int(len(x)), win=round(float((x > 0).mean() * 100), 1), pf=round(float(x[x > 0].sum() / -x[x <= 0].sum()), 2),
                         neto=round(float(x.sum())), dd=round(float((e - np.maximum.accumulate(np.maximum(e, 0))).min())),
                         anios_pf_mayor_1=int(sum(r['pf_' + y] > 1 for y in ANIOS)))
                rows.append(r)
    meta = [{'label': 'cuatro_anios.py', 'value': open(__file__).read(), 'type': 'code', 'lang': 'python'},
            {'label': 'Entradas', 'value': 'velas SPXUSD 1 min de HistData, 2023 – 13 nov 2026 · engine.py, perfil.py, rejilla_filtro.py, mejoras.py'}]
    json.dump({'rows': rows, 'meta': meta}, open(salida, 'w'), ensure_ascii=False)
    for r in rows:
        print(f"{r['clave']:58s} " + ' '.join(f"{y[2:]} {r['pf_' + y]:.2f}" for y in ANIOS) + f" | PF {r['pf']:.2f} DD {r['dd']:+,} años>1 {r['anios_pf_mayor_1']}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'cuatro_anios.json')
