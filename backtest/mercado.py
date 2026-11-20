#!/usr/bin/env python3
"""Backtest de "POC Apertura CDMX - Entrada a mercado".

Tendencia = apertura de la 1.ª vela del día vs último cierre antes del perfil.
A la hora de entrada se compra/vende al OPEN de la primera vela >= esa hora (solo si ya terminó el perfil).
SL y TP desde la misma vela de entrada. Si una vela toca SL y TP, se asume SL (conservador) y se cuenta como ambigua.

    python3 backtest/mercado.py backtest/datos --tf 1
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
    p.add_argument("--tf", type=int, default=1)
    p.add_argument("--prof", default="07:00")
    p.add_argument("--prof-dur", type=int, default=30)
    p.add_argument("--entry", default="08:30")
    p.add_argument("--sl", type=float, default=9.0)
    p.add_argument("--rr", type=float, default=0.32)
    p.add_argument("--tick", type=float, default=0.25)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2026-11-04")
    p.add_argument("--qty", type=float, default=2)
    p.add_argument("--point-value", type=float, default=50.0)
    p.add_argument("--commission", type=float, default=0.0, help="$ ida y vuelta por contrato")
    p.add_argument("--out", default=None)
    return p.parse_args(argv)


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def rt(x, t):
    return math.floor(x / t + 0.5) * t


def run(df, a):
    pS, pE, eS = hm(a.prof), hm(a.prof) + a.prof_dur, hm(a.entry)
    idx = df.index
    O, H, L, C = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    day = idx.day.to_numpy()
    out = []
    cur = None
    for i in range(len(df)):
        if i == 0 or day[i] != day[i - 1]:
            if cur is not None and cur["res"] is None:
                cur["res"] = "SIN RESOLVER"
            tOpen, tClose, prof_done, dirT, cur = O[i], C[i], False, 0, None
            had_prof = False
        if tm[i] < pS:
            tClose = C[i]
        if pS <= tm[i] < pE:
            had_prof = True
        if not prof_done and had_prof and tm[i] >= pE:
            prof_done = True
            dirT = 1 if tClose > tOpen else (-1 if tClose < tOpen else 0)
        if cur is None and prof_done and dirT != 0 and tm[i] >= eS:
            e = rt(O[i], a.tick)
            sl = rt(e - dirT * a.sl, a.tick)
            tp = rt(e + dirT * a.sl * a.rr, a.tick)
            cur = {"date": idx[i].date(), "dir": "COMPRA" if dirT == 1 else "VENTA", "entry_time": idx[i],
                   "entry": e, "sl": sl, "tp": tp, "res": None, "exit_time": None, "ambigua": False,
                   "mae": 0.0}
            out.append(cur)
        if cur is not None and cur["res"] is None:
            up = cur["dir"] == "COMPRA"
            slHit = L[i] <= cur["sl"] if up else H[i] >= cur["sl"]
            tpHit = H[i] >= cur["tp"] if up else L[i] <= cur["tp"]
            adv = (cur["entry"] - L[i]) if up else (H[i] - cur["entry"])
            if slHit and tpHit:
                cur.update(res="PERDIDA", exit_time=idx[i], ambigua=True)
            elif slHit:
                cur.update(res="PERDIDA", exit_time=idx[i])
            elif tpHit:
                cur.update(res="GANADA", exit_time=idx[i])
                cur["mae"] = max(cur["mae"], min(adv, a.sl))
            else:
                cur["mae"] = max(cur["mae"], adv)
    if cur is not None and cur["res"] is None:
        cur["res"] = "ABIERTA"
    tr = pd.DataFrame(out)
    tr["pts"] = np.where(tr.res == "GANADA", (tr.tp - tr.entry).abs(),
                         np.where(tr.res == "PERDIDA", -(tr.sl - tr.entry).abs(), 0.0))
    tr["usd"] = tr.pts * a.point_value * a.qty - np.where(tr.res.isin(["GANADA", "PERDIDA"]), a.commission * a.qty, 0)
    return tr


def streaks(res):
    """Rachas de días ganados entre pérdidas."""
    s, cur = [], 0
    for r in res:
        if r == "GANADA":
            cur += 1
        elif r == "PERDIDA":
            s.append(cur); cur = 0
    s.append(cur)
    return s


def main():
    a = args()
    base = pb.parse_args([a.datos, "--tf", str(a.tf), "--prof-hour", a.prof[:2], "--prof-min", a.prof[3:],
                          "--prof-dur", str(a.prof_dur), "--win-end", "13:30"])
    df = pb.load_bars([a.datos], base.input_tz, base.tz, a.tf, "auto")
    df = df[(df.index >= pd.Timestamp(a.start, tz=base.tz)) & (df.index < pd.Timestamp(a.end, tz=base.tz) + pd.Timedelta(days=1))]
    df, _ = pb.filter_days(df, base)
    tr = run(df, a)
    c = tr.res.value_counts()
    w, l = c.get("GANADA", 0), c.get("PERDIDA", 0)
    amb = int(tr.ambigua.sum())
    tp_pts = (tr.tp - tr.entry).abs().median()
    print(f"Velas de {a.tf} min | perfil {a.prof}+{a.prof_dur} | entrada {a.entry} | SL {a.sl} pts | TP {tp_pts:g} pts | "
          f"{a.qty:g} contratos × ${a.point_value:g}/pt")
    print(f"Días operados: {len(tr)}  Ganadas: {w}  Perdidas: {l} (de ellas {amb} ambiguas: SL y TP en la misma vela)  "
          f"Sin resolver: {c.get('SIN RESOLVER', 0) + c.get('ABIERTA', 0)}")
    print(f"% acierto: {100 * w / (w + l):.1f}%  (punto de equilibrio: {100 * a.sl / (a.sl + tp_pts):.1f}%)")
    print(f"Neto: {tr.pts.sum():+.2f} pts = ${tr.usd.sum():,.0f}")
    y = pd.to_datetime(tr.date).dt.year
    for yy, g in tr.groupby(y):
        cc = g.res.value_counts()
        print(f"  {yy}: {len(g)} días, {cc.get('GANADA', 0)} ganadas, {cc.get('PERDIDA', 0)} perdidas, "
              f"acierto {100 * cc.get('GANADA', 0) / max(1, cc.get('GANADA', 0) + cc.get('PERDIDA', 0)):.1f}%, ${g.usd.sum():,.0f}")
    s = streaks(tr.res.tolist())
    print(f"Rachas de días ganados entre pérdidas: mediana {np.median(s):.0f}, promedio {np.mean(s):.1f}, máx {max(s)}")
    res = tr.res.tolist()
    starts = [k for k in range(len(res) - 4)]
    ok5 = sum(all(r == "GANADA" for r in res[k:k + 5]) for k in starts)
    print(f"Si empiezas cualquier día: 5 días seguidos ganados en {100 * ok5 / len(starts):.1f}% de los casos "
          f"(con acierto p, en teoría p^5 = {100 * (w / (w + l)) ** 5:.1f}%)")
    if a.out:
        tr.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
