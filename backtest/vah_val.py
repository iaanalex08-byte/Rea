#!/usr/bin/env python3
"""Backtest de "Sesión CDMX VAH/VAL 07:00 MX".

Réplica del indicador:
- Tendencia: OPEN de la primera vela de 07:00 vs OPEN de la primera vela de 00:00.
- Perfil 07:00-07:30 con N filas; volumen repartido por traslape del rango de cada vela; POC y área de valor (70 %).
- Señal entre 07:30 y 12:00 (una por día): close[1] <= VAH y close > VAH con tendencia alcista (compra);
  close[1] >= VAL y close < VAL con tendencia bajista (venta).
- Entrada al nivel (VAH/VAL) o al cierre de la vela; SL fijo y TP = SL x R:R.
- Se evalúa desde la vela siguiente; si una vela toca SL y TP, se cuenta PERDIDA. Sin resolver al cambiar de día.

    python3 backtest/vah_val.py backtest/datos --tf 5
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402


def args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("datos")
    p.add_argument("--tf", type=int, default=5)
    p.add_argument("--rows", type=int, default=24)
    p.add_argument("--va", type=float, default=70.0)
    p.add_argument("--sig-start", default="07:30")
    p.add_argument("--sig-end", default="12:00")
    p.add_argument("--entry", choices=["nivel", "cierre", "stop", "retroceso"], default="nivel",
                   help="nivel: como el indicador (optimista); cierre: a mercado al cierre de la vela de señal; "
                        "stop: orden stop en el VAH/VAL desde las 7:30 (llena también rupturas falsas); "
                        "retroceso: tras el cierre de ruptura, orden límite en el VAH/VAL")
    p.add_argument("--sl", type=float, default=5.0)
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--qty", type=float, default=1)
    p.add_argument("--point-value", type=float, default=5.0)
    p.add_argument("--commission", type=float, default=1.24)
    p.add_argument("--out", default=None)
    return p.parse_args(argv)


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def rt(x, t=0.25):
    return math.floor(x / t + 0.5) * t


def profile(bh, bl, bv, rows, va_pct):
    hi, lo = max(bh), min(bl)
    step = (hi - lo) / rows
    if step <= 0:
        return None
    vols = [0.0] * rows
    for h, l, v in zip(bh, bl, bv):
        rng = h - l
        for r in range(rows):
            rlo = lo + r * step
            rhi = rlo + step
            share = 0.0
            if rng > 0:
                share = max(0.0, min(h, rhi) - max(l, rlo)) / rng
            elif l >= rlo and (l < rhi or r == rows - 1):
                share = 1.0
            vols[r] += v * share
    idx = vols.index(max(vols))
    target = sum(vols) * va_pct / 100
    loI = hiI = idx
    acc = vols[idx]
    while acc < target and (loI > 0 or hiI < rows - 1):
        up = vols[hiI + 1] if hiI < rows - 1 else -1.0
        dn = vols[loI - 1] if loI > 0 else -1.0
        if up >= dn:
            hiI += 1; acc += up
        else:
            loI -= 1; acc += dn
    return {"poc": lo + (idx + 0.5) * step, "vah": lo + (hiI + 1) * step, "val": lo + loI * step, "hi": hi, "lo": lo}


def run(df, a):
    ss, se = hm(a.sig_start), hm(a.sig_end)
    idx = df.index
    O, H, L, C, V = (df[c].to_numpy(float) for c in ("open", "high", "low", "close", "volume"))
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    day = idx.day.to_numpy()
    trades = []
    cur = None
    for i in range(len(df)):
        if i == 0 or day[i] != day[i - 1]:
            if cur is not None and cur["res"] is None:
                cur["res"] = "SIN RESOLVER"
            cur = None
            mid = None; trend = 0; bh, bl, bv = [], [], []; prof = None; traded = False; win_started = False; pend = None
        if tm[i] < 30 and mid is None:
            mid = O[i]
        in_win = 7 * 60 <= tm[i] < 7 * 60 + 30
        if in_win and not win_started:
            win_started = True
            trend = 0 if mid is None else (1 if O[i] > mid else (-1 if O[i] < mid else 0))
        if in_win:
            bh.append(H[i]); bl.append(L[i]); bv.append(V[i])
        if prof is None and win_started and not in_win and bh:
            prof = profile(bh, bl, bv, a.rows, a.va) or {}
        # resolución (desde la vela siguiente a la entrada)
        if cur is not None and cur["res"] is None and i > cur["i"]:
            up = cur["dir"] == "COMPRA"
            hs = L[i] <= cur["sl"] if up else H[i] >= cur["sl"]
            ht = H[i] >= cur["tp"] if up else L[i] <= cur["tp"]
            if hs or ht:
                cur["res"] = "PERDIDA" if hs else "GANADA"
                cur["exit_time"] = idx[i]
                cur["amb"] = hs and ht
        # entrada con orden stop en el nivel (se llena con cualquier toque más allá del nivel)
        if a.entry == "stop" and prof and not traded and ss <= tm[i] < se:
            hitB = trend == 1 and H[i] > prof["vah"]
            hitS = trend == -1 and L[i] < prof["val"]
            if hitB or hitS:
                traded = True
                d = 1 if hitB else -1
                lvl = prof["vah"] if hitB else prof["val"]
                ep = rt(max(lvl, O[i]) if d == 1 else min(lvl, O[i]))
                cur = {"date": idx[i].date(), "dir": "COMPRA" if d == 1 else "VENTA", "entry_time": idx[i], "i": i,
                       "entry": ep, "sl": rt(ep - d * a.sl), "tp": rt(ep + d * a.sl * a.rr), "res": None,
                       "exit_time": None, "amb": False, "close_vs_level": (C[i] - lvl) * d,
                       "va_width": prof["vah"] - prof["val"], "range": prof["hi"] - prof["lo"]}
                trades.append(cur)
                if (L[i] <= cur["sl"]) if d == 1 else (H[i] >= cur["sl"]):  # SL en la misma vela del llenado
                    cur.update(res="PERDIDA", exit_time=idx[i], amb=True)
        # retroceso: límite en el nivel tras la vela de ruptura
        if a.entry == "retroceso" and pend is not None and cur is None and ss <= tm[i] < se and i > pend["i"]:
            d = pend["d"]
            if (L[i] <= pend["lvl"]) if d == 1 else (H[i] >= pend["lvl"]):
                ep = rt(pend["lvl"])
                cur = {"date": idx[i].date(), "dir": "COMPRA" if d == 1 else "VENTA", "entry_time": idx[i], "i": i,
                       "entry": ep, "sl": rt(ep - d * a.sl), "tp": rt(ep + d * a.sl * a.rr), "res": None,
                       "exit_time": None, "amb": False, "close_vs_level": pend["cvl"],
                       "va_width": prof["vah"] - prof["val"], "range": prof["hi"] - prof["lo"]}
                trades.append(cur)
                pend = None
        # señal
        if a.entry in ("nivel", "cierre", "retroceso") and prof and not traded and ss <= tm[i] < se and i > 0:
            buy = trend == 1 and C[i - 1] <= prof["vah"] and C[i] > prof["vah"]
            sell = trend == -1 and C[i - 1] >= prof["val"] and C[i] < prof["val"]
            if buy or sell:
                traded = True
                if a.entry == "retroceso":
                    lvl = prof["vah"] if buy else prof["val"]
                    pend = {"i": i, "d": 1 if buy else -1, "lvl": lvl, "cvl": (C[i] - lvl) * (1 if buy else -1)}
                elif cur is None or cur["res"] is not None:
                    lvl = prof["vah"] if buy else prof["val"]
                    ep = rt(lvl if a.entry == "nivel" else C[i])
                    d = 1 if buy else -1
                    cur = {"date": idx[i].date(), "dir": "COMPRA" if buy else "VENTA", "entry_time": idx[i], "i": i,
                           "entry": ep, "sl": rt(ep - d * a.sl), "tp": rt(ep + d * a.sl * a.rr), "res": None,
                           "exit_time": None, "amb": False, "close_vs_level": (C[i] - lvl) * d,
                           "va_width": prof["vah"] - prof["val"], "range": prof["hi"] - prof["lo"]}
                    trades.append(cur)
    if cur is not None and cur["res"] is None:
        cur["res"] = "ABIERTA"
    t = pd.DataFrame(trades)
    if t.empty:
        return t
    t["pts"] = np.where(t.res == "GANADA", (t.tp - t.entry).abs(), np.where(t.res == "PERDIDA", -(t.sl - t.entry).abs(), 0.0))
    t["usd"] = t.pts * a.point_value * a.qty - np.where(t.res.isin(["GANADA", "PERDIDA"]), a.commission * a.qty, 0)
    return t


def load(a):
    base = pb.parse_args([a.datos, "--tf", str(a.tf), "--prof-hour", "7", "--prof-dur", "30", "--win-end", a.sig_end])
    df = pb.load_bars([a.datos], base.input_tz, base.tz, a.tf, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=base.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=base.tz))]
    df, _ = pb.filter_days(df, base)
    return df


def summary(t, a):
    c = t.res.value_counts()
    w, l = c.get("GANADA", 0), c.get("PERDIDA", 0)
    return {"ops": len(t), "ganadas": w, "perdidas": l, "sin_resolver": c.get("SIN RESOLVER", 0) + c.get("ABIERTA", 0),
            "winrate": 100 * w / (w + l) if w + l else np.nan, "equilibrio": 100 * a.sl / (a.sl + a.sl * a.rr),
            "neto_pts": t.pts.sum(), "neto_usd_1mes": t.usd.sum(), "ambiguas": int(t.amb.sum())}


def main():
    a = args()
    df = load(a)
    t = run(df, a)
    s = summary(t, a)
    print(s)
    if a.out:
        t.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
