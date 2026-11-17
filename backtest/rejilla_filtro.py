"""Rejilla SL × TP1 × TP2 del Modelo B con los filtros de perfil A + C.

Uso:  python3 backtest/rejilla_filtro.py datos/

Misma lógica que engine.run (velas de 1 min, stop primero si stop y objetivo caen en la misma vela,
BE del segundo contrato tras TP1, cierre 15:59 NY, 34 USD de costo), pero evalúa cada bracket
con numpy sobre los minutos de cada día para poder probar cientos de combinaciones.
Elige con 2025 y comprueba con 2026.
"""
import sys
import numpy as np
import pandas as pd
from engine import load, run, resample, ema3, TICK, TV, COST
from perfil import rasgos


def dias(df1, ema_len=20, ema_tf=3, hm=(9, 12)):
    """Para cada día: dirección, entrada y los minutos desde la entrada hasta el cierre, en ticks a favor."""
    ex = resample(df1, 1)
    ema = ema3(df1, ema_len, ema_tf)
    mx = ex.index.tz_convert('America/Mexico_City')
    ny = ex.index.tz_convert('America/New_York')
    O, H, L, C = ex.o.values, ex.h.values, ex.l.values, ex.c.values
    mxd = np.array(mx.date)
    idx = ex.index
    gap = np.r_[(idx[1:] - idx[:-1]) > pd.Timedelta(minutes=30), True]
    closing = ((ny.hour == 15) & (ny.minute + 1 > 59)) | gap
    out = []
    for s in np.where((mx.hour == hm[0]) & (mx.minute == hm[1]))[0]:
        if idx[s].weekday() >= 5:
            continue
        ent = O[s]
        d = 1 if ent > ema.asof(idx[s]) else -1
        e = s
        while e < len(C) and mxd[e] == mxd[s] and not closing[e]:
            e += 1
        if e >= len(C) or mxd[e] != mxd[s]:
            continue
        sl_ = slice(s, e + 1)
        up = ((H[sl_] - ent) if d == 1 else (ent - L[sl_])) / TICK     # mejor excursión a favor
        dn = ((L[sl_] - ent) if d == 1 else (ent - H[sl_])) / TICK     # peor excursión (negativa = en contra)
        op = ((O[sl_] - ent) * d) / TICK
        cl = (C[e] - ent) * d / TICK
        out.append(dict(date=str(mxd[s]), dir=d, entry=ent, ema=float(ema.asof(idx[s])), up=up, dn=dn, op=op, cl=cl))
    return out


def _first(mask):
    i = int(np.argmax(mask))
    return i if mask[i] else None


def bracket(day, sl, tp1, tp2, be=True):
    """Resultado en USD de un día con el bracket dado (en ticks)."""
    up, dn, op, cl = day['up'], day['dn'], day['op'], day['cl']
    i_sl = _first(dn <= -sl)
    i_t1 = _first(up >= tp1)
    if i_sl is not None and (i_t1 is None or i_sl <= i_t1):
        fill = -sl if i_sl == 0 else min(op[i_sl], -sl)
        return 2 * fill * TV - COST
    if i_t1 is None:
        return 2 * cl * TV - COST
    r1 = tp1
    if up[i_t1] >= tp2:
        return (r1 + tp2) * TV - COST
    rest_dn, rest_up = dn[i_t1 + 1:], up[i_t1 + 1:]
    lvl = 0 if be else -sl
    i_be = _first(rest_dn <= lvl) if len(rest_dn) else None
    i_t2 = _first(rest_up >= tp2) if len(rest_up) else None
    if i_be is not None and (i_t2 is None or i_be <= i_t2):
        r2 = min(op[i_t1 + 1 + i_be], float(lvl))
    elif i_t2 is not None:
        r2 = tp2
    else:
        r2 = cl
    return (r1 + r2) * TV - COST


def metr(u):
    u = np.asarray(u)
    gp, gl = u[u > 0].sum(), -u[u <= 0].sum()
    eq = np.cumsum(u)
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min() if len(u) else 0
    return dict(n=len(u), pf=gp / gl if gl else np.inf, net=u.sum(), dd=dd, wr=(u > 0).mean() if len(u) else 0)


if __name__ == '__main__':
    df = load(sys.argv[1] if len(sys.argv) > 1 else 'datos')
    D = dias(df)
    # comprobación: con 45/30/60 debe dar lo mismo que engine.run
    base = run(df)
    chk = pd.Series({d['date']: bracket(d, 45, 30, 60) for d in D})
    diff = (base.set_index('date').usd - chk.reindex(base.date).values).abs().max()
    print(f'comprobación contra engine.run: {len(base)} ops, diferencia máxima {diff:.2f} USD')
    R = rasgos(base, df)
    ok = set(R[(R['loc'].notna()) & (R['loc'] != 'dentro del valor') & (R.forma != 'a favor (P/b)')].date)
    Dk = [d for d in D if d['date'] in ok]
    filas = []
    for sl in [20, 25, 30, 35, 40, 45, 50, 60, 70, 80]:
        for tp1 in [12, 16, 20, 25, 30, 40, 50]:
            for tp2 in [30, 40, 50, 60, 80, 100, 120, 160]:
                if tp2 <= tp1:
                    continue
                res = [(d['date'], bracket(d, sl, tp1, tp2)) for d in Dk]
                u = np.array([r for _, r in res])
                y = np.array([dt[:4] for dt, _ in res])
                a, b, t = metr(u[y == '2025']), metr(u[y == '2026']), metr(u)
                filas.append(dict(sl=sl, tp1=tp1, tp2=tp2, n=t['n'], pf=t['pf'], net=t['net'], dd=t['dd'], wr=t['wr'],
                                  pf25=a['pf'], net25=a['net'], pf26=b['pf'], net26=b['net']))
    G = pd.DataFrame(filas)
    G.to_csv('rejilla_filtro.csv', index=False)
    pd.set_option('display.width', 200)
    print('\nActual 45/30/60:')
    print(G[(G.sl == 45) & (G.tp1 == 30) & (G.tp2 == 60)].round(2).to_string(index=False))
    print('\nMejores por PF 2025 (elegidos solo con 2025), con su resultado en 2026:')
    print(G.sort_values('pf25', ascending=False).head(15).round(2).to_string(index=False))
