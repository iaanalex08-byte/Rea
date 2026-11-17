"""Análisis de mejoras del Modelo B con EMA + perfil A + C.

Uso:  python3 backtest/mejoras.py datos/  [salida.json]

Cada idea se prueba igual: se mide el factor de beneficio (PF) en 2025 y en 2026 por separado.
Una idea solo cuenta como mejora si mejora a la base en los DOS años (se elige con 2025, se comprueba con 2026).
"""
import json
import sys
import numpy as np
import pandas as pd
from engine import load
from perfil import rasgos
import rejilla_filtro as rf

BASE = (45, 30, 60)


def metr(u, y):
    u, y = np.asarray(u, float), np.asarray(y)
    out = {}
    for k, m in [('2025', y == '2025'), ('2026', y == '2026'), ('total', np.ones(len(u), bool))]:
        x = u[m]
        g, l = x[x > 0].sum(), -x[x <= 0].sum()
        e = np.cumsum(x)
        dd = (e - np.maximum.accumulate(np.maximum(e, 0))).min() if len(x) else 0
        out[k] = dict(n=int(len(x)), pf=round(g / l, 3) if l else None, neto=round(float(x.sum())), win=round(float((x > 0).mean() * 100), 1) if len(x) else None,
                      dd=round(float(dd)))
    return out


def con_filtros(df, D, hm=(9, 12)):
    """Agrega a cada día los rasgos del perfil (A, C, rangos...) para la hora de entrada dada."""
    T = pd.DataFrame([dict(date=d['date'], dir=d['dir'], entry=d['entry'], ema=d['ema'], usd=0.0, out='') for d in D])
    R = rasgos(T, df, hm=hm)
    feats = R.set_index('date')
    res = []
    for d in D:
        if d['date'] not in feats.index:
            continue
        f = feats.loc[d['date']]
        if not isinstance(f['loc'], str):
            continue
        d = dict(d)
        d.update(loc=f['loc'], forma=f.forma, y_rango=f.y_rango, rango_dev=f.rango_dev, apertura_dir=f.apertura_dir, mig=f.mig, ib=f.ib,
                 pasa=(f['loc'] != 'dentro del valor') and (f.forma != 'a favor (P/b)'))
        res.append(d)
    return res


def fila(grupo, idea, detalle, days, br=BASE, be=True, base_ref=None):
    u = [rf.bracket(d, *br, be=be) for d in days]
    y = [d['date'][:4] for d in days]
    m = metr(u, y)
    mejora = None
    if base_ref is not None and m['2025']['pf'] and m['2026']['pf']:
        mejora = m['2025']['pf'] > base_ref['2025']['pf'] and m['2026']['pf'] > base_ref['2026']['pf']
    return dict(grupo=grupo, idea=idea, detalle=detalle, ops=m['total']['n'], win=m['total']['win'], pf=m['total']['pf'], neto=m['total']['neto'],
                dd=m['total']['dd'], pf_2025=m['2025']['pf'], pf_2026=m['2026']['pf'], n_2025=m['2025']['n'], n_2026=m['2026']['n'],
                mejora_ambos='sí' if mejora else ('no' if mejora is not None else 'base'))


if __name__ == '__main__':
    df = load(sys.argv[1] if len(sys.argv) > 1 else 'datos')
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'mejoras.json'
    rows = []
    D = rf.dias(df)
    F = con_filtros(df, D)
    AC = [d for d in F if d['pasa']]
    ref = metr([rf.bracket(d, *BASE) for d in AC], [d['date'][:4] for d in AC])
    rows.append(fila('Base', 'EMA + perfil A + C', '9:12 CDMX · EMA 20 de 3 min · 45/30/60', AC, base_ref=None))
    rows.append(fila('Base', 'Solo EMA (sin perfil)', 'Referencia', F, base_ref=ref))

    # 1. Bracket
    for br in [(25, 30, 160), (25, 35, 160), (30, 30, 100), (35, 30, 120), (45, 30, 120), (45, 40, 100)]:
        rows.append(fila('Bracket', f'{br[0]} / {br[1]} / {br[2]}', 'SL / TP1 / TP2 en ticks', AC, br=br, base_ref=ref))
    rows.append(fila('Gestión', 'Sin break-even tras TP1', 'El contrato 2 mantiene el stop original', AC, be=False, base_ref=ref))

    # 2. Hora de entrada (los filtros se recalculan para cada hora)
    for hm in [(8, 48), (9, 0), (9, 6), (9, 18), (9, 24), (9, 30), (9, 42), (10, 0)]:
        Fh = con_filtros(df, rf.dias(df, hm=hm), hm=hm)
        rows.append(fila('Hora de entrada', f'{hm[0]}:{hm[1]:02d} CDMX', 'Con filtros A + C recalculados', [d for d in Fh if d['pasa']], base_ref=ref))

    # 3. Parámetros de la EMA
    for ln, tf in [(10, 3), (34, 3), (50, 3), (20, 1), (20, 5), (50, 5), (9, 1)]:
        De = rf.dias(df, ema_len=ln, ema_tf=tf)
        Fe = con_filtros(df, De)
        rows.append(fila('EMA', f'EMA {ln} de {tf} min', 'Con filtros A + C', [d for d in Fe if d['pasa']], base_ref=ref))

    # 3b. Propuesta: cambios que mejoran en los dos años y no dependen de un umbral fino
    F5 = con_filtros(df, rf.dias(df, ema_len=20, ema_tf=5))
    AC5 = [d for d in F5 if d['pasa']]
    th5 = float(np.median([abs(d['entry'] - d['ema']) for d in AC5 if d['date'].startswith('2025')]))
    rows.append(fila('Propuesta', 'EMA 20 de 5 min + A + C + 35/30/120', 'Recomendada', AC5, br=(35, 30, 120), base_ref=ref))
    rows.append(fila('Propuesta', 'EMA 20 de 5 min + A + C + 25/30/160', 'Alternativa con objetivo más lejano', AC5, br=(25, 30, 160), base_ref=ref))
    rows.append(fila('Propuesta', 'Lo anterior + precio cerca de la EMA', f'≤ {th5:.1f} pts · no recomendada: solo funciona a las 9:12',
                     [d for d in AC5 if abs(d['entry'] - d['ema']) <= th5], br=(35, 30, 120), base_ref=ref))

    # 3c. Sensibilidad al minuto exacto de entrada
    for mi in [6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18]:
        hm = (9, mi)
        Fb = [d for d in con_filtros(df, rf.dias(df, hm=hm), hm=hm) if d['pasa']]
        Fm = [d for d in con_filtros(df, rf.dias(df, ema_len=20, ema_tf=5, hm=hm), hm=hm) if d['pasa']]
        rows.append(fila('Minuto · actual', f'9:{mi:02d}', 'EMA 20 de 3 min + A + C + 45/30/60', Fb, base_ref=ref))
        rows.append(fila('Minuto · propuesta', f'9:{mi:02d}', 'EMA 20 de 5 min + A + C + 35/30/120', Fm, br=(35, 30, 120), base_ref=ref))
        rows.append(fila('Minuto · propuesta + cerca EMA', f'9:{mi:02d}', f'≤ {th5:.1f} pts de la EMA', [d for d in Fm if abs(d['entry'] - d['ema']) <= th5],
                         br=(35, 30, 120), base_ref=ref))

    # 4. Filtros extra sobre A + C (umbrales fijados con la mediana de 2025)
    d25 = [d for d in AC if d['date'].startswith('2025')]
    med = lambda k: float(np.nanmedian([d[k] for d in d25]))
    dist = lambda d: abs(d['entry'] - d['ema'])
    md = float(np.median([dist(d) for d in d25]))
    yr, rd = med('y_rango'), med('rango_dev')
    rows.append(fila('Filtro extra', 'Rango de ayer mayor a la mediana', f'> {yr:.0f} pts (mediana 2025)', [d for d in AC if d['y_rango'] > yr], base_ref=ref))
    rows.append(fila('Filtro extra', 'Rango de ayer menor a la mediana', f'≤ {yr:.0f} pts', [d for d in AC if d['y_rango'] <= yr], base_ref=ref))
    rows.append(fila('Filtro extra', 'Rango del día a las 9:12 mayor a la mediana', f'> {rd:.0f} pts', [d for d in AC if d['rango_dev'] > rd], base_ref=ref))
    rows.append(fila('Filtro extra', 'Rango del día a las 9:12 menor a la mediana', f'≤ {rd:.0f} pts', [d for d in AC if d['rango_dev'] <= rd], base_ref=ref))
    rows.append(fila('Filtro extra', 'Precio lejos de la EMA', f'> {md:.1f} pts (mediana 2025)', [d for d in AC if dist(d) > md], base_ref=ref))
    rows.append(fila('Filtro extra', 'Precio cerca de la EMA', f'≤ {md:.1f} pts', [d for d in AC if dist(d) <= md], base_ref=ref))
    rows.append(fila('Filtro extra', 'Apertura no en contra', 'Saltar si abrió fuera del valor en contra de la señal', [d for d in AC if d['apertura_dir'] != 'en contra'], base_ref=ref))
    rows.append(fila('Filtro extra', 'Migración del valor no plana', 'Saltar si el POC de ayer casi no se movió', [d for d in AC if d['mig'] != 'plana'], base_ref=ref))
    for dow, nombre in enumerate(['lunes', 'martes', 'miércoles', 'jueves', 'viernes']):
        rows.append(fila('Día de la semana', f'Sin {nombre}', 'Saltar ese día', [d for d in AC if pd.Timestamp(d['date']).dayofweek != dow], base_ref=ref))

    # 5. Noticias (calendario del tablero original)
    try:
        news = {t[0]: t[5] for t in json.load(open(sys.argv[3] if len(sys.argv) > 3 else '../data-modelo-b.json'))['trades']}
        rows.append(fila('Noticias', 'Sin días de NFP / CPI', 'Saltar días con dato de las 8:30', [d for d in AC if 'NFP' not in news.get(d['date'], '')], base_ref=ref))
        rows.append(fila('Noticias', 'Solo días con noticia', 'Referencia', [d for d in AC if 'NFP' in news.get(d['date'], '')], base_ref=ref))
    except FileNotFoundError:
        pass

    json.dump({'rows': rows}, open(out_path, 'w'), ensure_ascii=False)
    pd.set_option('display.width', 250)
    print(pd.DataFrame(rows)[['grupo', 'idea', 'ops', 'win', 'pf', 'neto', 'dd', 'pf_2025', 'pf_2026', 'mejora_ambos']].to_string(index=False))
