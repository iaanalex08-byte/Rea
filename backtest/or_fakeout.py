#!/usr/bin/env python3
"""Ruptura falsa del rango de apertura de NY (NQ, hora ET real, 2024-2026, un trade al día).

Idea sacada de los datos: en ~50 % de los días la primera media hora rompe los dos lados de su rango
y el extremo del día se forma al principio. Reglas (venta; compra = espejo):
  1. Rango de apertura (OR): máximo y mínimo de 9:30 a 9:30+N min ET.
  2. Ruptura falsa: una vela pasa el máximo del OR y CIERRA de regreso dentro del rango.
  3. Entrada al cierre de esa vela, en contra de la ruptura.
  4. SL: 2 pts más allá del extremo de la ruptura. TP: el otro lado del OR, o R:R fijo.
  Entradas hasta las 11:30 ET; cierre 12:00 ET. Filtro opcional: solo a favor de la tendencia 00:00 -> entrada.
Comparación: la ruptura "de verdad" (entrar a favor cuando una vela cierra fuera del OR).

    python3 backtest/or_fakeout.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402

BUF = 2.0


def run(df, orm, mode, tp, filt, df_cdmx_open):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tm = (df.index.hour * 60 + df.index.minute).to_numpy()
    dates = df.index.date
    out = []
    for d, ii in pd.Series(np.arange(len(df))).groupby(dates):
        ii = ii.to_numpy()
        t = tm[ii]
        if d < pd.Timestamp("2024-01-01").date() or 570 not in t:
            continue
        orr = ii[(t >= 570) & (t < 570 + orm)]
        if len(orr) < 2:
            continue
        hi, lo = H[orr].max(), L[orr].min()
        o0 = df_cdmx_open.get(d, np.nan)
        trade = None
        for i in ii[(t >= 570 + orm) & (t < 690)]:
            if mode == "falsa":
                if H[i] > hi and C[i] < hi:
                    trade = (-1, C[i], H[i:i + 1].max() + BUF, i, lo)
                elif L[i] < lo and C[i] > lo:
                    trade = (1, C[i], L[i] - BUF, i, hi)
            elif mode == "falsa al revés":
                # misma señal, pero se entra A FAVOR de la ruptura; el riesgo es la misma distancia, del otro lado
                if H[i] > hi and C[i] < hi:
                    d_ = H[i] + BUF - C[i]
                    trade = (1, C[i], C[i] - d_, i, None)
                elif L[i] < lo and C[i] > lo:
                    d_ = C[i] - (L[i] - BUF)
                    trade = (-1, C[i], C[i] + d_, i, None)
            else:
                if C[i] > hi:
                    trade = (1, C[i], lo - BUF, i, None)
                elif C[i] < lo:
                    trade = (-1, C[i], hi + BUF, i, None)
            if trade:
                if filt and not np.isnan(o0) and np.sign(C[i] - o0) != trade[0]:
                    trade = None
                    continue
                break
        if not trade:
            continue
        side, ent, sl, i0, opp = trade
        risk = (ent - sl) * side
        if risk <= 1:
            continue
        tgt = opp if (tp == "otro lado" and opp is not None) else ent + side * float(tp if tp != "otro lado" else 1) * risk
        rr = (tgt - ent) * side / risk
        if rr <= 0.2:
            continue
        r = None
        k = i0 + 1
        while k < len(C) and dates[k] == d:
            if tm[k] >= 720:
                r = (O[k] - ent) * side / risk; break
            if (L[k] <= sl) if side == 1 else (H[k] >= sl):
                r = -1.0; break
            if (H[k] >= tgt) if side == 1 else (L[k] <= tgt):
                r = rr; break
            k += 1
        if r is None:
            r = (C[k - 1] - ent) * side / risk
        out.append({"date": d, "side": side, "risk": risk, "rr": rr, "R": r - 0.5 / risk,
                    "verano": df.index[i0].utcoffset() == pd.Timedelta(hours=-4)})
    return pd.DataFrame(out)


MODES = sys.argv[1:] or ["falsa", "ruptura", "falsa al revés"]


def main():
    nq1 = load("backtest/datos_NQ")
    cd = nq1.index.tz_convert("Etc/GMT+6")
    mid = nq1[(cd.hour == 0) & (cd.minute == 0)]
    o0 = pd.Series(mid.open.to_numpy(), index=mid.index.tz_convert("Etc/GMT+6").date)
    o0 = o0[~o0.index.duplicated()].to_dict()
    rows = []
    for tf in (1, 5):
        df = resample(nq1, tf)
        for orm in (15, 30):
            for mode in MODES:
                for tp in (("otro lado", "1", "1.5", "2") if mode == "falsa" else ("1", "1.5", "2")):
                    for filt in (False, True):
                        t = run(df, orm, mode, tp, filt, o0)
                        if t.empty:
                            continue
                        y = pd.to_datetime(t.date).dt.year
                        rows.append({"tf": tf, "OR": orm, "tipo": mode, "TP": tp, "filtro tendencia": "sí" if filt else "no",
                                     "ops": len(t), "acierto": round(100 * (t.R > 0).mean(), 1), "RR medio": round(t.rr.median(), 2),
                                     "riesgo med": round(t.risk.median(), 1), "R_IS": round(t.R[y <= 2025].sum(), 1),
                                     "R_OOS": round(t.R[y == 2026].sum(), 1), "R_op": round(t.R.mean(), 3),
                                     "R/op verano": round(t.R[t.verano].mean(), 3), "R/op invierno": round(t.R[~t.verano].mean(), 3)})
        print(f"tf {tf} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/or_fakeout_" + "_".join(m.replace(" ", "") for m in MODES) + ".csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))
    print("\nRobustas (2024-25 y 2026 > 0):", ((T.R_IS > 0) & (T.R_OOS > 0)).sum(), "de", len(T))


if __name__ == "__main__":
    main()
