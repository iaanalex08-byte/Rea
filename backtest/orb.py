"""ORB con retroceso en ES: rango de apertura, ruptura, retroceso al nivel roto y entrada a favor 1:R.

Reglas (velas de 1 minuto del contrato con más volumen del día, hora de Nueva York):
  1. Rango: máximo y mínimo de las velas que empiezan entre `inicio` y `inicio + rango_min` (9:30–9:35 NY por defecto).
  2. Ruptura: la primera vela que CIERRA fuera del rango marca la dirección (arriba = compra, abajo = venta).
  3. Retroceso: después de la ruptura, el precio vuelve a tocar el nivel roto (en compra, un mínimo <= máximo del rango).
  4. Entrada: cuando, tras el retroceso, el precio vuelve a cruzar el nivel roto a favor (orden stop en el nivel).
     Stop: el extremo del retroceso (en compra, el mínimo más bajo desde la ruptura). Objetivo: R veces el riesgo.
  5. Se cancela si el precio toca el otro lado del rango antes de entrar, si no hay entrada antes de `limite`,
     o si el riesgo es menor a `min_ticks`. Una operación por día. Lo que siga abierto se cierra a las 15:59 NY.
  Ambigüedad: si en una misma vela se tocan stop y objetivo cuenta el stop; en la vela de entrada solo se revisa el stop.
"""
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

import mas_dinero as M

TICK = 0.25


@dataclass(frozen=True)
class ORB:
    inicio: str = '09:30'
    tz: str = M.NY                # 'America/Mexico_City' para usar la hora fija de CDMX
    rango_min: int = 5
    rr: float = 2.0
    limite: str = '12:00'         # hora NY máxima para entrar
    cierre: str = '15:59'
    min_ticks: int = 4


def _t(day, hhmm, tz):
    h, m = map(int, hhmm.split(':'))
    return (pd.Timestamp(day).tz_localize(tz) + pd.Timedelta(hours=h, minutes=m)).tz_convert(M.NY)


def dia(m1, day, p: ORB):
    t0 = _t(day, p.inicio, p.tz)
    t1 = t0 + pd.Timedelta(minutes=p.rango_min)
    tlim, tend = _t(day, p.limite, M.NY), _t(day, p.cierre, M.NY)
    if tlim <= t1:
        tlim = t1 + pd.Timedelta(hours=2)
    rng = m1[(m1.index >= t0) & (m1.index < t1)]
    if len(rng) < p.rango_min - 1:
        return None
    hi, lo = rng.h.max(), rng.l.min()
    b = m1[(m1.index >= t1) & (m1.index < tend)]
    if b.empty:
        return None
    H, L, Cc, T = b.h.values, b.l.values, b.c.values, b.index
    n = len(b)
    # 2. ruptura por cierre
    i, d = 0, 0
    while i < n and T[i] < tlim:
        if Cc[i] > hi:
            d = 1
            break
        if Cc[i] < lo:
            d = -1
            break
        i += 1
    if d == 0:
        return {'fecha': day, 'estado': 'Sin ruptura', 'hi': hi, 'lo': lo}
    nivel = hi if d > 0 else lo
    opuesto = lo if d > 0 else hi
    ext = L[i] if d > 0 else H[i]          # extremo del retroceso (se actualiza)
    retest = False
    j = i + 1
    entrada = None
    while j < n and T[j] < tlim:
        if d > 0:
            if L[j] <= opuesto:
                return {'fecha': day, 'estado': 'Tocó el otro lado', 'dir': d, 'hi': hi, 'lo': lo}
            if retest and H[j] > nivel:     # tras el retroceso, vuelve a cruzar el nivel hacia arriba
                entrada = j
                break
            ext = min(ext, L[j])
            if L[j] <= nivel:
                retest = True
        else:
            if H[j] >= opuesto:
                return {'fecha': day, 'estado': 'Tocó el otro lado', 'dir': d, 'hi': hi, 'lo': lo}
            if retest and L[j] < nivel:
                entrada = j
                break
            ext = max(ext, H[j])
            if H[j] >= nivel:
                retest = True
        j += 1
    if entrada is None:
        return {'fecha': day, 'estado': 'Sin retroceso / entrada', 'dir': d, 'hi': hi, 'lo': lo}
    e, sl = nivel, ext
    riesgo = d * (e - sl)
    if riesgo < p.min_ticks * TICK:
        return {'fecha': day, 'estado': 'Riesgo muy chico', 'dir': d, 'hi': hi, 'lo': lo}
    tp = e + d * p.rr * riesgo
    k = entrada
    salida, res, hora_sal = None, None, None
    if (L[k] <= sl) if d > 0 else (H[k] >= sl):      # vela de entrada: solo stop (conservador)
        salida, res, hora_sal = 'Stop', -1.0, T[k]
    k += 1
    while salida is None and k < n:
        adv = (L[k] <= sl) if d > 0 else (H[k] >= sl)
        fav = (H[k] >= tp) if d > 0 else (L[k] <= tp)
        if adv:
            salida, res, hora_sal = 'Stop', -1.0, T[k]
        elif fav:
            salida, res, hora_sal = 'Objetivo', p.rr, T[k]
        k += 1
    if salida is None:
        salida, res, hora_sal = 'Cierre 15:59', d * (Cc[-1] - e) / riesgo, T[-1]
    return {'fecha': day, 'estado': 'Operada', 'dir': d, 'hi': hi, 'lo': lo, 'entrada': e, 'stop': sl, 'objetivo': tp,
            'riesgo_pts': riesgo, 'hora_entrada': T[entrada], 'hora_salida': hora_sal, 'salida': salida, 'R': res,
            'pts': res * riesgo}


def correr(prep, chosen, p: ORB, desde=2021):
    rows = []
    for day, c in chosen.items():
        if day.year < desde:
            continue
        r = dia(prep[c]['m1'], day, p)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


def resumen(t):
    o = t[t.estado == 'Operada']
    R = o.R.values
    g, l = R[R > 0].sum(), -R[R < 0].sum()
    eq = np.cumsum(R)
    dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    st = mx = 0
    for x in R:
        st = st + 1 if x < 0 else 0
        mx = max(mx, st)
    return {'dias': len(t), 'ops': len(o), 'win%': round(100 * (R > 0).mean(), 1), 'PF': round(g / l, 2) if l else np.inf,
            'espR': round(R.mean(), 3), 'netoR': round(R.sum(), 1), 'caidaR': round(dd, 1), 'racha_perd': mx}


if __name__ == '__main__':
    C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos')
    ch = M.choose_contracts(C)
    prep = {k: {'m1': df} for k, df in C.items()}
    t = correr(prep, ch, ORB())
    print(t.estado.value_counts().to_dict())
    print('BASE', resumen(t))
    o = t[t.estado == 'Operada']
    print(o.groupby(pd.to_datetime(o.fecha).dt.year).R.agg(['count', lambda x: round(100 * (x > 0).mean(), 1), 'sum']).round(2))
    print('riesgo pts: mediana', o.riesgo_pts.median(), 'p10', o.riesgo_pts.quantile(.1), 'p90', o.riesgo_pts.quantile(.9))
    print(o.salida.value_counts().to_dict())
