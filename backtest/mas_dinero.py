"""Modelo B · Más dinero: backtest con velas de 1 minuto de ES exportadas de NinjaTrader.

Datos: un .txt por contrato ("ES 03-24.Last.txt"), formato "yyyyMMdd HHmmss;o;h;l;c;v",
hora UTC al CIERRE de cada vela. Cada día se opera el contrato con más volumen en la sesión 9:30–16:00 NY,
y todos los indicadores de ese día salen del mismo contrato (así el cambio de contrato no mueve los niveles).

Reglas (las del dashboard):
  10:12 NY: cierre de la vela de 3 min 10:09–10:12. Compra si está arriba de la EMA 20 de 3 min, venta si abajo.
  A  el precio está fuera del área de valor de ayer, arriba del VAH o abajo del VAL
     (perfil 9:30–16:00 NY, 70 % del volumen). Así reproduce el embudo del dashboard (476 de 713 días).
  C  perfil de hoy (9:30–10:12): sin compra si el POC está en el 38 % de arriba (P), sin venta en el 38 % de abajo (b).
  BOS  en los últimos 60 min (20 velas de 3 min) no debe haber un cierre que rompa el último swing en contra
       (swing = 2 velas a cada lado).
  VWAP  del día desde las 9:30, a favor.
  Bracket: SL 30, TP1 40 (mitad), TP2 160 (mitad), sin break-even; cierre 15:59 NY. Si en una misma vela
  se tocan stop y objetivo, cuenta el stop (conservador).
"""
import glob
import os
import re
import zipfile
from dataclasses import dataclass

import numpy as np
import pandas as pd

TICK = 0.25
ES_TICK_USD, MES_TICK_USD = 12.5, 1.25
ES_COST = 1 * ES_TICK_USD + 4.5          # por contrato ES: 1 tick de deslizamiento + comisión
MES_COST = 2.49                          # por MES ida y vuelta
NY = 'America/New_York'


@dataclass(frozen=True)
class Params:
    entry: str = '10:12'
    entry_tz: str = NY            # 'America/Mexico_City' para entrar a la misma hora de CDMX todo el año
    ema_len: int = 20
    sl: int = 30
    tp1: int = 40
    tp2: int = 160
    breakeven: bool = False
    filt_a: bool = True
    filt_c: bool = True
    filt_bos: bool = True
    filt_vwap: bool = True
    filt_gap: bool = False
    gap_max: float = 8.0          # puntos: no se opera si el gap de apertura va en contra por esto o más
    skip_months: tuple = ()       # meses que no se operan, p. ej. (2, 3) para saltar febrero y marzo (opcional)
    c_frac: float = 0.38
    va_frac: float = 0.70
    bos_bars: int = 20
    bar_min: int = 3              # minutos de las velas de la EMA y del BOS (3 = el modelo; 1 o 5 para probar)
    close_at: str = '15:59'


# ---------- carga ----------

def _read_txt(path_or_buf):
    df = pd.read_csv(path_or_buf, sep=';', header=None, names=['ts', 'o', 'h', 'l', 'c', 'v'])
    ts = pd.to_datetime(df.ts, format='%Y%m%d %H%M%S').dt.tz_localize('UTC') - pd.Timedelta(minutes=1)
    df.index = ts.dt.tz_convert(NY)  # hora de INICIO de la vela, en NY
    return df[['o', 'h', 'l', 'c', 'v']]


def load_contracts(folder):
    """Lee .txt sueltos o dentro de .zip. Devuelve {contrato: DataFrame}."""
    out = {}
    pat = re.compile(r'(ES \d\d-\d\d)\.Last\.txt$')
    for p in sorted(glob.glob(os.path.join(folder, '*'))):
        if p.endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    m = pat.search(n)
                    if m:
                        with z.open(n) as f:
                            out[m.group(1)] = _read_txt(f)
        else:
            m = pat.search(p)
            if m:
                out[m.group(1)] = _read_txt(p)
    for k, df in out.items():
        out[k] = df[~df.index.duplicated()].sort_index()
    return out


# ---------- utilidades por contrato ----------

def _rth(df):
    t = df.index
    mins = t.hour * 60 + t.minute
    return df[(mins >= 570) & (mins < 960)]  # 9:30–15:59 (inicio de vela)


def value_area(bars, frac):
    """VAH, VAL y POC repartiendo el volumen de cada vela de 1 min entre sus ticks."""
    lo = np.round(bars.l.values / TICK).astype(int)
    hi = np.round(bars.h.values / TICK).astype(int)
    base = lo.min()
    prof = np.zeros(hi.max() - base + 1)
    for a, b, v in zip(lo - base, hi - base, bars.v.values):
        prof[a:b + 1] += v / (b - a + 1)
    poc = int(prof.argmax())
    tot, acc, i, j = prof.sum(), prof[poc], poc, poc
    while acc < frac * tot:
        up = prof[j + 1] if j + 1 < len(prof) else -1
        dn = prof[i - 1] if i > 0 else -1
        if up >= dn:
            j += 1
            acc += up
        else:
            i -= 1
            acc += dn
    return (j + base) * TICK, (i + base) * TICK, (poc + base) * TICK


def poc_position(bars):
    """Dónde cae el POC dentro del rango (0 = mínimo, 1 = máximo)."""
    _, _, poc = value_area(bars, 0.0)
    lo, hi = bars.l.min(), bars.h.max()
    return 0.5 if hi == lo else (poc - lo) / (hi - lo)


def _bos_against(c3, d):
    """c3: velas de 3 min de la ventana (DataFrame). d: 1 compra, -1 venta."""
    h, l, c = c3.h.values, c3.l.values, c3.c.values
    swing, n = None, len(c)
    for k in range(n):
        j = k - 2
        if j - 2 >= 0:
            ref = l if d > 0 else h
            if all((ref[j] < ref[m]) if d > 0 else (ref[j] > ref[m]) for m in (j - 2, j - 1, j + 1, j + 2)):
                swing = (j, ref[j])
        if swing and k > swing[0] + 2 and ((c[k] < swing[1]) if d > 0 else (c[k] > swing[1])):
            return True
    return False


# ---------- día por día ----------

def choose_contracts(contracts):
    """Para cada fecha NY, el contrato con más volumen en la sesión regular."""
    vols = []
    for k, df in contracts.items():
        r = _rth(df)
        vols.append(r.v.groupby(r.index.date).sum().rename(k))
    v = pd.concat(vols, axis=1).fillna(0)
    # fuera fines de semana y velas sueltas: un día cuenta si tiene sesión (≥ 100 velas RTH de 1 min)
    nbars = pd.concat([_rth(df).groupby(_rth(df).index.date).size().rename(k) for k, df in contracts.items()],
                      axis=1).fillna(0).max(axis=1)
    ok = [d for d in v.index if d.weekday() < 5 and nbars.get(d, 0) >= 100]
    return v.loc[ok].idxmax(axis=1)


def prepare(contracts):
    """Precalcula por contrato: velas RTH por día, EMA de 3 min."""
    prep = {}
    for k, df in contracts.items():
        agg = {'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last', 'v': 'sum'}
        bars = {m: (df if m == 1 else df.resample(f'{m}min', label='left', closed='left').agg(agg).dropna()) for m in (1, 3, 5)}
        r = _rth(df)
        prep[k] = {'m1': df, 'b3': bars[3], 'bars': bars, 'days': {d: g for d, g in r.groupby(r.index.date)}}
    return prep


def _prev_full_session(P, day):
    """Última sesión completa (≥ 300 velas RTH) antes de `day` en el mismo contrato."""
    prev = [d for d in P['days'] if d < day and len(P['days'][d]) >= 300]
    return max(prev) if prev else None


def day_signal(prep, contract, day, p: Params):
    """Devuelve dict con dirección, filtros y precio de entrada, o None si faltan datos."""
    P = prep[contract]
    prev_day = _prev_full_session(P, day)
    if day not in P['days'] or prev_day is None or (day - prev_day).days > 5:
        return None
    today, yday = P['days'][day], P['days'][prev_day]
    eh, em = map(int, p.entry.split(':'))
    t_ent = (pd.Timestamp(day).tz_localize(p.entry_tz) + pd.Timedelta(hours=eh, minutes=em)).tz_convert(NY)
    b3 = P['bars'][p.bar_min] if 'bars' in P else P['b3']
    closed = b3[b3.index < t_ent]                      # velas ya cerradas (de bar_min minutos)
    if len(closed) < p.ema_len * 3 or closed.index[-1] != t_ent - pd.Timedelta(minutes=p.bar_min):
        return None
    ema = closed.c.ewm(span=p.ema_len, adjust=False).mean().iloc[-1]
    ent = closed.c.iloc[-1]
    d = 1 if ent > ema else -1
    vah, val, _ = value_area(yday, p.va_frac)
    morning = today[today.index < t_ent]
    if len(morning) < 10:
        return None
    pos = poc_position(morning)
    tp = (morning.h + morning.l + morning.c) / 3
    vwap = (tp * morning.v).sum() / morning.v.sum()
    win = closed.iloc[-p.bos_bars:]
    gap = d * (today.o.iloc[0] - yday.c.iloc[-1])      # apertura 9:30 contra cierre de ayer, a favor (+) o en contra (−)
    return {
        'gap': gap, 'GAP': gap > -p.gap_max,
        'fecha': day, 'contrato': contract, 'dir': d, 'entrada': ent, 'ema': ema, 't': t_ent,
        'A': (ent > vah) or (ent < val),               # fuera del valor de ayer, de cualquier lado
        'C': not ((d > 0 and pos >= 1 - p.c_frac) or (d < 0 and pos <= p.c_frac)),
        'BOS': not _bos_against(win, d),
        'VWAP': (ent > vwap) if d > 0 else (ent < vwap),
        'vah': vah, 'val': val, 'vwap': vwap, 'poc_pos': pos,
    }


def simulate(prep, sig, p: Params):
    """Bracket sobre velas de 1 min desde la entrada hasta el cierre. Ticks por mitad (a, b)."""
    m1 = prep[sig['contrato']]['m1']
    ch, cm = map(int, p.close_at.split(':'))
    t_end = pd.Timestamp(sig['fecha']).tz_localize(NY) + pd.Timedelta(hours=ch, minutes=cm)
    bars = m1[(m1.index >= sig['t']) & (m1.index < t_end)]
    d, e = sig['dir'], sig['entrada']
    sl = e - d * p.sl * TICK
    t1, t2 = e + d * p.tp1 * TICK, e + d * p.tp2 * TICK
    half1 = None
    stop = sl
    for hi, lo in zip(bars.h.values, bars.l.values):
        adv = (lo <= stop) if d > 0 else (hi >= stop)
        f1 = (hi >= t1) if d > 0 else (lo <= t1)
        f2 = (hi >= t2) if d > 0 else (lo <= t2)
        stop_ticks = round(d * (stop - e) / TICK)
        if half1 is None:
            if adv:
                return stop_ticks, stop_ticks, 'Stop'
            if f1:
                half1 = p.tp1
                if f2:
                    return half1, p.tp2, 'TP1 + TP2'
                if p.breakeven:
                    stop = e
            continue
        if adv:
            return half1, stop_ticks, 'TP1 + stop' if stop_ticks < 0 else 'TP1 + BE'
        if f2:
            return half1, p.tp2, 'TP1 + TP2'
    last = bars.c.values[-1] if len(bars) else e
    lt = round(d * (last - e) / TICK)
    if half1 is None:
        return lt, lt, 'Cierre 15:59'
    return half1, lt, 'TP1 + cierre 15:59'


def run(prep, chosen, p: Params = Params(), start=None, end=None, signals=None):
    """Devuelve (operaciones, señales). Pasa `signals` ya calculadas para no recalcular."""
    days = [d for d in chosen.index if (start is None or d >= start) and (end is None or d <= end)]
    if signals is None:
        rows = []
        for d in days:
            s = day_signal(prep, chosen[d], d, p)
            if s:
                rows.append(s)
        signals = pd.DataFrame(rows)
    keep = np.ones(len(signals), bool)
    for f, on in (('A', p.filt_a), ('C', p.filt_c), ('BOS', p.filt_bos), ('VWAP', p.filt_vwap), ('GAP', p.filt_gap)):
        if on:
            keep &= signals[f].values
    if p.skip_months:
        keep &= ~pd.to_datetime(signals.fecha).dt.month.isin(p.skip_months).values
    trades = []
    for s in signals[keep].to_dict('records'):
        a, b, out = simulate(prep, s, p)
        ticks = a + b
        trades.append({**s, 'salida': out, 'ticks': ticks,
                       'usd_2es': ticks * ES_TICK_USD - 2 * ES_COST,
                       'usd_8mes': 4 * ticks * MES_TICK_USD - 8 * MES_COST})
    return pd.DataFrame(trades), signals


def stats(t, col='usd_8mes'):
    if len(t) == 0:
        return {'n': 0, 'wr': 0, 'pf': 0, 'net': 0, 'mdd': 0, 'avg': 0, 'racha': 0}
    u = t[col].values
    eq = u.cumsum()
    loss = -u[u < 0].sum()
    racha = mx = 0
    for x in u:
        racha = racha + 1 if x < 0 else 0
        mx = max(mx, racha)
    return {'n': len(u), 'wr': (u > 0).mean(), 'pf': u[u > 0].sum() / loss if loss else np.inf,
            'net': u.sum(), 'mdd': (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min(),
            'avg': u.mean(), 'racha': mx}


# Modelo final: 10:12 NY, 4 filtros + gap, bracket 35/35/120 con break-even tras TP1.
MODELO_GAP = Params(sl=35, tp1=35, tp2=120, breakeven=True, filt_gap=True)
