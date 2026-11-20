#!/usr/bin/env python3
"""Rango de acumulación + ruptura + OB/FVG en velas de 1 hora (NQ 2024-2026, hora ET).

  Rango: últimas W velas de 1 h (W = 6, 10, 16, 24) con ancho <= M x ATR14 de 1 h y >= 2 toques de cada lado.
  Ruptura: una vela de 1 h cierra fuera del rango (cualquier hora de 3:00 a 15:00 ET).
  POI: FVG u OB de 1 h a favor en las 6 velas siguientes. Entrada límite en el borde cercano (vigente 12 velas).
  SL: detrás del POI, detrás de la pierna, mitad del rango o fijo 40/60/100 pts.
  TP: 1R-4R o sin TP. Salida: "intradía" (cierre 16:00 ET) o "swing" (hasta 5 días).
  Una posición a la vez. Costo 1.5 pts. Se elige con 2024-25 y se comprueba en 2026.

    python3 backtest/liquidez_rango_1h.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from liquidez_rango import touches  # noqa: E402

COST, BUF = 1.5, 2.0


def fills_for(df, W, M, poi_mode):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tm = (df.index.hour * 60 + df.index.minute).to_numpy()
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    hiW = pd.Series(H).rolling(W).max().shift(1).to_numpy()
    loW = pd.Series(L).rolling(W).min().shift(1).to_numpy()
    fills, state = [], None
    start = int(np.searchsorted(df.index, pd.Timestamp("2024-01-01", tz="America/New_York")))
    for i in range(max(start, W + 20), len(C)):
        if state is not None and state[0] == "pend":
            _, side, edge, far, i0, mid = state
            if i - i0 > 12 or ((C[i - 1] < far - BUF) if side == 1 else (C[i - 1] > far + BUF)):
                state = None
            elif (L[i] <= edge) if side == 1 else (H[i] >= edge):
                j0 = max(0, i0 - 8)
                leg = L[j0:i].min() if side == 1 else H[j0:i].max()
                fills.append((i, side, edge, far, leg, mid)); state = None
            continue
        if state is not None:
            _, side, ib, mid = state
            if i - ib > 6:
                state = None; continue
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
            continue
        if 180 <= tm[i] <= 900:
            hi, lo = hiW[i], loW[i]; w = hi - lo
            if w > 0 and w <= M * atr[i - 1]:
                s = 1 if C[i] > hi else -1 if C[i] < lo else 0
                if s and touches(H, i - W, i, hi - 0.15 * w, True) >= 2 and touches(L, i - W, i, lo + 0.15 * w, False) >= 2:
                    state = ("brk", s, i, (hi + lo) / 2)
    return fills


def evaluate(df, m1, fills, sl_mode, tp_mode, hold):
    """Entrada en la vela de 1 h; la salida se revisa en velas de 1 min (para saber qué tocó primero)."""
    H1, L1, O1 = m1.high.to_numpy(), m1.low.to_numpy(), m1.open.to_numpy()
    t1 = m1.index
    tm1 = (t1.hour * 60 + t1.minute).to_numpy()
    d1 = t1.date
    out, busy = [], None
    for (i, s, edge, far, leg, mid) in fills:
        t0 = df.index[i]
        if busy is not None and t0 < busy:
            continue
        stop = {"POI": far - s * BUF, "pierna": leg - s * BUF, "mitad rango": mid}.get(sl_mode)
        if stop is None:
            stop = edge - s * float(sl_mode)
        risk = (edge - stop) * s
        if risk < 8 or risk > 250:
            continue
        tgt = None if tp_mode == "sin TP" else edge + s * float(tp_mode) * risk
        a = int(np.searchsorted(t1, t0)); b = int(np.searchsorted(t1, t0 + pd.Timedelta(hours=1)))
        j = a
        while j < b and not ((L1[j] <= edge) if s == 1 else (H1[j] >= edge)):
            j += 1
        if j >= b:
            continue
        end = t0 + pd.Timedelta(days=5)
        res = None; k = j
        # en el minuto de entrada solo cuenta el SL
        if (L1[k] <= stop) if s == 1 else (H1[k] >= stop):
            res = -risk
        k += 1
        while res is None and k < len(H1):
            if (hold == "intradía" and (d1[k] != d1[j] or tm1[k] >= 960)) or (hold == "swing" and t1[k] >= end):
                res = (O1[k] - edge) * s; break
            if (L1[k] <= stop) if s == 1 else (H1[k] >= stop):
                res = -risk; break
            if tgt is not None and ((H1[k] >= tgt) if s == 1 else (L1[k] <= tgt)):
                res = (tgt - edge) * s; break
            k += 1
        if res is None:
            continue
        busy = t1[min(k, len(t1) - 1)]
        out.append((t0, res - COST, risk))
    return pd.DataFrame(out, columns=["t", "pts", "risk"])


def main():
    nq = load("backtest/datos_NQ")
    df = resample(nq, 60)
    rows = []
    for W in (6, 10, 16, 24):
        for M in (2.0, 3.0, 4.0, 6.0):
            for poi in ("FVG", "OB", "cualquiera"):
                fl = fills_for(df, W, M, poi)
                if len(fl) < 30:
                    continue
                for slm in ("POI", "pierna", "mitad rango", "40", "60", "100"):
                    for tpm in ("1", "1.5", "2", "3", "4", "sin TP"):
                        for hold in ("intradía", "swing"):
                            t = evaluate(df, nq, fl, slm, tpm, hold)
                            if len(t) < 30:
                                continue
                            R = t.pts / t.risk; y = t.t.dt.year
                            eq = (t.pts * 2).cumsum()
                            rows.append({"W": W, "M": M, "POI": poi, "SL": slm, "TP": tpm, "salida": hold,
                                         "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.pts > 0).mean(), 1),
                                         "SL med": round(t.risk.median()), "R/op": round(R.mean(), 3),
                                         "R/op 24-25": round(R[y <= 2025].mean(), 3), "R/op 2026": round(R[y == 2026].mean(), 3),
                                         "n 2026": int((y == 2026).sum()), "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85),
                                         "peor DD $": round((eq.cummax() - eq).max())})
        print(f"W={W} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R/op 24-25"] > 0) & (T["R/op 2026"] > 0)
    T.to_csv("backtest/resultados/liquidez_rango_1h.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"{len(T)} versiones · robustas: {T.robusta.sum()} ({100 * T.robusta.mean():.1f} %)")
    for col in ("W", "M", "POI", "SL", "TP", "salida"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "acierto": g["acierto %"].mean().round(1),
                                                    "R/op 24-25": g["R/op 24-25"].mean().round(3), "R/op 2026": g["R/op 2026"].mean().round(3)}).to_string())
    top = T[T["ops/año"] >= 15].sort_values("R/op 24-25", ascending=False).head(15)
    print("\nTop 15 elegidas con 2024-25 -> 2026:")
    print(top.drop(columns=["robusta"]).to_string(index=False))
    print(f"\nPromedio R/op 2026 de esas 15: {top['R/op 2026'].mean():.3f}; positivas {(top['R/op 2026'] > 0).sum()}/15")


if __name__ == "__main__":
    main()
