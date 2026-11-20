#!/usr/bin/env python3
"""Todas las variantes con entrada a las 7:30 CDMX (UTC-6 fija) en NQ, 2024-2026.
Ojo: 7:30 CDMX = 9:30 NY en verano (apertura) y 8:30 NY en invierno (datos económicos).

Tipos de entrada:
  "mercado": a las 7:30, con la dirección de una regla.
  "ruptura del rango 7:30-7:45" / "7:30-8:00": se entra al romper el rango (filtro opcional de dirección).
Direcciones: EMA 20/50 15 min · tendencia 00:00 · contra Londres · a favor de Londres · día anterior ·
             tendencia + EMA de acuerdo.
SL fijo (20-150 pts) o el otro lado del rango; TP 1:1, 1:1.5, 1:2, 1:3, 1:4 o cierre 14:30. Costo 2 pts.
"Robusta" = gana en 2024-25, en 2026, en invierno y en verano.

    python3 backtest/entrada_730.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as c  # noqa: E402

COST, T0, TEND = 2.0, 450, 870
df = c.bars(1)
c15 = df.close.resample("15min", label="left", closed="left").last().dropna()
e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
days, prev = [], None
for d, g in df.groupby(df.index.date):
    t = (g.index.hour * 60 + g.index.minute).to_numpy()
    if t[0] != 0 or T0 not in t or (t >= TEND).sum() == 0:
        continue
    O, H, L, C = g.open.values, g.high.values, g.low.values, g.close.values
    i0, i1 = int(np.searchsorted(t, T0)), int(np.searchsorted(t, TEND))
    e = O[i0]; o0 = O[0]; lc = C[int(np.searchsorted(t, 360)) - 1]
    k = c15.index.searchsorted(g.index[i0]) - 1
    ema = 1 if e20.iloc[k] > e50.iloc[k] else -1
    tend = int(np.sign(e - o0))
    dirs = {"EMA 15 min": ema, "tendencia 00:00": tend, "contra Londres": -int(np.sign(lc - o0)),
            "a favor de Londres": int(np.sign(lc - o0)), "día anterior": prev if prev is not None else 0,
            "tendencia + EMA": tend if tend == ema else 0}
    summer = g.index[i0].tz_convert("America/New_York").utcoffset() == pd.Timedelta(hours=-4)
    if d >= pd.Timestamp("2024-01-01").date():
        days.append({"y": d.year, "verano": summer, "dirs": dirs, "O": O[i0:i1], "H": H[i0:i1], "L": L[i0:i1],
                     "exit": O[i1], "e": e, "t": t[i0:i1]})
    rth = (t >= 450) & (t < 900)
    prev = int(np.sign(C[rth][-1] - O[rth][0])) if rth.any() else None


def simulate(s, ent, sl, tp, H, L, ex, k0):
    """Resultado en pts desde la vela k0+1 (la de entrada ya se cuenta si es mercado: k0 = -1)."""
    slp = ent - s * sl
    tpp = None if tp is None else ent + s * tp
    for k in range(k0 + 1, len(H)):
        if (L[k] <= slp) if s == 1 else (H[k] >= slp):
            return -sl
        if tpp is not None and ((H[k] >= tpp) if s == 1 else (L[k] <= tpp)):
            return tp
    return (ex - ent) * s


rows = []


def add(tipo, dname, slname, rrname, res):
    x = pd.DataFrame(res, columns=["y", "verano", "p", "risk"])
    if len(x) < 80:
        return
    rows.append({"tipo": tipo, "dirección": dname, "SL": slname, "TP": rrname, "ops": len(x), "acierto %": round(100 * (x.p > 0).mean(), 1),
                 "pts 24-25": round(x.p[x.y <= 2025].mean(), 1), "pts 2026": round(x.p[x.y == 2026].mean(), 1),
                 "pts invierno": round(x.p[~x.verano].mean(), 1), "pts verano": round(x.p[x.verano].mean(), 1),
                 "R/op": round((x.p / x.risk).mean(), 3), "$ año 1 MNQ": round(x.p.sum() * 2 / 2.85)})


RRS = [1, 1.5, 2, 3, 4, None]
# 1) a mercado a las 7:30
for dname in days[0]["dirs"]:
    for sl in (20, 30, 40, 60, 80, 100, 150):
        for rr in RRS:
            res = []
            for dd in days:
                s = dd["dirs"][dname]
                if s == 0:
                    continue
                p = simulate(s, dd["e"], sl, None if rr is None else rr * sl, dd["H"], dd["L"], dd["exit"], -1)
                res.append((dd["y"], dd["verano"], p - COST, sl))
            add("mercado 7:30", dname, str(sl), f"1:{rr:g}" if rr else "cierre 14:30", res)
# 2) ruptura del rango de apertura
for rmin in (15, 30):
    for filt in ("sin filtro", "tendencia 00:00", "EMA 15 min"):
        for slm in ("otro lado del rango", 40, 60):
            for rr in (1, 2, 3, None):
                res = []
                for dd in days:
                    n = rmin
                    hi, lo = dd["H"][:n].max(), dd["L"][:n].min()
                    trade = None
                    for k in range(n, len(dd["H"])):
                        if dd["t"][k] >= 690:
                            break
                        up, dn = dd["H"][k] > hi, dd["L"][k] < lo
                        if up and dn:
                            break
                        if up or dn:
                            s = 1 if up else -1
                            trade = (k, s, max(hi, dd["O"][k]) if up else min(lo, dd["O"][k])); break
                    if not trade:
                        continue
                    k, s, ent = trade
                    if filt != "sin filtro" and dd["dirs"][filt] != s:
                        continue
                    sl = (hi - lo) + 1 if slm == "otro lado del rango" else slm
                    if sl > 200:
                        continue
                    p = simulate(s, ent, sl, None if rr is None else rr * sl, dd["H"], dd["L"], dd["exit"], k)
                    res.append((dd["y"], dd["verano"], p - COST, sl))
                add(f"ruptura rango 7:30-{7 + (30 + rmin) // 60}:{(30 + rmin) % 60:02d}", filt, str(slm), f"1:{rr}" if rr else "cierre 14:30", res)

T = pd.DataFrame(rows)
T["robusta"] = (T["pts 24-25"] > 0) & (T["pts 2026"] > 0) & (T["pts invierno"] > 0) & (T["pts verano"] > 0)
T.to_csv("backtest/resultados/entrada_730.csv", index=False)
pd.set_option("display.width", 240)
print(f"{len(T)} variantes · robustas (ganan en 24-25, 2026, invierno y verano): {T.robusta.sum()}")
g = T.groupby(["tipo", "dirección"])
print(pd.DataFrame({"variantes": g.size(), "robustas": g.robusta.sum(), "R/op promedio": g["R/op"].mean().round(3)}).to_string())
print("\nMejores robustas (por R/op):")
print(T[T.robusta].sort_values("R/op", ascending=False).head(15).to_string(index=False))
print("\nMejores robustas (por $ al año):")
print(T[T.robusta].sort_values("$ año 1 MNQ", ascending=False).head(10).to_string(index=False))
