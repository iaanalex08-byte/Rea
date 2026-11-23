"""Genera los JSON del dashboard «Modelo B · Gap» a partir de los datos de NinjaTrader.

Uso:  python3 backtest/construir_dashboard.py backtest/datos
Escribe backtest/dashboard/{operaciones,embudo,lucid,versiones}.json
"""
import json
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

import mas_dinero as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard')
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
SALIDAS = {'Stop': 'Stop', 'TP1 + TP2': 'TP1 + TP2', 'TP1 + BE': 'TP1 + break-even',
           'TP1 + cierre 15:59': 'TP1 + cierre 15:59', 'Cierre 15:59': 'Cierre 15:59', 'TP1 + stop': 'TP1 + stop'}


def usd_mes(ticks, n):
    return (n / 2) * ticks * M.MES_TICK_USD - n * M.MES_COST


def lucid(usd, target=3000, dd=2000):
    res = []
    for s in range(len(usd)):
        bal = peak = 0.0
        for k in range(s, len(usd)):
            bal += usd[k]
            peak = max(peak, bal)
            if bal >= target:
                res.append(('pasa', k - s + 1))
                break
            if bal <= min(peak - dd, 0):
                res.append(('pierde', k - s + 1))
                break
    r = pd.DataFrame(res, columns=['r', 'n'])
    ok = r[r.r == 'pasa']
    return {'cuentas': len(r), 'pasan': int(len(ok)), 'pasa_pct': round(100 * len(ok) / len(r), 1),
            'ops_pasar': int(ok.n.median()), 'ops_perder': int(r[r.r == 'pierde'].n.median()) if (r.r == 'pierde').any() else None}


def write(name, rows, meta):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump({'rows': rows, 'meta': meta}, f, ensure_ascii=False, indent=0)


def main(folder):
    os.makedirs(OUT, exist_ok=True)
    C = M.load_contracts(folder)
    ch = M.choose_contracts(C)
    prep = M.prepare(C)
    p = M.MODELO_GAP
    trades, sig = M.run(prep, ch, p)
    trades = trades[pd.to_datetime(trades.fecha).dt.year >= 2018].reset_index(drop=True)
    meta = [{'label': 'Origen', 'value': 'ES 1 min de NinjaTrader (36 contratos, 2018 – 20 nov 2026), contrato con más volumen cada día'},
            {'label': 'Script', 'value': 'backtest/construir_dashboard.py + backtest/mas_dinero.py (MODELO_GAP)'},
            {'label': 'Costos', 'value': 'MES: 2.49 USD ida y vuelta por contrato. ES: 1 tick de deslizamiento + 4.50 USD por contrato.'}]

    # operaciones
    rows, s8, s6 = [], 0.0, 0.0
    for t in trades.to_dict('records'):
        f = pd.Timestamp(t['fecha'])
        u8, u6 = usd_mes(t['ticks'], 8), usd_mes(t['ticks'], 6)
        s8 += u8
        s6 += u6
        rows.append({'fecha': f.strftime('%Y-%m-%d'), 'anio': str(f.year), 'mes': f.strftime('%Y-%m'), 'dia': DIAS[f.dayofweek],
                     'direccion': 'Compra' if t['dir'] > 0 else 'Venta', 'salida': SALIDAS.get(t['salida'], t['salida']),
                     'ticks': int(t['ticks']), 'gap_pts': round(float(t['gap']), 2), 'dist_ema_pts': round(abs(t['entrada'] - t['ema']), 2),
                     'usd_8mes': round(u8, 2), 'usd_6mes': round(u6, 2), 'usd_2es': round(t['usd_2es'], 2),
                     'saldo_8mes': round(s8, 2), 'saldo_6mes': round(s6, 2), 'gana': bool(u8 > 0)})
    write('operaciones.json', rows, meta)

    # embudo: días que quedan tras cada filtro, con el mismo bracket
    sg = sig[pd.to_datetime(sig.fecha).dt.year >= 2018]
    pasos = [('Días hábiles con datos', []), ('A: fuera del valor de ayer', ['A']), ('C: perfil de hoy no ya a favor', ['A', 'C']),
             ('Sin BOS en contra', ['A', 'C', 'BOS']), ('VWAP a favor', ['A', 'C', 'BOS', 'VWAP']),
             ('Gap no en contra (se opera)', ['A', 'C', 'BOS', 'VWAP', 'GAP'])]
    emb = []
    for nombre, fl in pasos:
        q = replace(p, filt_a='A' in fl, filt_c='C' in fl, filt_bos='BOS' in fl, filt_vwap='VWAP' in fl, filt_gap='GAP' in fl)
        t, _ = M.run(prep, ch, q, signals=sg)
        t['usd_8mes'] = usd_mes(t.ticks, 8)
        st = M.stats(t)
        emb.append({'paso': nombre, 'dias': int(st['n']), 'ganadoras': round(100 * st['wr'], 1), 'pf': round(st['pf'], 2), 'neto': round(st['net'])})
    write('embudo.json', emb, meta)

    # Lucid 50K por tamaño
    luc = []
    for n in (2, 4, 6, 8, 10):
        u = usd_mes(trades.ticks.values.astype(float), n)
        r = lucid(u)
        eq = u.cumsum()
        luc.append({'mes': n, 'perdida_stop': round(n * p.sl * M.MES_TICK_USD + n * M.MES_COST), 'neto': round(u.sum()),
                    'caida_max': round((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()), **r})
    write('lucid.json', luc, meta + [{'label': 'Reglas', 'value': 'Meta +3,000; caída máxima 2,000 al cierre, sube con el máximo y se congela en el saldo inicial. Sin regla de consistencia ni límite diario.'}])

    # versiones comparadas, mismo periodo 2018–2026, 8 MES
    vers = [('Más dinero (30/40/160, 4 filtros)', M.Params()),
            ('Modelo A + C (9:12 CDMX, 35/30/120 BE)', replace(M.Params(), entry='09:12', entry_tz='America/Mexico_City',
                                                                filt_bos=False, filt_vwap=False, sl=35, tp1=30, tp2=120, breakeven=True)),
            ('Mezcla (10:12 NY, 4 filtros, 35/30/120 BE)', replace(M.Params(), sl=35, tp1=30, tp2=120, breakeven=True)),
            ('Modelo B · Gap (este)', p)]
    vr = []
    for nombre, q in vers:
        t, _ = M.run(prep, ch, q)
        t = t[pd.to_datetime(t.fecha).dt.year >= 2018]
        t['usd_8mes'] = usd_mes(t.ticks, 8)
        a = M.stats(t)
        isd = pd.to_datetime(t.fecha) <= '2022-12-31'
        vr.append({'version': nombre, 'ops': int(a['n']), 'ganadoras': round(100 * a['wr'], 1), 'pf': round(a['pf'], 2),
                   'pf_2018_2022': round(M.stats(t[isd])['pf'], 2), 'pf_2023_2026': round(M.stats(t[~isd])['pf'], 2),
                   'neto': round(a['net']), 'caida_max': round(a['mdd']), 'racha': int(a['racha'])})
    write('versiones.json', vr, meta)
    print(pd.DataFrame(vr).to_string(index=False))
    print(pd.DataFrame(emb).to_string(index=False))
    print(pd.DataFrame(luc).to_string(index=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
