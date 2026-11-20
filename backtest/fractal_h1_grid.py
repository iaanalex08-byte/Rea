#!/usr/bin/env python3
"""Fractal H1 + 50 % + FVG/OB/IFVG: búsqueda amplia de temporalidad, dirección, SL y TP.

Dirección: "reversión" (la original: arriba del 50 % ventas) o "tendencia" (al revés: arriba del 50 % compras).
Ejecución: 5, 15, 30, 60 min. POI: FVG, OB, IFVG o cualquiera. Sesión: todo el día (3:00-15:00 ET) o NY (9:30-12:00).
SL: detrás del POI, fijo 20/40/60/100 pts o detrás del extremo del rango H1.
TP: 1R, 2R, 3R, el 50 % / extremo del rango, o sin TP (cierre 16:00 ET).
Una posición a la vez. Costo 1.5 pts. Robusta = gana en 2024-25 y en 2026 con al menos 60 operaciones.

    python3 backtest/fractal_h1_grid.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from fractal_h1 import h1_ranges  # noqa: E402

COST, BUF = 1.5, 2.0


def signals(df, rng, direc, poi_mode, ses):
    """Llenados de órdenes límite en el POI (sin gestionar la salida)."""
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    r = rng.reindex(idx, method="ffill")
    RH, RL = r.hi.to_numpy(), r.lo.to_numpy()
    t0, t1 = (180, 900) if ses == "todo el día" else (570, 720)
    fills, pend, zones = [], None, []
    start = max(20, int(np.searchsorted(idx, pd.Timestamp("2024-01-01", tz="America/New_York"))))
    for i in range(start, len(C)):
        hi, lo = RH[i], RL[i]
        if np.isnan(hi) or np.isnan(lo) or hi <= lo:
            continue
        mid = (hi + lo) / 2
        above = C[i - 1] > mid
        side = (-1 if above else 1) if direc == "reversión" else (1 if above else -1)
        insess = t0 <= tm[i] < t1
        if pend is not None:
            s, edge, far, k0 = pend
            if s != side or i - k0 > 24 or not insess or ((C[i - 1] < far - BUF) if s == 1 else (C[i - 1] > far + BUF)):
                pend = None
            elif (L[i] <= edge) if s == 1 else (H[i] >= edge):
                fills.append((i, s, edge, far, hi, lo, mid)); pend = None
                continue
        if not insess:
            continue
        k = i - 1
        inzone = (lambda p: p < mid) if (side == 1) == (direc == "reversión") else (lambda p: p > mid)
        poi = None
        if poi_mode in ("FVG", "cualquiera"):
            if side == 1 and L[k] > H[k - 2] and inzone(H[k - 2]):
                poi = (L[k], H[k - 2])
            if side == -1 and H[k] < L[k - 2] and inzone(L[k - 2]):
                poi = (H[k], L[k - 2])
        if poi is None and poi_mode in ("OB", "cualquiera"):
            if (C[k] - O[k]) * side >= atr[k] and (C[k - 1] - O[k - 1]) * side < 0:
                ob = (H[k - 1], L[k - 1]) if side == 1 else (L[k - 1], H[k - 1])
                if inzone(ob[0]):
                    poi = ob
        if poi_mode in ("IFVG", "cualquiera"):
            if side == 1 and H[k] < L[k - 2]:
                zones.append((L[k - 2], H[k], k))
            if side == -1 and L[k] > H[k - 2]:
                zones.append((L[k], H[k - 2], k))
            zones = [z for z in zones if k - z[2] <= 48]
            if poi is None:
                for z in zones[::-1]:
                    top, bot, _ = z
                    if side == 1 and C[k] > top and inzone(top):
                        poi = (top, bot); zones.remove(z); break
                    if side == -1 and C[k] < bot and inzone(bot):
                        poi = (bot, top); zones.remove(z); break
        if poi is not None:
            pend = (side, poi[0], poi[1], i)
    return fills


def evaluate(df, fills, sl_mode, tp_mode):
    H, L, O = df.high.to_numpy(), df.low.to_numpy(), df.open.to_numpy()
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    out, busy = [], -1
    for (i, s, edge, far, hi, lo, mid) in fills:
        if i <= busy:
            continue
        stop = {"POI": far - s * BUF, "extremo H1": (lo - BUF) if s == 1 else (hi + BUF)}.get(sl_mode)
        if stop is None:
            stop = edge - s * float(sl_mode)
        risk = (edge - stop) * s
        if risk <= 0.5 or risk > 200:
            continue
        if tp_mode == "50 % / extremo":
            tgt = mid if (mid - edge) * s > 0 else (hi if s == 1 else lo)
        elif tp_mode == "cierre":
            tgt = None
        else:
            tgt = edge + s * float(tp_mode) * risk
        if tgt is not None and (tgt - edge) * s < 0.5 * risk:
            continue
        # buscar salida
        j = i; res = None
        if (L[i] <= stop) if s == 1 else (H[i] >= stop):
            res = -risk
        else:
            j = i + 1
            while j < len(H):
                if dates[j] != dates[i] or tm[j] >= 960:
                    res = (O[j] - edge) * s; break
                if (L[j] <= stop) if s == 1 else (H[j] >= stop):
                    res = -risk; break
                if tgt is not None and ((H[j] >= tgt) if s == 1 else (L[j] <= tgt)):
                    res = (tgt - edge) * s; break
                j += 1
        if res is None:
            continue
        busy = j
        out.append((dates[i].year, res - COST, risk))
    return pd.DataFrame(out, columns=["y", "pts", "risk"])


def main():
    nq = load("backtest/datos_NQ")
    rng = h1_ranges(nq)
    rows = []
    for tf in (5, 15, 30, 60):
        df = resample(nq, tf)
        for direc in ("reversión", "tendencia"):
            for poi in ("FVG", "OB", "IFVG", "cualquiera"):
                for ses in ("todo el día", "NY 9:30-12:00"):
                    fills = signals(df, rng, direc, poi, ses)
                    for slm in ("POI", "20", "40", "60", "100", "extremo H1"):
                        for tpm in ("1", "2", "3", "50 % / extremo", "cierre"):
                            t = evaluate(df, fills, slm, tpm)
                            if len(t) < 60:
                                continue
                            R = t.pts / t.risk
                            rows.append({"tf": tf, "dirección": direc, "POI": poi, "sesión": ses, "SL": slm, "TP": tpm,
                                         "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.pts > 0).mean(), 1),
                                         "R/op": round(R.mean(), 3), "R 24-25": round(R[t.y <= 2025].sum(), 1),
                                         "R 2026": round(R[t.y == 2026].sum(), 1), "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85)})
            print(f"{tf} min {direc} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/fractal_h1_grid.csv", index=False)
    pd.set_option("display.width", 240)
    print(f"{len(T)} versiones · robustas: {T.robusta.sum()}")
    for col in ("tf", "dirección", "POI", "sesión", "SL", "TP"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "R/op prom": g["R/op"].mean().round(3)}).to_string())
    print("\nMejores robustas con >= 40 ops/año:")
    print(T[T.robusta & (T["ops/año"] >= 40)].sort_values("R/op", ascending=False).head(15).to_string(index=False))


if __name__ == "__main__":
    main()
