"""Exporta las operaciones del Gap con bracket invertido (tres variantes) para el dashboard de winrate y rachas."""
import sys
import numpy as np, pandas as pd
import mas_dinero as M, optimizar as O
from winrate80 import resultado, ES_COST_T

VARIANTES = [('92.7', 8, 104), ('88.2', 12, 80), ('81.5', 20, 80)]

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos')
P = M.prepare(C); p = M.MODELO_GAP
_, sig = M.run(P, M.choose_contracts(C), p)
sig = sig[(sig.A & sig.C & sig.BOS & sig.VWAP & sig.GAP).values].reset_index(drop=True)
pth = O.paths(P, sig, p)
rows = []
for nombre, tp, sl in VARIANTES:
    for s, x in zip(sig.to_dict('records'), pth):
        t = resultado(x, tp, sl); neto = t - ES_COST_T
        rows.append({'variante': nombre, 'fecha': str(s['fecha']), 'dir': 'Compra' if s['dir'] > 0 else 'Venta',
                     'salida': 'TP' if t == tp else ('Stop' if t == -sl else 'Cierre 15:59'),
                     'tp_ticks': tp, 'sl_ticks': sl, 'ticks_netos': round(neto, 2), 'usd_1es': round(neto * 12.5, 2),
                     'gana': int(neto > 0)})
pd.DataFrame(rows).to_csv('dashboard_w80/operaciones.csv', index=False)
print(len(rows))
