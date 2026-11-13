#!/usr/bin/env python3
"""Rango de acumulación (liquidez acumulada) -> ruptura con cierre -> retroceso a OB / FVG -> continuación.

Como el dibujo: el precio hace varios toques arriba y abajo en un rango estrecho, rompe un lado con cierre,
retrocede (a veces vuelve a probar el rango) y entra en el OB/FVG que dejó la pierna de ruptura.
  Rango: las últimas W velas (se pueden formar desde las 8:00 ET) con ancho <= M x ATR14 y >= 2 toques de cada lado
         (velas cuyo máximo/mínimo queda en el 15 % superior/inferior, separadas al menos 2 velas).
  Ruptura: cierre fuera del rango entre 9:30 y 11:30 ET. POI en las 12 velas siguientes, a favor de la ruptura.
  Entrada límite en el borde cercano del POI (24 velas, hasta 11:45 ET). SL: detrás del POI, detrás de la pierna,
  en la mitad del rango o fijo 40. TP 1R/2R/3R o cierre 15:00 ET. Máx. 2 al día, una a la vez. Costo 1.5 pts.

    python3 backtest/liquidez_rango.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402

COST, BUF = 1.5, 2.0


def touches(x, i0, i1, thr, up):
    n, last = 0, -9
    for j in range(i0, i1):
        if (x[j] >= thr) if up else (x[j] <= thr):
            if j - last >= 2:
                n += 1
            last = j
    return n


def fills_for(df, W, M, poi_mode):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    hiW = pd.Series(H).rolling(W).max().shift(1).to_numpy()
    loW = pd.Series(L).rolling(W).min().shift(1).to_numpy()
    fills = []
    newd = np.r_[True, dates[1:] != dates[:-1]]
    i = int(np.searchsorted(idx, pd.Timestamp("2024-01-01", tz="America/New_York")))
    nfill, state = 0, None
    while i < len(C):
        if newd[i]:
            nfill, state = 0, None
        t = tm[i]
        if t < 570 or t >= 705 or nfill >= 2 or i - W < 0 or tm[i - W] < 480 or dates[i - W] != dates[i]:
            if t >= 705:
                state = None
            i += 1; continue
        if state is not None and state[0] == "pend":
            _, side, edge, far, i0, mid = state
            if i - i0 > 24 or ((C[i - 1] < far - BUF) if side == 1 else (C[i - 1] > far + BUF)):
                state = None
            elif (L[i] <= edge) if side == 1 else (H[i] >= edge):
                j0 = max(0, i0 - 15)
                leg = L[j0:i].min() if side == 1 else H[j0:i].max()
                fills.append((i, side, edge, far, leg, mid)); nfill += 1; state = None
            i += 1; continue
        if state is not None:
            _, side, ib, mid = state
            if i - ib > 12:
                state = None; i += 1; continue
            k = i - 1; poi = None
            if poi_mode in ("FVG", "cualquiera"):
                if side == 1 and L[k] > H[k - 2]: poi = (L[k], H[k - 2])
                if side == -1 and H[k] < L[k - 2]: poi = (H[k], L[k - 2])
            if poi is None and poi_mode in ("OB", "cualquiera") and (C[k] - O[k]) * side >= atr[k]:
                for q in range(k - 1, k - 6, -1):
                    if (C[q] - O[q]) * side < 0:
                        poi = (H[q], L[q]) if side == 1 else (L[q], H[q]); break
            if poi is not None and abs(poi[0] - poi[1]) > 0.5:
                state = ("pend", side, poi[0], poi[1], i, mid)
            i += 1; continue
        if t < 690:
            hi, lo = hiW[i], loW[i]
            w = hi - lo
            if w > 0 and w <= M * atr[i - 1]:
                s = 1 if C[i] > hi else -1 if C[i] < lo else 0
                if s and touches(H, i - W, i, hi - 0.15 * w, True) >= 2 and touches(L, i - W, i, lo + 0.15 * w, False) >= 2:
                    state = ("brk", s, i, (hi + lo) / 2)
        i += 1
    return fills


def evaluate(df, fills, sl_mode, tp_mode):
    H, L, O = df.high.to_numpy(), df.low.to_numpy(), df.open.to_numpy()
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    out, busy = [], -1
    for (i, s, edge, far, leg, mid) in fills:
        if i <= busy:
            continue
        stop = {"POI": far - s * BUF, "pierna": leg - s * BUF, "mitad rango": mid}.get(sl_mode)
        if stop is None:
            stop = edge - s * float(sl_mode)
        risk = (edge - stop) * s
        if risk < 4 or risk > 120:
            continue
        tgt = None if tp_mode == "cierre" else edge + s * float(tp_mode) * risk
        j, res = i, None
        if (L[i] <= stop) if s == 1 else (H[i] >= stop):
            res = -risk
        else:
            j = i + 1
            while j < len(H):
                if dates[j] != dates[i] or tm[j] >= 900:
                    res = (O[j] - edge) * s; break
                if (L[j] <= stop) if s == 1 else (H[j] >= stop):
                    res = -risk; break
                if tgt is not None and ((H[j] >= tgt) if s == 1 else (L[j] <= tgt)):
                    res = (tgt - edge) * s; break
                j += 1
        if res is None:
            continue
        busy = j
        out.append((idx[i], s, res - COST, risk))
    return pd.DataFrame(out, columns=["t", "side", "pts", "risk"])


def main():
    nq = load("backtest/datos_NQ")
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq, tf)
        for W in (10, 20, 30):
            for M in (2.0, 3.0, 4.0):
                for poi in ("FVG", "OB", "cualquiera"):
                    fl = fills_for(df, W, M, poi)
                    for slm in ("POI", "pierna", "mitad rango", "40"):
                        for tpm in ("1", "2", "3", "cierre"):
                            t = evaluate(df, fl, slm, tpm)
                            if len(t) < 60:
                                continue
                            R = t.pts / t.risk; y = t.t.dt.year
                            eq = (t.pts * 2).cumsum()
                            rows.append({"tf": tf, "velas rango": W, "ancho xATR": M, "POI": poi, "SL": slm, "TP": tpm,
                                         "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.pts > 0).mean(), 1),
                                         "SL med": round(t.risk.median(), 1), "R/op": round(R.mean(), 3),
                                         "R 24-25": round(R[y <= 2025].sum(), 1), "R 2026": round(R[y == 2026].sum(), 1),
                                         "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85), "peor DD $": round((eq.cummax() - eq).max())})
            print(f"{tf} min W={W} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/liquidez_rango.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"{len(T)} versiones · robustas: {T.robusta.sum()}")
    for col in ("tf", "velas rango", "ancho xATR", "POI", "SL", "TP"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "acierto prom": g["acierto %"].mean().round(1),
                                                    "R/op prom": g["R/op"].mean().round(3)}).to_string())
    print("\nMejores robustas (>= 30 ops/año):")
    print(T[T.robusta & (T["ops/año"] >= 30)].sort_values("R/op", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
