"""Modelo B backtest on HistData SPXUSD 1-minute bars (EST fixed, UTC-5).

Rules: entry 9:12 Mexico City, side = entry price vs EMA20 of 3-minute closes,
2 contracts, SL 45 ticks, TP1 30, TP2 60, BE after TP1, forced close 15:59 New York.
Costs: 1 tick slippage + 4.50 USD commission per contract (34 USD per trade).
"""
import glob, sys
import numpy as np, pandas as pd

TICK, TV = 0.25, 12.5
COST = 2 * (1 * TV + 4.5)


def load(folder):
    fs = sorted(glob.glob(folder + '/DAT_ASCII_SPXUSD_M1_*.csv'))
    df = pd.concat([pd.read_csv(f, sep=';', header=None, names=['ts', 'o', 'h', 'l', 'c', 'v']) for f in fs])
    t = pd.to_datetime(df.ts, format='%Y%m%d %H%M%S') + pd.Timedelta(hours=5)  # EST fixed -> UTC
    df.index = t.dt.tz_localize('UTC')
    df = df[['o', 'h', 'l', 'c']].sort_index()
    return df[~df.index.duplicated()]


def resample(df, minutes):
    if minutes == 1:
        return df
    r = df.resample(f'{minutes}min', label='left', closed='left').agg({'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last'})
    return r.dropna()


def ema3(df1, length=20, tf=3):
    b = resample(df1, tf)
    e = b.c.ewm(span=length, adjust=False).mean()
    e.index = e.index + pd.Timedelta(minutes=tf)  # value known at the bar's close
    return e


def run(df1, exec_tf=1, ema_len=20, ema_tf=3, sl=45, tp1=30, tp2=60, side_mode='ema', stop_first=True):
    """exec_tf: candle size used to simulate fills (1 or 3 minutes)."""
    ex = resample(df1, exec_tf)
    ema = ema3(df1, ema_len, ema_tf)
    mx = ex.index.tz_convert('America/Mexico_City')
    ny = ex.index.tz_convert('America/New_York')
    ex = ex.assign(mxd=mx.date, mxh=mx.hour, mxm=mx.minute, nyh=ny.hour, nym=ny.minute)
    O, H, L, C = ex.o.values, ex.h.values, ex.l.values, ex.c.values
    idx = ex.index
    out = []
    starts = np.where((ex.mxh.values == 9) & (ex.mxm.values == 12))[0]
    for s in starts:
        t0 = idx[s]
        if t0.weekday() >= 5:
            continue
        e = ema.asof(t0)
        ent = O[s]
        if side_mode == 'ema':
            d = 1 if ent > e else -1
        elif side_mode == 'inv':
            d = -1 if ent > e else 1
        else:
            d = int(side_mode)
        slp, t1p, t2p = ent - d * sl * TICK, ent + d * tp1 * TICK, ent + d * tp2 * TICK
        l1 = l2 = True
        r1 = r2 = 0.0
        w1 = w2 = ''
        stop = slp
        j = s
        day = ex.mxd.values[s]
        tp1_min = None
        while j < len(C) and (l1 or l2):
            if ex.mxd.values[j] != day:
                break
            hit_sl = (L[j] <= stop) if d == 1 else (H[j] >= stop)
            hit1 = l1 and ((H[j] >= t1p) if d == 1 else (L[j] <= t1p))
            hit2 = l2 and ((H[j] >= t2p) if d == 1 else (L[j] <= t2p))
            if hit_sl and (stop_first or not (hit1 or hit2)):
                fill = stop
                if j > s:
                    fill = min(O[j], stop) if d == 1 else max(O[j], stop)
                be = (not l1) and stop == ent
                if l1:
                    r1, w1, l1 = (fill - ent) * d / TICK, 'SL', False
                if l2:
                    r2, w2, l2 = (fill - ent) * d / TICK, 'BE' if be else 'SL', False
                break
            if hit1:
                r1, w1, l1 = tp1, 'TP1', False
                tp1_min = (idx[j] - t0).total_seconds() / 60 + exec_tf
                stop = ent
            if hit2:
                r2, w2, l2 = tp2, 'TP2', False
            closing = ex.nyh.values[j] == 15 and ex.nym.values[j] + exec_tf > 59
            if not closing and (j + 1 >= len(C) or (idx[j + 1] - idx[j]) > pd.Timedelta(minutes=30)):
                closing = True  # sesión recortada (festivo): cierre en la última vela
            if (l1 or l2) and closing:
                if l1:
                    r1, w1, l1 = (C[j] - ent) * d / TICK, 'CL', False
                if l2:
                    r2, w2, l2 = (C[j] - ent) * d / TICK, 'CL', False
                break
            if l1 or l2:
                j += 1
        if l1 or l2:
            continue
        usd = (r1 + r2) * TV - COST
        oc = 'TP1 + TP2' if (w1, w2) == ('TP1', 'TP2') else 'TP1 + BE' if (w1, w2) == ('TP1', 'BE') else 'TP1 + cierre' if w1 == 'TP1' else 'Stop (−2)' if w1 == 'SL' else 'Cierre 15:59'
        out.append(dict(date=str(day), dir=d, entry=ent, ema=e, usd=round(usd, 2), out=oc,
                        mins=int((idx[min(j, len(idx) - 1)] - t0).total_seconds() / 60 + exec_tf), mins_tp1=tp1_min))
    return pd.DataFrame(out)


def stats(T):
    u = T.usd.values
    gp, gl = u[u > 0].sum(), -u[u <= 0].sum()
    eq = np.cumsum(u)
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min()
    return dict(n=len(u), wr=(u > 0).mean(), pf=gp / gl if gl else np.inf, net=u.sum(), exp=u.mean(), mdd=dd)
