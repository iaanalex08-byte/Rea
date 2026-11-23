"""Optimización del Modelo B · Más dinero con validación fuera de muestra.

Se optimiza SOLO con 2018–2022 (dentro de muestra) y se revisa en 2023–2026 (fuera de muestra).
Para probar cientos de brackets rápido, cada día guarda el máximo recorrido a favor y en contra
minuto a minuto; con eso se sabe en qué vela se toca cada nivel sin volver a recorrer las velas.

Uso:  python3 backtest/optimizar.py backtest/datos
"""
import itertools
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

import mas_dinero as M

IS_END = pd.Timestamp('2022-12-31').date()


def paths(prep, signals, p: M.Params):
    """Por señal: recorridos acumulados a favor/en contra (ticks), recorrido en contra por vela y cierre."""
    out = []
    ch, cm = map(int, p.close_at.split(':'))
    for s in signals.to_dict('records'):
        m1 = prep[s['contrato']]['m1']
        t_end = pd.Timestamp(s['fecha']).tz_localize(M.NY) + pd.Timedelta(hours=ch, minutes=cm)
        b = m1[(m1.index >= s['t']) & (m1.index < t_end)]
        d, e = s['dir'], s['entrada']
        fav = ((b.h.values - e) if d > 0 else (e - b.l.values)) / M.TICK
        adv = ((e - b.l.values) if d > 0 else (b.h.values - e)) / M.TICK
        last = (d * (b.c.values[-1] - e) / M.TICK) if len(b) else 0.0
        out.append((np.maximum.accumulate(fav) if len(b) else fav,
                    np.maximum.accumulate(adv) if len(b) else adv, adv, round(last)))
    return out


def bracket(pth, sl, tp1, tp2, be):
    """Ticks totales (dos mitades) y tipo de salida para un día."""
    cf, ca, adv, last = pth
    n = len(cf)
    i_sl = np.searchsorted(ca, sl)
    i_1 = np.searchsorted(cf, tp1)
    if i_sl <= i_1:
        return (-2 * sl, 'Stop') if i_sl < n else (2 * last, 'Cierre')
    i_2 = np.searchsorted(cf, tp2)
    if be:
        hit = np.nonzero(adv[i_1 + 1:] >= 0)[0]
        i_be = i_1 + 1 + hit[0] if len(hit) else n
        if i_2 == i_1 or i_2 < i_be:
            return (tp1 + tp2, 'TP1 + TP2') if i_2 < n else (tp1 + last, 'TP1 + cierre')
        return (tp1, 'TP1 + BE') if i_be < n else (tp1 + last, 'TP1 + cierre')
    if i_2 < i_sl:
        return (tp1 + tp2, 'TP1 + TP2') if i_2 < n else (tp1 + last, 'TP1 + cierre')
    return (tp1 - sl, 'TP1 + stop') if i_sl < n else (tp1 + last, 'TP1 + cierre')


def evaluate(signals, pths, mask, sl, tp1, tp2, be):
    idx = np.nonzero(mask)[0]
    ticks = np.array([bracket(pths[i], sl, tp1, tp2, be)[0] for i in idx], float)
    usd = 4 * ticks * M.MES_TICK_USD - 8 * M.MES_COST   # 8 MES
    t = pd.DataFrame({'fecha': signals.fecha.values[idx], 'usd_8mes': usd})
    return t


def summary(t):
    out = {}
    for name, g in (('IS', t[t.fecha <= IS_END]), ('OOS', t[t.fecha > IS_END])):
        s = M.stats(g)
        out.update({f'{name}_n': s['n'], f'{name}_pf': round(s['pf'], 2), f'{name}_net': round(s['net']),
                    f'{name}_dd': round(s['mdd'])})
    return out


def grid(signals, pths):
    rows = []
    flags = list(itertools.product([True, False], repeat=4))
    for (fa, fc, fb, fv), sl, tp1, tp2, be in itertools.product(
            flags, (20, 30, 40, 50), (20, 30, 40, 60), (80, 120, 160, 240), (False, True)):
        if tp2 <= tp1:
            continue
        mask = np.ones(len(signals), bool)
        for f, on in (('A', fa), ('C', fc), ('BOS', fb), ('VWAP', fv)):
            if on:
                mask &= signals[f].values
        t = evaluate(signals, pths, mask, sl, tp1, tp2, be)
        rows.append({'A': fa, 'C': fc, 'BOS': fb, 'VWAP': fv, 'sl': sl, 'tp1': tp1, 'tp2': tp2, 'be': be,
                     **summary(t)})
    return pd.DataFrame(rows)


def main(folder):
    contracts = M.load_contracts(folder)
    chosen = M.choose_contracts(contracts)
    prep = M.prepare(contracts)
    base = M.Params()
    _, signals = M.run(prep, chosen, base)
    pths = paths(prep, signals, base)
    g = grid(signals, pths)
    g.to_csv('optimizacion_grid.csv', index=False)
    print('Modelo actual:')
    print(g[(g.A & g.C & g.BOS & g.VWAP) & (g.sl == 30) & (g.tp1 == 40) & (g.tp2 == 160) & ~g.be].to_string(index=False))
    ok = g[(g.IS_n >= 150)]
    print('\nMejores 15 por factor dentro de muestra (2018–2022), con ≥150 operaciones:')
    print(ok.sort_values('IS_pf', ascending=False).head(15).to_string(index=False))
    return g


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
