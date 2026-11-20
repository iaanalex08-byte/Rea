"""Perfil de mercado (TPO) para el Modelo B.

Las velas SPXUSD de HistData no traen volumen, así que el perfil se arma por tiempo:
cada vela de 1 minuto reparte un punto entre todos los niveles de precio que tocó (TPO).
Es la misma idea que el perfil de volumen y marca POC, VAH y VAL muy parecidos.

Sesión regular (RTH): 9:30–16:00 Nueva York. Niveles en cajas de 1 punto.
"""
import numpy as np
import pandas as pd

BIN = 1.0          # tamaño de cada nivel, en puntos
VA_PCT = 0.70      # área de valor


def _hist(lo, hi):
    """TPO de un conjunto de velas: devuelve (precios base de cada caja, cuentas)."""
    b0 = np.floor(lo.min() / BIN) * BIN
    nb = int(np.floor(hi.max() / BIN) - b0 / BIN) + 1
    cnt = np.zeros(nb)
    a = np.floor(lo / BIN).astype(int) - int(b0 / BIN)
    z = np.floor(hi / BIN).astype(int) - int(b0 / BIN)
    for i, j in zip(a, z):
        cnt[i:j + 1] += 1.0 / (j - i + 1)
    return b0 + np.arange(nb) * BIN, cnt


def niveles(lo, hi):
    """POC, VAH, VAL y la forma del perfil (posición del POC dentro del rango, 0 = abajo, 1 = arriba)."""
    px, c = _hist(np.asarray(lo), np.asarray(hi))
    p = int(c.argmax())
    up = dn = p
    acc, tot = c[p], c.sum()
    while acc < tot * VA_PCT:
        a = c[up + 1] if up + 1 < len(c) else -1
        b = c[dn - 1] if dn - 1 >= 0 else -1
        if a >= b:
            up += 1
            acc += a
        else:
            dn -= 1
            acc += b
    poc = px[p] + BIN / 2
    rng_lo, rng_hi = px[0], px[-1] + BIN
    pos = (poc - rng_lo) / max(rng_hi - rng_lo, BIN)
    return dict(poc=poc, vah=px[up] + BIN, val=px[dn], lo=rng_lo, hi=rng_hi, pos=pos, px=px, cnt=c)


def rth(df1):
    """Velas de la sesión regular con la fecha de Nueva York."""
    ny = df1.index.tz_convert('America/New_York')
    m = ny.hour * 60 + ny.minute
    x = df1[(m >= 570) & (m < 960)].copy()
    x['nyd'] = ny[(m >= 570) & (m < 960)].date
    x['nym'] = m[(m >= 570) & (m < 960)]
    return x


def perfiles_diarios(df1):
    """POC/VAH/VAL de cada sesión regular completa, indexado por fecha de Nueva York."""
    x = rth(df1)
    rows = {}
    for d, g in x.groupby('nyd'):
        if len(g) < 200:          # sesiones recortadas o incompletas
            continue
        n = niveles(g.l.values, g.h.values)
        rows[d] = dict(poc=n['poc'], vah=n['vah'], val=n['val'], lo=n['lo'], hi=n['hi'], pos=n['pos'],
                       close=g.c.values[-1], hvn=_hvns(n))
    return pd.DataFrame.from_dict(rows, orient='index').sort_index()


def _hvns(n, k=3):
    """Nodos de alto volumen: máximos locales del perfil con al menos el 60 % del POC."""
    c = n['cnt']
    s = np.convolve(c, np.ones(3) / 3, mode='same')
    out = [n['px'][i] + BIN / 2 for i in range(1, len(s) - 1)
           if s[i] >= s[i - 1] and s[i] >= s[i + 1] and s[i] >= 0.6 * s.max()]
    return out


def rasgos(T, df1, hm=(9, 12)):
    """Agrega a cada operación del Modelo B los rasgos del perfil al momento de entrar."""
    P = perfiles_diarios(df1)
    x = rth(df1)
    by_day = {d: g for d, g in x.groupby('nyd')}
    fechas = list(P.index)
    out = []
    for _, t in T.iterrows():
        d = pd.Timestamp(t.date).date()
        g = by_day.get(d)
        prev = [f for f in fechas if f < d]
        if g is None or len(prev) < 2:
            out.append({})
            continue
        y, y2 = P.loc[prev[-1]], P.loc[prev[-2]]
        e, s = t.entry, t.dir
        # 1. ubicación contra el área de valor de ayer, vista en la dirección de la operación
        if (s == 1 and e > y.vah) or (s == -1 and e < y.val):
            loc = 'a favor (fuera del valor)'
        elif (s == 1 and e < y.val) or (s == -1 and e > y.vah):
            loc = 'en contra (fuera del valor)'
        else:
            loc = 'dentro del valor'
        # 2. espacio libre: nivel de ayer más cercano en la dirección de la operación
        lv = [y.poc, y.vah, y.val] + list(y.hvn)
        ahead = [(v - e) * s for v in lv if (v - e) * s > 0.5]
        room = min(ahead) if ahead else np.inf
        # 3. perfil en desarrollo desde las 9:30 NY hasta la entrada
        t0 = pd.Timestamp(f'{t.date} {hm[0]:02d}:{hm[1]:02d}', tz='America/Mexico_City').tz_convert('America/New_York')
        hh = t0.hour * 60 + t0.minute
        dev = g[g.nym < hh]
        if len(dev) >= 20:
            n = niveles(dev.l.values, dev.h.values)
            pos = n['pos'] if s == 1 else 1 - n['pos']
            forma = 'a favor (P/b)' if pos > 0.62 else 'en contra' if pos < 0.38 else 'D (balance)'
            dpoc_dist = (e - n['poc']) * s
            ib = g[g.nym < 630]
            ib_ext = None
            if hh >= 630 and len(ib):
                ib_ext = 'extensión a favor' if (s == 1 and e > ib.h.max()) or (s == -1 and e < ib.l.min()) else \
                         'extensión en contra' if (s == 1 and e < ib.l.min()) or (s == -1 and e > ib.h.max()) else 'dentro del IB'
            rango_dev = n['hi'] - n['lo']
        else:
            forma, dpoc_dist, ib_ext, rango_dev = None, np.nan, None, np.nan
        # 4. migración del valor de varios días
        mig = (y.poc - y2.poc) * s
        migr = 'a favor' if mig > 2 else 'en contra' if mig < -2 else 'plana'
        # 5. apertura de hoy contra el valor de ayer
        o = g.o.values[0]
        ap = 'arriba del VAH' if o > y.vah else 'abajo del VAL' if o < y.val else 'dentro del valor'
        ap_dir = ('a favor' if (s == 1 and o > y.vah) or (s == -1 and o < y.val) else
                  'en contra' if (s == 1 and o < y.val) or (s == -1 and o > y.vah) else 'dentro')
        out.append(dict(ny_min=hh, loc=loc, room=room, forma=forma, dpoc=dpoc_dist, ib=ib_ext, mig=migr, apertura=ap,
                        apertura_dir=ap_dir, rango_dev=rango_dev, y_rango=y.hi - y.lo, y_va=y.vah - y.val,
                        dist_vah=(e - y.vah), dist_val=(e - y.val), dist_poc=(e - y.poc) * s))
    return pd.concat([T.reset_index(drop=True), pd.DataFrame(out)], axis=1)
