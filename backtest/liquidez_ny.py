#!/usr/bin/env python3
"""Liquidez acumulada + ruptura en NY + entrada en OB / FVG (NQ 2024-2026, hora ET real).

  1. Liquidez (nivel que no se ha tocado antes de las 9:30 ET):
       Asia (18:00-00:00), Londres (2:00-5:00), noche completa (18:00-9:30), día anterior (9:30-16:00),
       EQH/EQL = dos máximos (o mínimos) de estructura a <= 5 pts sin romper (se forman también durante NY),
       "cualquiera" = el primero que se rompa.
  2. Ruptura: una vela de ejecución CIERRA más allá del nivel entre 9:30 y 11:30 ET.
  3. Modo "continuación": se busca un FVG o un OB a favor de la ruptura (en las 12 velas siguientes);
     modo "falla": la ruptura regresa (cierre de vuelta dentro en <= 6 velas) y se busca OB/FVG en contra.
  4. Entrada: orden límite en el borde cercano del POI (vigente 24 velas, hasta 11:45 ET).
     SL: detrás del POI, detrás de la pierna (extremo desde la ruptura) o fijo 20 / 40 pts.
     TP: 1R, 2R, 3R o sin TP (cierre a las 15:00 ET). Cierre forzado 15:00 ET.
  Máx. 2 operaciones al día, una a la vez. Costo 1.5 pts. Robusta = gana en 2024-25 y en 2026 con >= 60 ops.

    python3 backtest/liquidez_ny.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402

COST, BUF, TOL = 1.5, 2.0, 5.0
LEVELS = ("Asia", "Londres", "Noche", "Día anterior", "EQH/EQL", "cualquiera")


def session_levels(nq):
    tm = nq.index.hour * 60 + nq.index.minute
    d = nq.index.date
    nxt = (nq.index + pd.Timedelta(days=1)).date
    out = {}

    def grp(mask, key):
        x = nq[mask]
        return x.groupby(key[mask]).agg(h=("high", "max"), l=("low", "min"))
    asia = grp((tm >= 1080), np.array(nxt))
    lon = grp((tm >= 120) & (tm < 300), np.array(d))
    night = grp((tm >= 1080) | (tm < 570), np.where(tm >= 1080, np.array(nxt), np.array(d)))
    rth = grp((tm >= 570) & (tm < 960), np.array(d))
    days = sorted(rth.index)
    prev = {days[i]: (rth.h.iloc[i - 1], rth.l.iloc[i - 1]) for i in range(1, len(days))}
    # máximo / mínimo entre el fin de la sesión y las 9:30 (para saber si ya se tocó)
    pre_after_lon = grp((tm >= 300) & (tm < 570), np.array(d))
    pre_after_asia = grp((tm < 570), np.array(d))
    pre_day = night
    for day in days:
        lv = []
        if day in asia.index and day in pre_after_asia.index:
            h, l = asia.loc[day]; ph, pl = pre_after_asia.loc[day]
            if ph <= h: lv.append(("Asia", h, 1))
            if pl >= l: lv.append(("Asia", l, -1))
        if day in lon.index and day in pre_after_lon.index:
            h, l = lon.loc[day]; ph, pl = pre_after_lon.loc[day]
            if ph <= h: lv.append(("Londres", h, 1))
            if pl >= l: lv.append(("Londres", l, -1))
        if day in night.index:
            h, l = night.loc[day]
            lv.append(("Noche", h, 1)); lv.append(("Noche", l, -1))
        if day in prev and day in pre_day.index:
            h, l = prev[day]; ph, pl = pre_day.loc[day]
            if ph < h: lv.append(("Día anterior", h, 1))
            if pl > l: lv.append(("Día anterior", l, -1))
        out[day] = lv
    return out


def fills_for(df, slv, level, mode, poi_mode):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    fills = []
    starts = np.flatnonzero((tm == 0) | (np.r_[True, dates[1:] != dates[:-1]]))
    bounds = list(starts) + [len(C)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        day = dates[a]
        if day not in slv or pd.Timestamp(day).year < 2024:
            continue
        lv = [[n, p, s, True] for n, p, s in slv[day] if level in (n, "cualquiera") and n != "EQH/EQL"]
        sh = []; sl = []   # swings confirmados para EQH/EQL
        state = None       # ("brk", s, lvl, i_brk) o ("pend", side, edge, far, i0, legext)
        nfill = 0
        for i in range(a + 4, b):
            # swings de la vela i-2 (n=2) para EQH/EQL
            k = i - 2
            if level in ("EQH/EQL", "cualquiera") and k - 2 >= a:
                if H[k] == H[k - 2:k + 3].max():
                    for p, j in sh:
                        if abs(p - H[k]) <= TOL and C[j:i].max() <= max(p, H[k]):
                            lv.append(["EQH/EQL", max(p, H[k]), 1, True]); break
                    sh.append((H[k], k))
                if L[k] == L[k - 2:k + 3].min():
                    for p, j in sl:
                        if abs(p - L[k]) <= TOL and C[j:i].min() >= min(p, L[k]):
                            lv.append(["EQH/EQL", min(p, L[k]), -1, True]); break
                    sl.append((L[k], k))
                sh = sh[-12:]; sl = sl[-12:]
            if tm[i] < 570:
                for x in lv:   # niveles rotos antes de NY ya no cuentan
                    if x[3] and (C[i] > x[1] if x[2] == 1 else C[i] < x[1]):
                        x[3] = False
                continue
            if nfill >= 2 or tm[i] >= 705:
                break
            if state is not None and state[0] == "pend":
                _, side, edge, far, i0 = state
                if i - i0 > 24 or ((C[i - 1] < far - BUF) if side == 1 else (C[i - 1] > far + BUF)):
                    state = None
                elif (L[i] <= edge) if side == 1 else (H[i] >= edge):
                    j0 = max(a, i0 - 15)
                    leg = L[j0:i].min() if side == 1 else H[j0:i].max()
                    fills.append((i, side, edge, far, leg)); nfill += 1; state = None
                    continue
                else:
                    continue
            if state is not None and state[0] == "brk":
                _, s, p, ib = state
                if mode == "continuación":
                    if i - ib > 12:
                        state = None; continue
                    side = s
                else:
                    if i - ib > 6:
                        state = None; continue
                    if not ((C[i - 1] < p) if s == 1 else (C[i - 1] > p)) and state[0] == "brk" and len(state) == 4:
                        continue
                    side = -s
                kk = i - 1
                poi = None
                if poi_mode in ("FVG", "cualquiera") and kk - 2 >= ib - 2:
                    if side == 1 and L[kk] > H[kk - 2]:
                        poi = (L[kk], H[kk - 2])
                    if side == -1 and H[kk] < L[kk - 2]:
                        poi = (H[kk], L[kk - 2])
                if poi is None and poi_mode in ("OB", "cualquiera"):
                    if (C[kk] - O[kk]) * side >= atr[kk]:
                        for q in range(kk - 1, max(a, kk - 6), -1):
                            if (C[q] - O[q]) * side < 0:
                                poi = (H[q], L[q]) if side == 1 else (L[q], H[q]); break
                if poi is not None and abs(poi[0] - poi[1]) > 0.5:
                    state = ("pend", side, poi[0], poi[1], i)
                continue
            if tm[i] >= 690:
                continue
            for x in lv:
                if x[3] and (C[i] > x[1] if x[2] == 1 else C[i] < x[1]):
                    x[3] = False
                    if state is None:
                        state = ("brk", x[2], x[1], i)
    return fills


def evaluate(df, fills, sl_mode, tp_mode):
    H, L, O = df.high.to_numpy(), df.low.to_numpy(), df.open.to_numpy()
    idx = df.index
    tm = (idx.hour * 60 + idx.minute).to_numpy()
    dates = idx.date
    out, busy = [], -1
    for (i, s, edge, far, leg) in fills:
        if i <= busy:
            continue
        stop = {"POI": far - s * BUF, "pierna": leg - s * BUF}.get(sl_mode)
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
    slv = session_levels(nq)
    rows, keep = [], {}
    for tf in (1, 3, 5):
        df = resample(nq, tf)
        for level in LEVELS:
            for mode in ("continuación", "falla"):
                for poi in ("FVG", "OB", "cualquiera"):
                    fl = fills_for(df, slv, level, mode, poi)
                    for slm in ("POI", "pierna", "20", "40"):
                        for tpm in ("1", "2", "3", "cierre"):
                            t = evaluate(df, fl, slm, tpm)
                            if len(t) < 60:
                                continue
                            R = t.pts / t.risk
                            y = t.t.dt.year
                            key = (tf, level, mode, poi, slm, tpm)
                            keep[key] = t
                            rows.append({"tf": tf, "liquidez": level, "modo": mode, "POI": poi, "SL": slm, "TP": tpm,
                                         "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.pts > 0).mean(), 1),
                                         "SL med": round(t.risk.median(), 1), "R/op": round(R.mean(), 3),
                                         "R 24-25": round(R[y <= 2025].sum(), 1), "R 2026": round(R[y == 2026].sum(), 1),
                                         "$ año 1 MNQ": round(t.pts.sum() * 2 / 2.85),
                                         "peor DD $": round(((t.pts * 2).cumsum().cummax() - (t.pts * 2).cumsum()).max())})
            print(f"{tf} min {level} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/liquidez_ny.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"{len(T)} versiones · robustas: {T.robusta.sum()}")
    for col in ("tf", "liquidez", "modo", "POI", "SL", "TP"):
        g = T.groupby(col)
        print(f"\nPor {col}:"); print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(),
                                                    "R/op prom": g["R/op"].mean().round(3)}).to_string())
    print("\nMejores robustas (>= 30 ops/año):")
    print(T[T.robusta & (T["ops/año"] >= 30)].sort_values("R/op", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
