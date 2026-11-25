"""Modelo B · Gap en otros horarios de entrada y otros timeframes (velas de la EMA y del BOS)."""
import sys
from dataclasses import replace
import pandas as pd
import mas_dinero as M

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C); prep = M.prepare(C)
base = M.MODELO_GAP

def res(name, p):
    t, _ = M.run(prep, ch, p)
    t = t[pd.to_datetime(t.fecha).dt.year >= 2018]
    t['usd_8mes'] = 4 * t.ticks * 1.25 - 8 * 2.49
    isd = pd.to_datetime(t.fecha).dt.year <= 2022
    a, i, o = M.stats(t), M.stats(t[isd]), M.stats(t[~isd])
    return {'prueba': name, 'ops': a['n'], 'gana%': round(100 * a['wr'], 1), 'PF': round(a['pf'], 2),
            '2018-22': round(i['pf'], 2), '2023-26': round(o['pf'], 2), 'neto_8MES': round(a['net']), 'caida': round(a['mdd'])}

rows = []
for h in ['10:00', '10:06', '10:12', '10:18', '10:30', '11:00', '11:30', '12:00', '13:00', '14:00']:
    rows.append(res(f'Hora {h} · velas 3 min', replace(base, entry=h)))
print(pd.DataFrame(rows).to_string(index=False)); print()
rows = [res('Velas 3 min · EMA 20 · BOS 60 min (modelo)', base),
        res('Velas 1 min · EMA 20 · BOS 60 min', replace(base, bar_min=1, bos_bars=60)),
        res('Velas 1 min · EMA 60 (mismo lapso) · BOS 60 min', replace(base, bar_min=1, ema_len=60, bos_bars=60)),
        res('Velas 5 min · 10:10 · EMA 20 · BOS 60 min', replace(base, bar_min=5, entry='10:10', bos_bars=12)),
        res('Velas 5 min · 10:15 · EMA 20 · BOS 60 min', replace(base, bar_min=5, entry='10:15', bos_bars=12)),
        res('Velas 5 min · 10:10 · EMA 12 (mismo lapso)', replace(base, bar_min=5, entry='10:10', ema_len=12, bos_bars=12))]
print(pd.DataFrame(rows).to_string(index=False))
