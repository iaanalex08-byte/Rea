"""Versión mecánica de la estrategia (sesgo + FVG/envolventes + gatillo en 1m).

Reglas (todas parametrizables en `Params`):

1. Sesgo diario: alcista si el cierre diario rompe el último swing high diario
   (fractal de 5 velas), bajista si rompe el último swing low. El estado se
   mantiene hasta que se rompe el lado contrario. Se usa el sesgo del día
   anterior (sin mirar al futuro).
2. Zonas en H1 y H4:
   - FVG alcista: mínimo de la vela 3 > máximo de la vela 1 (hueco >= min_gap).
   - Envolvente alcista válida: vela previa bajista, cuerpo actual envuelve el
     cuerpo previo y cierra por encima del máximo previo. Zona = desde la mecha
     (mínimo) hasta el 50% de la vela ("wick50") o el cuerpo completo ("body").
   - Una zona está "no mitigada" mientras el precio no haya vuelto a tocarla.
3. Impulso actual = zonas creadas desde el último swing low de H4 (leg_tf). Si hay
   varias zonas abiertas, se descarta la primera y se espera la más profunda
   (select="deepest"). Variantes: "skip_first" o "all".
4. Ventana: solo se busca entrada entre session_start y entry_end (hora NY).
   Se salta el día si hay noticia de alto impacto (news_calendar.csv).
5. Gatillo en 1m: el precio toca la zona y después una vela alcista cierra
   (con cuerpo) por encima del último fractal high de 1m (3 velas).
6. Stop en el mínimo del retroceso - sl_buffer. Objetivo = rr * riesgo.
   Si no toca stop ni objetivo, se cierra a exit_time. Si una misma vela toca
   stop y objetivo, se cuenta como pérdida (supuesto conservador).
7. Máximo una operación por día. Las ventas son el espejo exacto de las compras.
"""
import os
from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

from data import Bars, Market

NEWS = os.path.join(os.path.dirname(__file__), "news_calendar.csv")


@dataclass
class Params:
    session_start: str = "09:30"
    entry_end: str = "10:30"          # apertura de NY: primera hora
    exit_time: str = "15:55"
    zone_tfs: tuple = ("H1", "H4")
    leg_tf: str = "H4"               # temporalidad del swing que define el impulso
    use_engulf: bool = True
    engulf_mode: str = "wick50"      # "wick50" | "body"
    min_gap_pts: float = 5.0
    select: str = "deepest"          # "deepest" | "skip_first" | "all"
    min_zones_for_skip: int = 2
    rr: float = 2.0
    sl_buffer: float = 1.0
    min_risk: float = 4.0
    max_risk: float = 60.0
    trigger_timeout: int = 45        # minutos desde el toque
    cost_pts: float = 1.0            # spread + comisión + deslizamiento (ida y vuelta)
    news_filter: bool = True
    directions: str = "both"         # "both" | "long" | "short"
    zone_scope: str = "leg"          # "leg": solo zonas del impulso actual | "all": cualquier zona reciente
    max_age_days: float = 10.0       # con zone_scope="all": antigüedad máxima de la zona
    max_dist_atr: float = 1.0        # con zone_scope="all": distancia máx. a la apertura (x ATR diario)
    mitigation: str = "touch"        # "touch": mitigada al tocarla | "half": mitigada al llegar al 50%

    def label(self):
        return ", ".join(f"{k}={v}" for k, v in asdict(self).items())


# ---------------------------------------------------------------- zonas
def find_zones(b: Bars, tf: str, p: Params):
    z = []
    o, h, l, c = b.o, b.h, b.l, b.c
    n = len(o)
    i = np.arange(2, n)
    gap = l[i] - h[i - 2]
    for k in i[gap >= p.min_gap_pts]:
        z.append((b.start[k - 2], b.end[k], h[k - 2], l[k], "FVG", tf))
    if p.use_engulf:
        i = np.arange(1, n)
        ok = ((c[i - 1] < o[i - 1]) & (c[i] > o[i]) & (o[i] <= c[i - 1])
              & (c[i] >= o[i - 1]) & (c[i] > h[i - 1]))
        for k in i[ok]:
            if p.engulf_mode == "body":
                bot, top = o[k], c[k]
            else:
                bot, top = l[k], l[k] + 0.5 * (h[k] - l[k])
            if top - bot >= p.min_gap_pts:
                z.append((b.start[k - 1], b.end[k], bot, top, "ENG", tf))
    return pd.DataFrame(z, columns=["anchor", "created", "bottom", "top", "kind", "tf"])


def first_touch(zones, m1: Bars, h1: Bars, levels=None):
    """Índice 1m del primer toque (low <= nivel) posterior a la creación."""
    out = np.full(len(zones), len(m1.l), dtype=np.int64)
    if levels is None:
        levels = zones["top"].to_numpy()
    for r, (cr, top) in enumerate(zip(zones["created"].to_numpy(), levels)):
        b0 = np.searchsorted(h1.start, cr)
        # minutos entre la creación y el inicio de la siguiente H1 (si los hay)
        if b0 < len(h1.start) and h1.start[b0] > cr:
            seg = m1.l[cr:h1.start[b0]]
            hit = np.flatnonzero(seg <= top)
            if hit.size:
                out[r] = cr + hit[0]
                continue
        hit = np.flatnonzero(h1.l[b0:] <= top)
        if not hit.size:
            continue
        b = b0 + hit[0]
        seg = m1.l[h1.start[b]:h1.end[b]]
        out[r] = h1.start[b] + np.flatnonzero(seg <= top)[0]
    return out


# ---------------------------------------------------------------- estructura
def swing_lows(b: Bars, n=2):
    """(índice 1m de confirmación, índice 1m de inicio de la vela swing)."""
    l = b.l
    conf, anchor = [], []
    for k in range(n, len(l) - n):
        if l[k] < l[k - n:k].min() and l[k] <= l[k + 1:k + n + 1].min():
            conf.append(b.end[k + n])
            anchor.append(b.start[k])
    return np.array(conf), np.array(anchor)


def daily_bias(d1: Bars, n=2):
    """+1 alcista / -1 bajista / 0 neutral, estado tras el cierre de cada día."""
    h, l, c = d1.h, d1.l, d1.c
    state = np.zeros(len(c), dtype=int)
    sh = sl = None
    cur = 0
    for k in range(len(c)):
        j = k - n  # vela central confirmada al cierre de k
        if j >= n:
            if h[j] > h[j - n:j].max() and h[j] >= h[j + 1:k + 1].max():
                sh = h[j]
            if l[j] < l[j - n:j].min() and l[j] <= l[j + 1:k + 1].min():
                sl = l[j]
        if sh is not None and c[k] > sh:
            cur = 1
        elif sl is not None and c[k] < sl:
            cur = -1
        state[k] = cur
    return state


def fractal_high_ref(m1: Bars):
    """Nivel del último fractal high de 1m (3 velas) conocido en cada minuto."""
    h = m1.h
    k = np.arange(1, len(h) - 1)
    is_fh = (h[k] > h[k - 1]) & (h[k] >= h[k + 1])
    ref = np.full(len(h), np.nan)
    idx = k[is_fh] + 2
    keep = idx < len(h)
    ref[idx[keep]] = h[k[is_fh]][keep]
    return pd.Series(ref).ffill().to_numpy()


# ---------------------------------------------------------------- sesiones
def sessions(local: pd.DatetimeIndex, p: Params):
    def mins(s):
        hh, mm = s.split(":")
        return int(hh) * 60 + int(mm)
    mod = local.hour * 60 + local.minute
    date = local.normalize()
    s0, s1, sx = mins(p.session_start), mins(p.entry_end), mins(p.exit_time)
    df = pd.DataFrame({"date": date, "mod": mod, "i": np.arange(len(local))})
    df = df[(df["mod"] >= s0) & (df["mod"] < sx) & (date.weekday < 5)]
    out = []
    for d, g in df.groupby("date", sort=True):
        m = g["mod"].to_numpy()
        ii = g["i"].to_numpy()
        if m[0] > s0 + 5:          # día festivo / sin datos en la apertura
            continue
        e = ii[m < s1]
        if not e.size:
            continue
        out.append((d.date(), ii[0], e[-1] + 1, ii[-1]))
    return out


# ---------------------------------------------------------------- motor
class Side:
    """Precomputa todo lo necesario para operar un lado (compras sobre los datos
    originales o ventas sobre los datos espejo)."""

    def __init__(self, mk: Market, p: Params):
        self.mk, self.p = mk, p
        frames = []
        for tf in p.zone_tfs:
            frames.append(find_zones(getattr(mk, tf.lower()), tf, p))
        z = pd.concat(frames, ignore_index=True)
        lvl = z["top"].to_numpy()
        if p.mitigation == "half":
            lvl = ((z["top"] + z["bottom"]) / 2).to_numpy()
        z["mit_level"] = lvl
        z["touch"] = first_touch(z, mk.m1, mk.h1, lvl)
        self.z = z.sort_values("created").reset_index(drop=True)
        self.sw_conf, self.sw_anchor = swing_lows(getattr(mk, p.leg_tf.lower()))
        self.ref = fractal_high_ref(mk.m1)
        d = mk.d1
        tr_ = np.maximum(d.h[1:], d.c[:-1]) - np.minimum(d.l[1:], d.c[:-1])
        atr = pd.Series(np.r_[d.h[0] - d.l[0], tr_]).rolling(14, min_periods=5).mean()
        self.atr = atr.to_numpy()
        self.created_t = mk.local[self.z["created"].clip(upper=len(mk.local) - 1)].to_numpy()

    def candidates(self, S):
        z, p = self.z, self.p
        px = self.mk.m1.c[S - 1]
        m = (z["created"].to_numpy() <= S) & (z["touch"].to_numpy() >= S) \
            & (z["mit_level"].to_numpy() < px)
        if p.zone_scope == "leg":
            k = np.searchsorted(self.sw_conf, S, side="right") - 1
            if k < 0:
                return z.iloc[0:0]
            m &= z["anchor"].to_numpy() >= self.sw_anchor[k]
        else:
            t0 = self.mk.local[S] - pd.Timedelta(days=p.max_age_days)
            di = np.searchsorted(self.mk.d1.start, S, side="right") - 2
            atr = self.atr[max(di, 0)]
            m &= (self.created_t >= np.datetime64(t0)) & (z["top"].to_numpy() >= px - p.max_dist_atr * atr)
        return z[m].sort_values("top", ascending=False)

    def run_day(self, S, E, X):
        p, m1 = self.p, self.mk.m1
        cand = self.candidates(S)
        if cand.empty:
            return None, "sin_zonas"
        if len(cand) >= p.min_zones_for_skip and p.select == "deepest":
            allowed = cand.iloc[[-1]]
        elif len(cand) >= p.min_zones_for_skip and p.select == "skip_first":
            allowed = cand.iloc[1:]
        else:
            allowed = cand
        zones = list(allowed.itertuples(index=False))
        active = None
        touch_j = rlow = None
        for j in range(S, E):
            if active is None:
                hit = [zz for zz in zones if m1.l[j] <= zz.top]
                if not hit:
                    continue
                active = hit[0]
                touch_j, rlow = j, m1.l[j]
            else:
                rlow = min(rlow, m1.l[j])
            if m1.c[j] < active.bottom:          # zona rota: pasa a la siguiente
                zones = [zz for zz in zones if zz.top < active.top]
                active = None
                if not zones:
                    return None, "zona_rota"
                continue
            if j - touch_j > p.trigger_timeout:
                return None, "sin_gatillo"
            ref = self.ref[j]
            if m1.c[j] > m1.o[j] and not np.isnan(ref) and m1.c[j] > ref:
                entry = m1.c[j]
                stop = rlow - p.sl_buffer
                risk = entry - stop
                if risk < p.min_risk or risk > p.max_risk:
                    return None, "stop_fuera_rango"
                tp = entry + p.rr * risk
                return self._manage(j, X, entry, stop, tp, risk, active), "operacion"
        return None, ("sin_gatillo" if active is not None else "no_llego")

    def _manage(self, j, X, entry, stop, tp, risk, zone):
        m1 = self.mk.m1
        res, exit_px, k = None, None, X
        for k in range(j + 1, X + 1):
            if m1.l[k] <= stop:
                res, exit_px = "SL", stop
                break
            if m1.h[k] >= tp:
                res, exit_px = "TP", tp
                break
        if res is None:
            res, exit_px = "TIEMPO", m1.c[X]
        r = (exit_px - entry) / risk - self.p.cost_pts / risk
        return dict(entry_i=j, exit_i=k, entry=entry, stop=stop, tp=tp, risk_pts=risk,
                    exit=exit_px, result=res, R=r, zone_kind=zone.kind, zone_tf=zone.tf)


def backtest(mk: Market, p: Params, news_path=NEWS):
    bias = daily_bias(mk.d1)
    day_idx = {d: i for i, d in enumerate(mk.d1_day)}
    news = set()
    if p.news_filter and os.path.exists(news_path):
        news = set(pd.to_datetime(pd.read_csv(news_path)["date"]).dt.date)
    long_side = Side(mk, p) if p.directions in ("both", "long") else None
    short_side = Side(mk.mirrored(), p) if p.directions in ("both", "short") else None

    trades, log = [], []
    for d, S, E, X in sessions(mk.local, p):
        di = day_idx.get(d)
        b = bias[di - 1] if di else 0
        if d in news:
            log.append((d, b, "noticia"))
            continue
        side, sgn = (long_side, 1) if b == 1 else (short_side, -1) if b == -1 else (None, 0)
        if side is None:
            log.append((d, b, "sin_sesgo" if b == 0 else "lado_desactivado"))
            continue
        t, why = side.run_day(S, E, X)
        log.append((d, b, why))
        if t:
            for key in ("entry", "stop", "tp", "exit"):
                t[key] *= sgn
            t.update(date=d, side="LONG" if sgn == 1 else "SHORT",
                     entry_time=mk.local[t["entry_i"]], exit_time=mk.local[t["exit_i"]])
            trades.append(t)
    cols = ["date", "side", "entry_time", "exit_time", "entry", "stop", "tp", "exit",
            "risk_pts", "result", "R", "zone_kind", "zone_tf"]
    tr = pd.DataFrame(trades, columns=cols + ["entry_i", "exit_i"])[cols]
    return tr, pd.DataFrame(log, columns=["date", "bias", "outcome"])


# ---------------------------------------------------------------- métricas
def stats(tr: pd.DataFrame):
    if tr.empty:
        return dict(trades=0)
    r = tr["R"].to_numpy()
    eq = np.cumsum(r)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    losses = (r < 0).astype(int)
    streak = run = 0
    for x in losses:
        run = run + 1 if x else 0
        streak = max(streak, run)
    gw, gl = r[r > 0].sum(), -r[r < 0].sum()
    return dict(trades=len(r), winrate=float((tr["result"] == "TP").mean()),
                avg_R=float(r.mean()), total_R=float(r.sum()),
                profit_factor=float(gw / gl) if gl else float("inf"),
                max_dd_R=float(-dd.min()), max_losing_streak=int(streak),
                avg_risk_pts=float(tr["risk_pts"].mean()))
