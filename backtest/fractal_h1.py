#!/usr/bin/env python3
"""Estrategia "fractal H1 + 50 % + FVG/OB/IFVG" en NQ, 2024-2026, hora ET real.

  1-2. En H1: último fractal (último máximo y último mínimo de estructura, 2 velas a cada lado).
  3-4. 50 % del rango: arriba del 50 % solo ventas (premium), abajo solo compras (descuento).
  5.   En la temporalidad de ejecución (30, 15 o 5 min): POI a favor dentro de la zona (premium para ventas):
         FVG  = hueco de 3 velas a favor;  OB = última vela contraria antes de una vela fuerte (>= 1 ATR) a favor;
         IFVG = FVG contrario que el precio invalidó (cierre al otro lado): se usa como zona a favor.
       Entrada: orden límite en el borde del POI cuando el precio regresa.
  6.   Máximos y mínimos: SL más allá del POI (o del extremo del rango H1); TP en el 50 % o en el extremo opuesto.
  Una posición a la vez; cierre a las 16:00 ET; costo 1 pt por operación. Probado todo el día (3:00-15:00 ET)
  y solo NY (9:30-12:00 ET).

    python3 backtest/fractal_h1.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from smc_mss import swings  # noqa: E402

COST, BUF = 1.0, 2.0


def h1_ranges(nq):
    h = resample(nq, 60)
    sh, sl = swings(h.high.to_numpy(), h.low.to_numpy())
    rows, lh, ll = [], np.nan, np.nan
    for i in range(len(h)):
        # el fractal de la vela i-2 se confirma al cerrar la vela i -> válido desde el inicio de la vela i+1
        if i >= 2 and sh[i - 2]:
            lh = h.high.iloc[i - 2]
        if i >= 2 and sl[i - 2]:
            ll = h.low.iloc[i - 2]
        rows.append((h.index[i] + pd.Timedelta(hours=1), lh, ll))
    return pd.DataFrame(rows, columns=["t", "hi", "lo"]).set_index("t")


def run(df, rng, poi_mode, sl_mode, tp_mode, ses):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    r = rng.reindex(idx, method="ffill")
    RH, RL = r.hi.to_numpy(), r.lo.to_numpy()
    t0, t1 = (180, 900) if ses == "todo el día" else (570, 720)
    out = []
    pend = None   # orden límite pendiente: (side, edge, far, created)
    zones = []    # FVG contrarios vivos para IFVG: (side_original, top, bottom, k)
    pos = None
    start = np.searchsorted(idx, pd.Timestamp("2024-01-01", tz="America/New_York"))
    for i in range(max(start, 20), len(C)):
        hi, lo = RH[i], RL[i]
        if np.isnan(hi) or np.isnan(lo) or hi <= lo:
            continue
        mid = (hi + lo) / 2
        # gestionar posición abierta
        if pos is not None:
            s, ent, stop, tgt, d0 = pos
            res = None
            if idx[i].date() != d0 or tm[i] >= 960:
                res = (O[i] - ent) * s
            elif (L[i] <= stop) if s == 1 else (H[i] >= stop):
                res = (stop - ent) * s
            elif (H[i] >= tgt) if s == 1 else (L[i] <= tgt):
                res = (tgt - ent) * s
            if res is not None:
                risk = abs(ent - stop)
                out.append({"date": d0, "R": (res - COST) / risk, "pts": res - COST, "risk": risk})
                pos = None
            continue
        side = -1 if C[i - 1] > mid else 1
        insess = t0 <= tm[i] < t1
        # ¿se llena la orden pendiente?
        if pend is not None:
            s, edge, far, k0 = pend
            if s != side or i - k0 > 24 or not insess:
                pend = None
            elif (C[i - 1] < far - BUF) if s == 1 else (C[i - 1] > far + BUF):
                pend = None
            elif (L[i] <= edge) if s == 1 else (H[i] >= edge):
                stop = far - s * BUF if sl_mode == "POI" else (lo - BUF if s == 1 else hi + BUF)
                tgt = mid if tp_mode == "50 %" else (hi if s == 1 else lo)
                risk = abs(edge - stop)
                if risk > 0 and (tgt - edge) * s >= risk and risk <= 150:
                    pos = (s, edge, stop, tgt, idx[i].date())
                    # vela de entrada: solo cuenta el SL
                    if (L[i] <= stop) if s == 1 else (H[i] >= stop):
                        out.append({"date": idx[i].date(), "R": (-risk - COST) / risk, "pts": -risk - COST, "risk": risk})
                        pos = None
                pend = None
                continue
        if not insess:
            continue
        k = i - 1  # última vela cerrada
        zone_ok = (lambda p: p < mid) if side == 1 else (lambda p: p > mid)
        poi = None
        if poi_mode in ("FVG", "cualquiera"):
            if side == 1 and L[k] > H[k - 2] and zone_ok(H[k - 2]):
                poi = (L[k], H[k - 2])
            if side == -1 and H[k] < L[k - 2] and zone_ok(L[k - 2]):
                poi = (H[k], L[k - 2])
        if poi is None and poi_mode in ("OB", "cualquiera"):
            if (C[k] - O[k]) * side >= atr[k] and (C[k - 1] - O[k - 1]) * side < 0:
                ob = (H[k - 1], L[k - 1]) if side == 1 else (L[k - 1], H[k - 1])
                if zone_ok(ob[0]):
                    poi = ob
        if poi_mode in ("IFVG", "cualquiera"):
            # registrar FVG en contra; si el precio cierra al otro lado, se invierte y sirve a favor
            if side == 1 and H[k] < L[k - 2]:
                zones.append((L[k - 2], H[k], k))  # FVG bajista (top, bottom)
            if side == -1 and L[k] > H[k - 2]:
                zones.append((L[k], H[k - 2], k))  # FVG alcista (top, bottom)
            zones = [z for z in zones if k - z[2] <= 48]
            if poi is None:
                for z in zones[::-1]:
                    top, bot, kz = z
                    if side == 1 and C[k] > top and zone_ok(top):
                        poi = (top, bot); zones.remove(z); break
                    if side == -1 and C[k] < bot and zone_ok(bot):
                        poi = (bot, top); zones.remove(z); break
        if poi is not None:
            pend = (side, poi[0], poi[1], i)
    return pd.DataFrame(out)


def main():
    nq = load("backtest/datos_NQ")
    rng = h1_ranges(nq)
    rows = []
    for tf in (30, 15, 5):
        df = resample(nq, tf)
        for ses in ("todo el día", "NY 9:30-12:00"):
            for poi in ("FVG", "OB", "IFVG", "cualquiera"):
                for slm in ("POI", "extremo H1"):
                    for tpm in ("50 %", "extremo opuesto"):
                        t = run(df, rng, poi, slm, tpm, ses)
                        if len(t) < 30:
                            continue
                        y = pd.to_datetime(t.date).dt.year
                        rows.append({"tf": tf, "sesión": ses, "POI": poi, "SL": slm, "TP": tpm, "ops/año": round(len(t) / 2.85),
                                     "acierto %": round(100 * (t.pts > 0).mean(), 1), "SL med": round(t.risk.median(), 1),
                                     "R/op": round(t.R.mean(), 3), "R 24-25": round(t.R[y <= 2025].sum(), 1),
                                     "R 2026": round(t.R[y == 2026].sum(), 1), "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85)})
        print(f"{tf} min listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/fractal_h1.csv", index=False)
    pd.set_option("display.width", 230)
    g = T.groupby(["tf", "sesión"])
    print(pd.DataFrame({"versiones": g.size(), "robustas": g.robusta.sum(), "R/op prom": g["R/op"].mean().round(3),
                        "acierto prom": g["acierto %"].mean().round(1)}).to_string())
    g = T.groupby(["POI"]); print(); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "R/op prom": g["R/op"].mean().round(3)}).to_string())
    g = T.groupby(["TP"]); print(); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "R/op prom": g["R/op"].mean().round(3)}).to_string())
    print("\nMejores robustas:")
    print(T[T.robusta].sort_values("R/op", ascending=False).head(12).to_string(index=False))
    print(f"\nRobustas: {T.robusta.sum()} de {len(T)}")


if __name__ == "__main__":
    main()
