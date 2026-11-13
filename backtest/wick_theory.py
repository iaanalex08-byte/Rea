#!/usr/bin/env python3
"""Teoría de la Mecha (Wick Theory) en NQ, 2024-2026, hora ET real, un trade al día.

  1. Mechas de 30 min (últimas 24 h antes de las 9:30 ET): una mecha cuenta si mide >= 40 % de su vela y
     >= 30 % del rango mediano de 30 min. Nivel = mitad de la mecha.
  2. Equilibrio: mitad del rango (máximo-mínimo) de esas 24 h.
  3. Sesgo a las 9:30: compras si el precio está arriba del equilibrio (y, en la variante con mechas, arriba del
     último nivel de mecha); ventas al revés. Además, la vela de 5 min previa a la entrada debe cerrar del mismo lado
     del equilibrio ("presión").
  4. Entrada (1, 3 o 5 min): barrido de liquidez interna (mecha que pasa el último swing y cierra de regreso) y
     después, en <= 15 velas, una vela de convicción (cuerpo >= 60 % del rango y >= 1 ATR) que cierra más allá del
     máximo/mínimo de la vela del barrido. Entrada al cierre.
  SL: 2 pts más allá del barrido. TP: el siguiente nivel (mecha, equilibrio o extremo del rango) a >= m R, o R:R fijo.
  Entradas 9:30-11:30 ET, cierre 12:00 ET.

    python3 backtest/wick_theory.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from smc_mss import swings  # noqa: E402

BUF, MIN_RISK, MAX_RISK = 2.0, 4.0, 80.0


def context(nq1):
    b30 = resample(nq1, 30)
    med = (b30.high - b30.low).rolling(200, min_periods=50).median()
    ctx = {}
    for d in sorted(set(b30.index.date)):
        t0 = pd.Timestamp(d).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
        w = b30[(b30.index < t0) & (b30.index >= t0 - pd.Timedelta(hours=24))]
        if len(w) < 30:
            continue
        rng = (w.high - w.low).to_numpy(); m = med.loc[w.index].to_numpy()
        top, bot = np.maximum(w.open, w.close).to_numpy(), np.minimum(w.open, w.close).to_numpy()
        up, lo = w.high.to_numpy() - top, bot - w.low.to_numpy()
        lv = []
        for k in range(len(w)):
            if rng[k] > 0 and up[k] >= 0.4 * rng[k] and up[k] >= 0.3 * m[k]:
                lv.append((k, (w.high.iloc[k] + top[k]) / 2))
            if rng[k] > 0 and lo[k] >= 0.4 * rng[k] and lo[k] >= 0.3 * m[k]:
                lv.append((k, (w.low.iloc[k] + bot[k]) / 2))
        hi, low = w.high.max(), w.low.min()
        ctx[d] = {"eq": (hi + low) / 2, "hi": hi, "lo": low, "levels": [x for _, x in lv],
                  "last": lv[-1][1] if lv else np.nan}
    return ctx


def run(df, df5, ctx, use_wick, tp_mode, min_rr):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tm = (df.index.hour * 60 + df.index.minute).to_numpy()
    dates = df.index.date
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    body = C - O
    sh, sl_ = swings(H, L)
    c5 = df5.close
    out = []
    for d, ii in pd.Series(np.arange(len(df))).groupby(dates):
        if d < pd.Timestamp("2024-01-01").date() or d not in ctx:
            continue
        ii = ii.to_numpy(); t = tm[ii]
        if 570 not in t:
            continue
        cx = ctx[d]; p0 = O[ii[t == 570][0]]
        side = 1 if p0 > cx["eq"] else -1
        if use_wick and not np.isnan(cx["last"]) and np.sign(p0 - cx["last"]) != side:
            continue
        last_h = last_l = None; sweep = None; trade = None
        for i in ii[(t >= 540) & (t < 690)]:
            if sh[i - 2]:
                last_h = H[i - 2]
            if sl_[i - 2]:
                last_l = L[i - 2]
            if tm[i] < 570 or last_h is None or last_l is None:
                continue
            if sweep is None:
                if side == 1 and L[i] < last_l and C[i] > last_l:
                    sweep = (i, L[i], H[i])
                elif side == -1 and H[i] > last_h and C[i] < last_h:
                    sweep = (i, H[i], L[i])
                continue
            j, ext, other = sweep
            ext = min(ext, L[i]) if side == 1 else max(ext, H[i]); sweep = (j, ext, other)
            if i - j > 15:
                sweep = None; continue
            conv = body[i] * side > 0 and abs(body[i]) >= 0.6 * (H[i] - L[i]) and abs(body[i]) >= atr[i] and \
                ((C[i] > other) if side == 1 else (C[i] < other))
            if not conv:
                continue
            k5 = c5.index.searchsorted(df.index[i], side="right") - 1
            if k5 < 0 or np.sign(c5.iloc[k5] - cx["eq"]) != side:  # presión de 5 min
                sweep = None; continue
            ent = C[i]; stop = ext - side * BUF; risk = (ent - stop) * side
            if not (MIN_RISK <= risk <= MAX_RISK):
                sweep = None; continue
            if tp_mode == "nivel":
                cands = [x for x in cx["levels"] + [cx["eq"], cx["hi"], cx["lo"]] if (x - ent) * side >= min_rr * risk]
                if not cands:
                    sweep = None; continue
                tgt = min(cands) if side == 1 else max(cands)
            else:
                tgt = ent + side * float(tp_mode) * risk
            trade = (i, side, ent, stop, tgt, risk); break
        if not trade:
            continue
        i0, side, ent, stop, tgt, risk = trade
        r = None; k = i0 + 1
        while k < len(C) and dates[k] == d:
            if tm[k] >= 720:
                r = (O[k] - ent) * side / risk; break
            if (L[k] <= stop) if side == 1 else (H[k] >= stop):
                r = -1.0; break
            if (H[k] >= tgt) if side == 1 else (L[k] <= tgt):
                r = (tgt - ent) * side / risk; break
            k += 1
        if r is None:
            r = (C[k - 1] - ent) * side / risk
        out.append({"date": d, "side": side, "risk": risk, "R": r - 0.5 / risk})
    return pd.DataFrame(out)


def main():
    nq1 = load("backtest/datos_NQ")
    ctx = context(nq1)
    df5 = resample(nq1, 5)
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq1, tf)
        for use_wick in (False, True):
            for tp, m in (("nivel", 1.0), ("nivel", 1.5), ("1", 0), ("1.5", 0), ("2", 0)):
                t = run(df, df5, ctx, use_wick, tp, m)
                if t.empty:
                    continue
                y = pd.to_datetime(t.date).dt.year
                rows.append({"velas": tf, "sesgo": "equilibrio + mecha" if use_wick else "equilibrio", "TP": f"siguiente nivel >= {m:g}R" if tp == "nivel" else f"{tp}R",
                             "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.R > 0).mean(), 1), "SL med": round(t.risk.median(), 1),
                             "R/op": round(t.R.mean(), 3), "R 24-25": round(t.R[y <= 2025].sum(), 1), "R 2026": round(t.R[y == 2026].sum(), 1),
                             "$ año 1 MNQ": round((t.R * t.risk * 2 - 1.24).sum() / 2.85)})
        print(f"{tf} min listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/wick_theory.csv", index=False)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))
    print("\nRobustas (2024-25 y 2026 > 0):", ((T["R 24-25"] > 0) & (T["R 2026"] > 0)).sum(), "de", len(T))


if __name__ == "__main__":
    main()
