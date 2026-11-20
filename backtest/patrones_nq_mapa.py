#!/usr/bin/env python3
"""Mapa de ventaja del NQ (CDMX, UTC-6 fija), 2024-2026, velas de 1 min. Sin mirar al futuro.

1. Tendencia: a cada hora t, dirección = precio(t) vs apertura de las 00:00. ¿Sigue en esa dirección?
   Se mide t -> t+60 min y t -> 14:30, en pts y % de días a favor; 2024-25 y 2026 por separado.
2. Horario: rango medio por media hora (dónde se mueve el precio) y a qué hora se forma el máximo / mínimo del día.
3. Velas de 5 min: después de una vela fuerte (cuerpo >= 60 % del rango y >= 1 ATR) a favor o en contra de la
   tendencia del día, ¿qué hacen los siguientes 30 min?
4. Ventanas de entrada: retroceso. Si a la hora t el precio retrocedió contra la tendencia de la noche,
   ¿la tendencia se reanuda hasta las 14:30?

    python3 backtest/patrones_nq_mapa.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

COST = 1.0


def main():
    a = pb.parse_args(["backtest/datos_NQ", "--tf", "1"])
    df = pb.load_bars(a.csv, a.input_tz, a.tz, 1, a.nt_tz)
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]
    df = df[df.index.dayofweek < 5]
    tm = df.index.hour * 60 + df.index.minute
    df = df.assign(tm=tm, d=df.index.date)
    piv = df[df.tm < 900].pivot_table(index="d", columns="tm", values="close")
    opn = df.groupby("d").open.first()
    piv = piv.ffill(axis=1)
    y = pd.Series(pd.to_datetime(piv.index).year, index=piv.index)
    pd.set_option("display.width", 220)

    # 1. tendencia
    rows = []
    for t in range(360, 841, 30):
        if t not in piv or 870 - 1 not in piv:
            continue
        p = piv[t]; dirn = np.sign(p - opn.reindex(piv.index))
        f60 = (piv.get(min(t + 60, 869)) - p) * dirn
        fcl = (piv[869] - p) * dirn
        ok = dirn != 0
        rows.append({"hora": f"{t // 60}:{t % 60:02d}", "+60 min pts": round(f60[ok].mean(), 1), "+60 a favor %": round(100 * (f60[ok] > 0).mean(), 1),
                     "a 14:30 pts": round(fcl[ok].mean(), 1), "a 14:30 a favor %": round(100 * (fcl[ok] > 0).mean(), 1),
                     "a 14:30 24-25": round(fcl[ok & (y <= 2025)].mean(), 1), "a 14:30 2026": round(fcl[ok & (y == 2026)].mean(), 1)})
    print("1. Seguir la tendencia desde las 00:00 (pts NQ por día, sin costo):")
    print(pd.DataFrame(rows).to_string(index=False))

    # 2. horario
    df["hh"] = (df.tm // 30) * 30
    r = df[(df.tm >= 360) & (df.tm < 900)].groupby(["d", "hh"]).agg(h=("high", "max"), l=("low", "min"))
    rng = (r.h - r.l).groupby("hh").mean()
    day = df[(df.tm >= 0) & (df.tm < 900)]
    hi_t = day.loc[day.groupby("d").high.idxmax()].tm
    lo_t = day.loc[day.groupby("d").low.idxmin()].tm
    ext = pd.concat([hi_t, lo_t])
    ext_b = ((ext // 60) * 60).value_counts(normalize=True).sort_index()
    print("\n2. Rango medio por media hora (pts) y % de máximos/mínimos del día (00:00-15:00) por hora:")
    print(pd.DataFrame({"rango medio": rng.round(1)}).rename(index=lambda m: f"{m // 60}:{m % 60:02d}").T.to_string())
    print(pd.DataFrame({"% extremos": (100 * ext_b).round(1)}).rename(index=lambda m: f"{m // 60}:00").T.to_string())

    # 3. velas fuertes de 5 min
    m5 = df.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    m5 = m5[m5.index.dayofweek < 5]
    t5 = m5.index.hour * 60 + m5.index.minute
    tr = np.maximum(m5.high - m5.low, np.maximum(abs(m5.high - m5.close.shift()), abs(m5.low - m5.close.shift())))
    atr = tr.rolling(14).mean().shift()
    body = m5.close - m5.open
    strong = (body.abs() >= 0.6 * (m5.high - m5.low)) & (body.abs() >= atr)
    o00 = opn.reindex(m5.index.date).to_numpy()
    tdir = np.sign(m5.open.to_numpy() - o00)
    fwd = m5.close.shift(-6) - m5.close
    same = m5.index.date == pd.Index(m5.index.date).to_series().shift(-6).to_numpy()
    yy = m5.index.year
    out = []
    for lab, a0, a1 in (("7:30-8:30", 450, 510), ("8:30-10:00", 510, 600), ("10:00-12:00", 600, 720), ("12:00-14:00", 720, 840)):
        w = strong & (t5 >= a0) & (t5 < a1) & same
        for kind, m in (("a favor", np.sign(body) == tdir), ("en contra", np.sign(body) == -tdir)):
            sel = w & m
            f = (fwd * np.sign(body))[sel]
            out.append({"ventana": lab, "vela fuerte": kind, "velas": int(sel.sum()), "30 min sigue (pts)": round(f.mean(), 1),
                        "sigue %": round(100 * (f > 0).mean(), 1), "24-25": round(f[yy[sel] <= 2025].mean(), 1), "2026": round(f[yy[sel] == 2026].mean(), 1)})
    print("\n3. Después de una vela fuerte de 5 min (pts en la dirección de la vela, siguientes 30 min):")
    print(pd.DataFrame(out).to_string(index=False))

    # 4. retroceso contra la tendencia de la noche (00:00-8:30)
    noche = np.sign(piv[509] - opn.reindex(piv.index))
    out = []
    for t in (570, 600, 630, 660, 690, 720):
        back = (piv[t] - piv[509]) * noche  # < 0 = retrocedió contra la noche
        fcl = (piv[869] - piv[t]) * noche
        for lab, m in (("retrocedió > 50 pts", back < -50), ("retrocedió 0-50", (back < 0) & (back >= -50)), ("siguió a favor", back >= 0)):
            sel = m & (noche != 0)
            out.append({"hora": f"{t // 60}:{t % 60:02d}", "desde las 8:30": lab, "días": int(sel.sum()),
                        "a 14:30 a favor de la noche (pts)": round(fcl[sel].mean(), 1), "a favor %": round(100 * (fcl[sel] > 0).mean(), 1),
                        "24-25": round(fcl[sel & (y <= 2025)].mean(), 1), "2026": round(fcl[sel & (y == 2026)].mean(), 1)})
    print("\n4. ¿La tendencia de la noche se reanuda después de un retroceso? (pts hasta 14:30 a favor de la noche):")
    print(pd.DataFrame(out).to_string(index=False))


if __name__ == "__main__":
    main()
