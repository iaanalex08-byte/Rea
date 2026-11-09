"""
Backtest de la metodología de Gerard (tendencia M30 + EMA20, entradas límite en
imbalances (FVG) bajo mínimos / sobre máximos relevantes, sin stop estructural,
salida por "personal daily loss" sobre el flotante, y promediadas opcionales).

Reglas cuantificadas (las decisiones que el video deja abiertas están marcadas
con [SUPUESTO] y son parámetros):

1. Tendencia (vela cerrada t, timeframe de señal):
   alcista  = close > EMA20  y  EMA20[t] > EMA20[t - slope_n]   (dirección diagonal)
   bajista  = close < EMA20  y  EMA20[t] < EMA20[t - slope_n]
2. Máximos / mínimos relevantes: pivotes fractales con `pivot_n` velas a cada
   lado (se confirman pivot_n velas después -> sin look-ahead).
3. Imbalance = Fair Value Gap de 3 velas:
   FVG alcista en vela k: low[k] > high[k-2]  -> zona [high[k-2], low[k]]
   FVG bajista en vela k: high[k] < low[k-2]  -> zona [high[k], low[k-2]]
4. Setup de compra (tendencia alcista): existe un FVG alcista NO tocado cuyo
   techo está por debajo del último mínimo relevante confirmado
   (fvg_mode="below_pivot") -> orden límite de compra en el techo del FVG
   (o en el 50 %, entry="mid"). Ventas: espejo.
   fvg_mode="any" relaja la condición: cualquier FVG no tocado a favor de la
   tendencia.
5. Objetivo [SUPUESTO]: el último máximo relevante (liquidez opuesta) o un
   número fijo de puntos (target_mode).
6. Riesgo: sin stop estructural. Se cierra todo cuando el flotante alcanza
   -(daily_loss_usd + PnL realizado negativo del día). Al tocarse el límite
   no se opera más ese día.
7. Promediada [SUPUESTO]: hasta `max_adds` entradas extra de `add_qty`
   contratos cada `add_step_pts` puntos en contra.
8. Sesión [SUPUESTO]: órdenes sólo entre session_start y session_end (hora NY);
   todo se cierra en flat_time (antes del cierre de Apex 16:59 ET).
   Máximo `max_trades_day` ejecuciones por día.

Ejecución: si se pasa un DataFrame de menor timeframe (p. ej. 5m), los
rellenos y salidas se resuelven sobre esas sub-velas. Dentro de cada vela se
asume el peor orden posible: primero se evalúa la pérdida y después el
objetivo (conservador).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import numpy as np
import pandas as pd


@dataclass
class Params:
    point_value: float = 20.0         # NQ = 20 $/pt, ES = 50 $/pt
    tick: float = 0.25
    qty: int = 1
    ema_len: int = 20
    slope_n: int = 5
    pivot_n: int = 3
    fvg_mode: str = "below_pivot"     # "below_pivot" | "any" | "none" (control: entra a mercado sin FVG)
    entry: str = "edge"               # "edge" (borde próximo del FVG) | "mid"
    fvg_max_age: int = 48             # velas que un FVG sigue siendo válido
    target_mode: str = "swing"        # "swing" | "fixed"
    target_pts: float = 40.0          # si target_mode == "fixed"
    min_target_pts: float = 10.0      # descarta setups con objetivo demasiado cerca
    daily_loss_usd: float = 1000.0    # personal daily loss (flotante)
    max_adds: int = 0                 # promediadas
    add_step_pts: float = 20.0
    add_qty: int = 1
    max_trades_day: int = 2
    session_start: str = "08:00"
    session_end: str = "15:00"
    flat_time: str = "15:55"
    commission_rt: float = 5.0        # $ ida y vuelta por contrato
    slippage_ticks: int = 1           # en salidas a mercado (límite de pérdida / cierre)


@dataclass
class Trade:
    side: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None = None
    fills: list = field(default_factory=list)   # [(precio, qty)]
    target: float = np.nan
    exit_price: float = np.nan
    reason: str = ""
    pnl_usd: float = 0.0
    mae_usd: float = 0.0

    @property
    def qty(self):
        return sum(q for _, q in self.fills)

    @property
    def avg(self):
        return sum(p * q for p, q in self.fills) / self.qty


def _hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def compute_signals(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    d = df.copy()
    d["ema"] = d["close"].ewm(span=p.ema_len, adjust=False).mean()
    slope = d["ema"] - d["ema"].shift(p.slope_n)
    d["trend"] = 0
    d.loc[(d["close"] > d["ema"]) & (slope > 0), "trend"] = 1
    d.loc[(d["close"] < d["ema"]) & (slope < 0), "trend"] = -1

    n = p.pivot_n
    hi, lo = d["high"].values, d["low"].values
    ph = np.full(len(d), np.nan)
    pl = np.full(len(d), np.nan)
    for i in range(n, len(d) - n):
        if hi[i] == hi[i - n:i + n + 1].max():
            ph[i + n] = hi[i]            # conocido en i+n (confirmación)
        if lo[i] == lo[i - n:i + n + 1].min():
            pl[i + n] = lo[i]
    d["last_ph"] = pd.Series(ph, index=d.index).ffill()
    d["last_pl"] = pd.Series(pl, index=d.index).ffill()
    return d


def run(df: pd.DataFrame, p: Params, exec_df: pd.DataFrame | None = None):
    d = compute_signals(df, p)
    idx = d.index
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close"))
    trend, last_ph, last_pl = d["trend"].values, d["last_ph"].values, d["last_pl"].values
    if exec_df is not None:
        # mapea cada sub-vela a la vela de señal que la contiene
        pos = idx.searchsorted(exec_df.index, side="right") - 1
        groups = {}
        for j, k in enumerate(pos):
            if k >= 0:
                groups.setdefault(k, []).append(j)
        eo, eh, el, ec = (exec_df[k].values for k in ("open", "high", "low", "close"))
        etimes = exec_df.index
        bar_dur = idx[1] - idx[0] if len(idx) > 1 else pd.Timedelta(minutes=30)

    s_start, s_end, s_flat = _hhmm(p.session_start), _hhmm(p.session_end), _hhmm(p.flat_time)
    pv, slip = p.point_value, p.slippage_ticks * p.tick

    bull_fvgs, bear_fvgs = [], []   # [creado_idx, bottom, top, usado]
    trades: list[Trade] = []
    pending = None                  # dict(side, price, target, fvg)
    trade: Trade | None = None
    day = None
    realized_day = 0.0
    trades_day = 0
    stopped_day = False

    def allowance():
        return p.daily_loss_usd + min(0.0, realized_day)

    def close_trade(t, price, when, reason):
        nonlocal trade, realized_day, stopped_day
        t.exit_price, t.exit_time, t.reason = price, when, reason
        gross = sum((price - fp) * fq * t.side for fp, fq in t.fills) * pv
        t.pnl_usd = gross - p.commission_rt * t.qty
        realized_day += t.pnl_usd
        trades.append(t)
        trade = None
        if reason == "daily_loss" or realized_day <= -p.daily_loss_usd:
            stopped_day = True

    def process_subbar(t_now, bo, bh, bl, bc, minute):
        """Gestiona orden pendiente / posición sobre una (sub)vela."""
        nonlocal pending, trade, trades_day
        if pending is not None and trade is None:
            side, price = pending["side"], pending["price"]
            # el objetivo se alcanzó antes de llenar -> setup inválido
            if (side == 1 and bh >= pending["target"]) or (side == -1 and bl <= pending["target"]):
                if not ((side == 1 and bl <= price) or (side == -1 and bh >= price)):
                    pending = None
            if pending is not None:
                hit = bl <= price if side == 1 else bh >= price
                if hit:
                    fill = min(bo, price) if side == 1 else max(bo, price)
                    trade = Trade(side=side, entry_time=t_now, fills=[(fill, p.qty)],
                                  target=pending["target"])
                    trade.fill_bar = t_now
                    pending["fvg"][3] = True
                    pending = None
                    trades_day += 1
        if trade is None:
            return
        side = trade.side
        # promediadas
        while len(trade.fills) - 1 < p.max_adds:
            nxt = trade.fills[0][0] - side * p.add_step_pts * (len(trade.fills))
            if (side == 1 and bl <= nxt) or (side == -1 and bh >= nxt):
                trade.fills.append((nxt, p.add_qty))
            else:
                break
        # límite de pérdida sobre el flotante (peor precio de la vela primero)
        worst = bl if side == 1 else bh
        float_worst = sum((worst - fp) * fq * side for fp, fq in trade.fills) * pv
        trade.mae_usd = min(trade.mae_usd, float_worst)
        if float_worst <= -allowance():
            pts = allowance() / (pv * trade.qty)
            exit_px = trade.avg - side * pts
            if (side == 1 and bo < exit_px) or (side == -1 and bo > exit_px):
                exit_px = bo           # gap a través del límite
            close_trade(trade, exit_px - side * slip, t_now, "daily_loss")
            return
        # objetivo (debe atravesarse 1 tick). En la vela del fill no se acepta el
        # objetivo: no sabemos si el máximo/mínimo ocurrió antes del fill.
        if getattr(trade, "fill_bar", None) != t_now and (
                (side == 1 and bh >= trade.target + p.tick) or (side == -1 and bl <= trade.target - p.tick)):
            close_trade(trade, trade.target, t_now, "target")
            return
        if minute >= s_flat:
            close_trade(trade, bc - side * slip, t_now, "flat_eod")

    for i in range(len(d)):
        t = idx[i]
        minute = t.hour * 60 + t.minute
        if t.date() != day:
            if trade is not None:       # no debería ocurrir (flat diario), por seguridad
                close_trade(trade, o[i] - trade.side * slip, t, "flat_eod")
            day, realized_day, trades_day, stopped_day = t.date(), 0.0, 0, False
            pending = None

        # ---- 1) ejecución durante la vela i (con la orden colocada al cierre de i-1)
        if exec_df is not None and i in groups:
            for j in groups[i]:
                et = etimes[j]
                process_subbar(et, eo[j], eh[j], el[j], ec[j], et.hour * 60 + et.minute + 5)
        else:
            process_subbar(t, o[i], h[i], l[i], c[i],
                           minute + int((idx[1] - idx[0]).total_seconds() // 60) if len(idx) > 1 else minute)

        # ---- 2) actualizar imbalances con la vela i cerrada
        if i >= 2:
            if l[i] > h[i - 2]:
                bull_fvgs.append([i, h[i - 2], l[i], False])
            if h[i] < l[i - 2]:
                bear_fvgs.append([i, h[i], l[i - 2], False])
        # FVG tocado o viejo -> fuera
        bull_fvgs = [f for f in bull_fvgs if not f[3] and i - f[0] <= p.fvg_max_age
                     and (f[0] == i or l[i] > f[2])]
        bear_fvgs = [f for f in bear_fvgs if not f[3] and i - f[0] <= p.fvg_max_age
                     and (f[0] == i or h[i] < f[1])]

        # ---- 3) colocar / cancelar orden para la próxima vela
        end_min = minute + 30
        in_session = s_start <= end_min < s_end
        if trade is not None:
            continue
        tr = trend[i]
        if pending is not None and pending["side"] != tr:
            pending = None
        if not in_session or stopped_day or trades_day >= p.max_trades_day or tr == 0:
            pending = None
            continue
        ph, pl = last_ph[i], last_pl[i]
        if np.isnan(ph) or np.isnan(pl):
            continue
        cand = None
        if p.fvg_mode == "none":
            price = c[i]
            tgt = (ph if tr == 1 else pl) if p.target_mode == "swing" else price + tr * p.target_pts
            if (tgt - price) * tr >= p.min_target_pts:
                cand = dict(side=tr, price=_round(price, p.tick), target=tgt, fvg=[i, 0, 0, False])
        elif tr == 1:
            pool = [f for f in bull_fvgs if f[2] < c[i] and (p.fvg_mode == "any" or f[2] < pl)]
            if pool:
                f = max(pool, key=lambda f: f[2])         # el más cercano al precio
                price = f[2] if p.entry == "edge" else (f[1] + f[2]) / 2
                tgt = ph if p.target_mode == "swing" else price + p.target_pts
                if tgt - price >= p.min_target_pts:
                    cand = dict(side=1, price=_round(price, p.tick), target=tgt, fvg=f)
        else:
            pool = [f for f in bear_fvgs if f[1] > c[i] and (p.fvg_mode == "any" or f[1] > ph)]
            if pool:
                f = min(pool, key=lambda f: f[1])
                price = f[1] if p.entry == "edge" else (f[1] + f[2]) / 2
                tgt = pl if p.target_mode == "swing" else price - p.target_pts
                if price - tgt >= p.min_target_pts:
                    cand = dict(side=-1, price=_round(price, p.tick), target=tgt, fvg=f)
        pending = cand

    if trade is not None:
        close_trade(trade, c[-1], idx[-1], "end_data")
    return trades_to_df(trades), d


def _round(x, tick):
    return round(x / tick) * tick


def trades_to_df(trades):
    rows = []
    for t in trades:
        rows.append(dict(side="long" if t.side == 1 else "short", entry_time=t.entry_time,
                         exit_time=t.exit_time, entry_avg=round(t.avg, 2), first_fill=t.fills[0][0],
                         n_fills=len(t.fills), qty=t.qty, target=round(t.target, 2),
                         exit_price=round(t.exit_price, 2), reason=t.reason,
                         pnl_usd=round(t.pnl_usd, 2), mae_usd=round(t.mae_usd, 2)))
    return pd.DataFrame(rows)


def stats(tr: pd.DataFrame, daily_loss: float = 1000.0) -> dict:
    if tr.empty:
        return dict(trades=0)
    pnl = tr["pnl_usd"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    eq = pnl.cumsum()
    dd = (eq - eq.cummax().clip(lower=0)).min()
    daily = tr.groupby(pd.to_datetime(tr["exit_time"]).dt.date)["pnl_usd"].sum()
    return dict(
        trades=len(tr),
        win_rate=round(100 * len(wins) / len(tr), 1),
        net_usd=round(pnl.sum(), 0),
        avg_win=round(wins.mean(), 0) if len(wins) else 0,
        avg_loss=round(losses.mean(), 0) if len(losses) else 0,
        profit_factor=round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else np.inf,
        expectancy=round(pnl.mean(), 1),
        max_dd_usd=round(dd, 0),
        daily_loss_hits=int((tr["reason"] == "daily_loss").sum()),
        days_traded=len(daily),
        green_days_pct=round(100 * (daily > 0).mean(), 1),
        worst_day=round(daily.min(), 0),
        best_day=round(daily.max(), 0),
        long_net=round(pnl[tr["side"] == "long"].sum(), 0),
        short_net=round(pnl[tr["side"] == "short"].sum(), 0),
    )
