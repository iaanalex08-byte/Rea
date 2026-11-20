#!/usr/bin/env python3
"""Qué hace el NQ a partir de las 7:30 CDMX (UTC-6 fija), 2024-2026, velas de 1 minuto.
    python3 backtest/nq_desde_730.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

a = pb.parse_args(["backtest/datos_NQ", "--tf", "1"])
df = pb.load_bars(a.csv, a.input_tz, a.tz, 1, a.nt_tz)
df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]
tm = df.index.hour * 60 + df.index.minute
# verano en NY: 7:30 CDMX = 9:30 ET (apertura); invierno: 7:30 CDMX = 8:30 ET (datos económicos)
rows = []
for d, g in df.groupby(df.index.date):
    t = (g.index.hour * 60 + g.index.minute).to_numpy()
    if t[0] != 0 or (t >= 15 * 60).sum() == 0 or 450 not in t or any(((t >= x) & (t < x + 30)).sum() < 20 for x in range(450, 900, 30)):
        continue
    O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
    px = lambda m: O[np.searchsorted(t, m)]
    s = (t >= 450) & (t < 900)
    hs, ls = H[s], L[s]; ts = t[s]
    summer = g.index[0].tz_convert("America/New_York").utcoffset() == pd.Timedelta(hours=-4)
    r = {"date": d, "verano": summer, "o0": O[0], "p730": px(450), "p800": px(480), "p830": px(510), "p1030": px(630), "p1430": px(870)}
    r["hi_t"] = ts[hs.argmax()]; r["lo_t"] = ts[ls.argmin()]
    orh, orl = H[(t >= 450) & (t < 480)].max(), L[(t >= 450) & (t < 480)].min()
    after = (t >= 480) & (t < 870)
    hb = np.where(H[after] > orh)[0]; lb = np.where(L[after] < orl)[0]
    r["or_rng"] = orh - orl; r["up_first"] = (len(hb) > 0) and (len(lb) == 0 or hb[0] < lb[0])
    r["dn_first"] = (len(lb) > 0) and (len(hb) == 0 or lb[0] < hb[0]); r["both"] = len(hb) > 0 and len(lb) > 0; r["none"] = not len(hb) and not len(lb)
    for a_, b_ in ((450, 480), (480, 510), (510, 540), (540, 600), (600, 660), (660, 720), (720, 780), (780, 840), (840, 900)):
        m = (t >= a_) & (t < b_)
        r[f"rng_{a_}"] = H[m].max() - L[m].min()
    r["day_rng"] = hs.max() - ls.min()
    rows.append(r)
D = pd.DataFrame(rows)
pd.set_option("display.width", 220)
hm = lambda m: f"{m // 60}:{m % 60:02d}"
print(f"{len(D)} días · verano {D.verano.sum()} · invierno {(~D.verano).sum()}")
print("\n1) Volatilidad: rango mediano (pts NQ) por bloque, invierno vs verano")
cols = [c for c in D.columns if c.startswith("rng_")]
tab = pd.DataFrame({hm(int(c[4:])): [D[~D.verano][c].median(), D[D.verano][c].median()] for c in cols}, index=["invierno", "verano"]).round(0)
print(tab.to_string())
print("\n2) ¿A qué hora se hace el máximo / mínimo de la sesión 7:30-15:00? (% de días)")
bins = [450, 480, 510, 540, 600, 660, 720, 780, 840, 900]
lab = [f"{hm(bins[i])}-{hm(bins[i + 1])}" for i in range(len(bins) - 1)]
hi = pd.cut(D.hi_t, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
lo = pd.cut(D.lo_t, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
print(pd.DataFrame({"máximo %": hi.round(1), "mínimo %": lo.round(1), "alguno de los dos %": (hi + lo).round(1)}).T.to_string())
print("\n3) Rango de apertura 7:30-8:00: qué rompe primero hasta las 14:30")
print(f"rompe arriba primero {100 * D.up_first.mean():.1f}% · abajo primero {100 * D.dn_first.mean():.1f}% · rompe ambos {100 * D.both.mean():.1f}% · ninguno {100 * D.none.mean():.1f}% · rango mediano {D.or_rng.median():.0f} pts")
print("\n4) ¿Continúa o se revierte? (% de días con el mismo signo)")
def same(a_, b_, c_, d_):
    x = np.sign(D[b_] - D[a_]); y = np.sign(D[d_] - D[c_]); m = (x != 0) & (y != 0)
    return 100 * (x[m] == y[m]).mean()
for name, args in (("00:00→7:30 vs 7:30→14:30", ("o0", "p730", "p730", "p1430")),
                   ("7:30→8:00 vs 8:00→14:30", ("p730", "p800", "p800", "p1430")),
                   ("7:30→8:30 vs 8:30→14:30", ("p730", "p830", "p830", "p1430")),
                   ("00:00→10:30 vs 10:30→14:30", ("o0", "p1030", "p1030", "p1430"))):
    print(f"  {name}: mismo sentido {same(*args):.1f}%")
for v, nm in ((False, "invierno"), (True, "verano")):
    E = D[D.verano == v]
    x = np.sign(E.p800 - E.p730); y = np.sign(E.p1430 - E.p800); m = (x != 0) & (y != 0)
    print(f"  7:30→8:00 vs 8:00→14:30 en {nm}: {100 * (x[m] == y[m]).mean():.1f}%")
print("\n5) Tamaño del primer movimiento 7:30→8:00 y lo que sigue (pts a favor del primer movimiento hasta 14:30)")
mv = D.p800 - D.p730; nxt = (D.p1430 - D.p800) * np.sign(mv)
q = pd.qcut(mv.abs(), 4)
print(pd.DataFrame({"días": nxt.groupby(q, observed=True).size(), "sigue a favor %": (100 * (nxt > 0).groupby(q, observed=True).mean()).round(1),
                    "pts prom después": nxt.groupby(q, observed=True).mean().round(1)}).to_string())
print("\n6) Por día de la semana: rango 7:30-15:00 mediano")
print(D.groupby(pd.to_datetime(D.date).dt.dayofweek.map(dict(enumerate(["lun", "mar", "mié", "jue", "vie"])))).day_rng.median().round(0).to_string())
