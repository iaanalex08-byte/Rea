"""Estrategia del video (Dani Charts): ruptura de la primera vela de 5 min (9:30–9:35 NY), TP corto y SL amplio.
En el Dow: TP 15 pts, SL 80 pts. En ES se prueba en % del precio (15/80 pts de ~45,000 = 0.033 % / 0.178 %) y en puntos fijos.
Entrada: orden stop 1 tick arriba del máximo (compra) o abajo del mínimo (venta); la primera que se toque. Una por día.
Salida: TP, SL o cierre 15:59 NY. Ambigüedad: stop primero; en la vela de entrada, 'conservador' solo revisa el stop
y 'optimista' cuenta el objetivo si la vela lo alcanza."""
import sys
import numpy as np, pandas as pd
import mas_dinero as M

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C)
T = 0.25

def dia(m1, day, tp_f, sl_f, modo):
    t0 = pd.Timestamp(day).tz_localize(M.NY) + pd.Timedelta(hours=9, minutes=30)
    r = m1[(m1.index >= t0) & (m1.index < t0 + pd.Timedelta(minutes=5))]
    if len(r) < 4: return None
    hi, lo = r.h.max() + T, r.l.min() - T
    b = m1[(m1.index >= t0 + pd.Timedelta(minutes=5)) & (m1.index < t0 + pd.Timedelta(hours=6, minutes=29))]
    H, L, Cc = b.h.values, b.l.values, b.c.values
    px = r.c.iloc[-1]
    tp, sl = tp_f(px), sl_f(px)
    for i in range(len(b)):
        up, dn = H[i] >= hi, L[i] <= lo
        if not (up or dn): continue
        if up and dn: return None                       # rompe ambos lados en la misma vela: se descarta
        d = 1 if up else -1; e = hi if up else lo
        stp, obj = e - d * sl, e + d * tp
        if (L[i] <= stp) if d > 0 else (H[i] >= stp): return {'fecha': day, 'R': -sl, 'tp': tp, 'sl': sl, 'sal': 'Stop'}
        if modo == 'opt' and ((H[i] >= obj) if d > 0 else (L[i] <= obj)): return {'fecha': day, 'R': tp, 'tp': tp, 'sl': sl, 'sal': 'TP'}
        for k in range(i + 1, len(b)):
            if (L[k] <= stp) if d > 0 else (H[k] >= stp): return {'fecha': day, 'R': -sl, 'tp': tp, 'sl': sl, 'sal': 'Stop'}
            if (H[k] >= obj) if d > 0 else (L[k] <= obj): return {'fecha': day, 'R': tp, 'tp': tp, 'sl': sl, 'sal': 'TP'}
        return {'fecha': day, 'R': d * (Cc[-1] - e), 'tp': tp, 'sl': sl, 'sal': 'Cierre'}
    return None

def correr(tp_f, sl_f, modo, desde=2018):
    rows = [dia(C[c], d, tp_f, sl_f, modo) for d, c in ch.items() if d.year >= desde]
    return pd.DataFrame([x for x in rows if x])

def lucid(u, target=3000, dd=2000):
    res = []
    for s in range(len(u)):
        bal = pk = 0.0
        for k in range(s, len(u)):
            bal += u[k]; pk = max(pk, bal)
            if bal >= target: res.append(1); break
            if bal <= min(pk - dd, 0): res.append(0); break
    return round(100 * np.mean(res), 1)

def informe(nombre, t):
    out = []
    for cn, cost in (('sin costos', 0.0), ('ES con costos', 0.25 + 4.5 / 50), ('MES con costos', 0.25 + 2.49 / 5)):
        pts = t.R.values - cost
        y = pd.to_datetime(t.fecha).dt.year.values
        pf = lambda p: round(p[p > 0].sum() / -p[p < 0].sum(), 2)
        eq = np.cumsum(pts * 50); dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
        be = 100 * (t.sl.mean() + cost) / (t.tp.mean() + t.sl.mean())
        out.append({'prueba': nombre, 'costos': cn, 'ops': len(pts), 'gana%': round(100 * (pts > 0).mean(), 1), 'equilibrio%': round(be, 1),
                    'PF': pf(pts), '2018-22': pf(pts[y <= 2022]), '2023-26': pf(pts[y >= 2023]), 'neto_1ES': round(pts.sum() * 50),
                    'caida_1ES': round(dd), 'lucid_1ES': lucid(pts * 50) if cn != 'sin costos' else None})
    return out

rows = []
pct_tp, pct_sl = 15 / 45000, 80 / 45000
for modo in ('cons', 'opt'):
    t = correr(lambda p: max(T, round(p * pct_tp / T) * T), lambda p: round(p * pct_sl / T) * T, modo)
    rows += informe(f'% del precio (como 15/80 en el Dow) · {modo}', t)
t = correr(lambda p: 2.0, lambda p: 10.75, 'cons'); rows += informe('Fijo 2 / 10.75 pts · cons', t)
t = correr(lambda p: 4.0, lambda p: 20.0, 'cons'); rows += informe('Fijo 4 / 20 pts · cons', t)
pd.set_option('display.width', 250)
r = pd.DataFrame(rows); print(r.to_string(index=False))
r.to_csv('orb_ratio_invertido.csv', index=False)
