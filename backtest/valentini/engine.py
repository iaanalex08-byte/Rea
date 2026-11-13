"""Backtest de los dos modelos de Fabio Valentini en el ES (velas con volumen de Yahoo, ES=F).

Sesión RTH: 9:30–16:00 Nueva York. Entradas entre 9:30 y 15:30, cierre forzado 15:59.
Perfil de volumen: el volumen de cada vela se reparte por igual entre los ticks de su rango.

Balance (dos versiones):
  'ib'   balance inicial: rango de la primera hora (9:30–10:30), como el recuadro del ejemplo.
  'prev' área de valor (70 %) del día anterior.

Big trade: sin datos de ticks no hay operaciones individuales, así que se usa una vela de agresión:
  volumen >= mult × media de las 20 velas anteriores, cuerpo a favor y cierre en el tercio del extremo.

Modelo 1 · Ruptura de balance (tendencia)
  Imbalance: una vela cierra fuera del balance por >= brk ticks. Se sigue el extremo de la iniciativa.
  Retroceso: el precio vuelve a la zona de bajo volumen entre el borde del balance y el 40 % de la
  iniciativa, sin cerrar dentro del balance. Gatillo: big trade a favor en esa zona (o sin gatillo).
  Stop: detrás de la iniciativa = otro lado del borde, máx(borde, extremo del retroceso) + buf ticks.
  Objetivo: 'mm' extensión igual a la altura del balance desde el borde; 'r2' 2R; 'poc' POC del día anterior
  si está a >= 1R a favor (si no, 2R).

Modelo 2 · Reversión a la media (giros)
  Contexto: el día abre dentro del balance de referencia (área de valor o rango del día anterior).
  Falsa salida: el precio sale del extremo >= brk ticks y una vela cierra de vuelta dentro.
  Gatillo: big trade opuesto en esa vela o en las 2 siguientes (atrapados).
  Stop: extremo de la falsa salida + buf ticks. Objetivo: POC o el extremo opuesto.
"""
import numpy as np, pandas as pd

TICK, TV = 0.25, 12.5
COST = 1 * TV + 4.5  # 1 tick de deslizamiento + 4.50 USD de comisión, por contrato y vuelta completa


def sessions(df):
    df = df.assign(rv=df.v)
    if df.v.sum() == 0:  # sin volumen: perfil por tiempo en el precio (TPO)
        df = df.assign(v=1.0)
    ny = df.index.tz_convert('America/New_York')
    mins = ny.hour * 60 + ny.minute
    df = df.assign(day=ny.date, mins=mins)
    return df[(df.mins >= 570) & (df.mins < 960)]


def profile(bars):
    lo = np.floor(bars.l.min() / TICK).astype(int); hi = np.ceil(bars.h.max() / TICK).astype(int)
    vap = np.zeros(hi - lo + 1)
    for l, h, v in zip(bars.l.values, bars.h.values, bars.v.values):
        a, b = int(round(l / TICK)) - lo, int(round(h / TICK)) - lo
        vap[a:b + 1] += v / (b - a + 1)
    poc = int(vap.argmax()); tot = vap.sum(); acc = vap[poc]; i = j = poc
    while acc < 0.7 * tot:
        up = vap[j + 1] if j + 1 < len(vap) else -1
        dn = vap[i - 1] if i > 0 else -1
        if up >= dn: j += 1; acc += up
        else: i -= 1; acc += dn
    p = lambda k: (k + lo) * TICK
    return dict(poc=p(poc), vah=p(j), val=p(i), hi=bars.h.max(), lo=bars.l.min())


def big_trade(d, mult):
    """Con volumen: pico de volumen. Sin volumen (SPX de HistData): vela de expansión de rango."""
    v = d.rv.values if d.rv.sum() > 0 else (d.h - d.l).values; o, h, l, c = d.o.values, d.h.values, d.l.values, d.c.values
    avg = pd.Series(v).rolling(20, min_periods=10).mean().shift(1).values
    rng = np.where(h > l, h - l, TICK)
    spike = v >= mult * np.nan_to_num(avg, nan=np.inf)
    buy = spike & (c > o) & ((c - l) / rng >= 2 / 3)
    sell = spike & (c < o) & ((h - c) / rng >= 2 / 3)
    return buy, sell


def simulate(H, L, C, mins, k, d, ent, stop, tgt):
    """Desde la vela k+1. Conservador: si stop y objetivo caen en la misma vela, cuenta el stop."""
    for j in range(k + 1, len(C)):
        if (L[j] <= stop) if d == 1 else (H[j] >= stop):
            return (stop - ent) * d / TICK, 'stop', j
        if (H[j] >= tgt) if d == 1 else (L[j] <= tgt):
            return (tgt - ent) * d / TICK, 'objetivo', j
        if mins[j] >= 959:
            return (C[j] - ent) * d / TICK, 'cierre', j
    return (C[-1] - ent) * d / TICK, 'cierre', len(C) - 1


def run(df, tf, model, balance='ib', target='mm', trigger=True, mult=2.0, brk=2, buf=2, rng_ref='va'):
    df = sessions(df)
    days = sorted(df.day.unique())
    ib_n = 60 // tf
    out = []
    for n, day in enumerate(days[1:], 1):
        d = df[df.day == day]
        pv = df[df.day == days[n - 1]]
        if len(d) < 300 // tf or len(pv) < 300 // tf:
            continue
        prev = profile(pv)
        O, H, L, C, mins = d.o.values, d.h.values, d.l.values, d.c.values, d.mins.values
        bb, bs = big_trade(d, mult) if trigger else (np.ones(len(d), bool), np.ones(len(d), bool))
        t = d.index
        if model == 1:
            if balance == 'ib':
                top, bot, s0 = H[:ib_n].max(), L[:ib_n].min(), ib_n
            else:
                top, bot, s0 = prev['vah'], prev['val'], 1
            height = top - bot
            for side in (1, -1):
                edge = top if side == 1 else bot
                state, ext, k0 = 0, None, None
                for k in range(s0, len(C)):
                    if mins[k] > 930: break
                    if state == 0:
                        if (C[k] - edge) * side >= brk * TICK:
                            state, ext, k0 = 1, (H[k] if side == 1 else L[k]), k
                        continue
                    ext = max(ext, H[k]) if side == 1 else min(ext, L[k])
                    if (C[k] - edge) * side < 0:  # volvió a cerrar dentro: se cancela, espera nueva ruptura
                        state = 0; continue
                    zone = edge + side * 0.4 * abs(ext - edge)
                    touched = (L[k] <= zone) if side == 1 else (H[k] >= zone)
                    trig = bb[k] if side == 1 else bs[k]
                    if k > k0 and touched and trig:
                        ent = C[k]
                        pull = L[k0:k + 1].min() if side == 1 else H[k0:k + 1].max()
                        stop = (min(edge, pull) - buf * TICK) if side == 1 else (max(edge, pull) + buf * TICK)
                        risk = abs(ent - stop)
                        if risk < 4 * TICK: continue
                        if target == 'mm': tgt = edge + side * max(height, risk)
                        elif target == 'r2': tgt = ent + side * 2 * risk
                        else:
                            tgt = prev['poc'] if (prev['poc'] - ent) * side >= risk else ent + side * 2 * risk
                        if (tgt - ent) * side <= 0: continue
                        r, why, j = simulate(H, L, C, mins, k, side, ent, stop, tgt)
                        out.append(dict(date=str(day), model=1, side=side, time=t[k], ent=ent, stop=stop, tgt=tgt,
                                        risk_t=risk / TICK, ticks=r, why=why, exit=t[j]))
                        break
        else:
            top, bot = (prev['vah'], prev['val']) if rng_ref == 'va' else (prev['hi'], prev['lo'])
            if not (bot < O[0] < top):
                continue
            taken = 0
            for side in (-1, 1):  # -1: falsa salida por arriba -> venta
                edge = top if side == -1 else bot
                opp = bot if side == -1 else top
                out_ext, k_re = None, None
                for k in range(len(C)):
                    if mins[k] > 930: break
                    beyond = (H[k] - edge) >= brk * TICK if side == -1 else (edge - L[k]) >= brk * TICK
                    if beyond:
                        x = H[k] if side == -1 else L[k]
                        out_ext = x if out_ext is None else (max(out_ext, x) if side == -1 else min(out_ext, x))
                    if out_ext is not None and k_re is None and ((C[k] < edge) if side == -1 else (C[k] > edge)):
                        k_re = k
                    if k_re is not None:
                        if k - k_re > 2:  # sin gatillo a tiempo: espera otra falsa salida
                            out_ext, k_re = None, None; continue
                        if (bs[k] if side == -1 else bb[k]):
                            ent = C[k]
                            stop = out_ext + buf * TICK if side == -1 else out_ext - buf * TICK
                            stop = max(stop, H[k_re:k + 1].max() + buf * TICK) if side == -1 else min(stop, L[k_re:k + 1].min() - buf * TICK)
                            risk = abs(ent - stop)
                            tgt = prev['poc'] if target == 'poc' else opp
                            if risk < 4 * TICK or (tgt - ent) * side <= 0: break
                            r, why, j = simulate(H, L, C, mins, k, side, ent, stop, tgt)
                            out.append(dict(date=str(day), model=2, side=side, time=t[k], ent=ent, stop=stop, tgt=tgt,
                                            risk_t=risk / TICK, ticks=r, why=why, exit=t[j]))
                            break
    T = pd.DataFrame(out)
    if len(T):
        T['usd'] = T.ticks * TV - COST
        T['R'] = T.ticks / T.risk_t
    return T


def stats(T):
    if not len(T):
        return dict(n=0, wr=np.nan, pf=np.nan, net=0.0, exp=np.nan, R=np.nan, mdd=0.0)
    u = T.usd.values
    gp, gl = u[u > 0].sum(), -u[u <= 0].sum()
    eq = np.cumsum(u)
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min()
    return dict(n=len(u), wr=(u > 0).mean(), pf=gp / gl if gl else np.inf, net=u.sum(), exp=u.mean(),
                R=T.R.mean(), mdd=dd)
