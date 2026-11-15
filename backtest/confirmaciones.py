#!/usr/bin/env python3
"""¿Qué confirmaciones ayudan a la estrategia de tendencia del SP500 a las 9:00 y a las 9:12?

Base: dirección = cierre 8:59 vs apertura 00:00 CDMX (>= 20 pts). Entrada a mercado (+1 tick), comisión incluida.
Cada confirmación usa SOLO información anterior a la entrada (velas cerradas antes de la hora).
Para cada una: ops que pasan, R/op si pasa vs si no pasa, y R/op por año (2024, 2025, 2026) de las que pasan.
Robusta = mejora el R/op de la base en los tres años por separado.

    python3 backtest/confirmaciones.py
Salida: backtest/resultados/confirmaciones.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

CONFIGS = {  # nombre: (minuto de entrada, SL ticks, salida)
    "9:00 · SL 60 / TP1 60 / TP2 120": (540, 60, "parcial 1:1 + BE + 2R"),
    "9:12 · SL 60 / TP1 60 / TP2 120": (552, 60, "parcial 1:1 + BE + 2R"),
    "9:12 · SL 45 / TP1 30 / TP2 60": (552, 45, "sl45"),
}
g.SALIDAS["sl45"] = ([(0.5, 30 / 45), (0.5, 60 / 45)], True)


def features(df):
    """Una fila por día y hora de entrada con las confirmaciones (alineadas a la dirección: 1 = a favor)."""
    c5 = df.close.resample("5min").last().dropna()
    e20, e50 = c5.ewm(span=20, adjust=False).mean(), c5.ewm(span=50, adjust=False).mean()
    cierre5 = c5.index + pd.Timedelta(minutes=5)  # una vela de 5 min se conoce al cerrar
    e20.index = e50.index = cierre5
    c5c = c5.copy(); c5c.index = cierre5
    rows = []
    prev_dir = None
    for d, x in df.groupby(df.index.date):
        if x.index[0].dayofweek >= 5:
            continue
        tm = (x.index.hour * 60 + x.index.minute).to_numpy()
        if tm[0] > 5 or (tm < 540).sum() == 0:
            continue
        O, H, L, C, V = (x[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
        mv = C[tm < 540][-1] - O[0]
        s = 1 if mv > 0 else -1
        ny = (tm >= 510) & (tm < 900)
        dir_hoy = np.sign(C[ny][-1] - O[ny][0]) if ny.any() else 0
        for ent in (540, 552):
            if (tm == ent).sum() == 0 or (tm == 510).sum() == 0:
                continue
            pre = tm < ent
            last = C[pre][-1]
            i830 = int(np.flatnonzero(tm == 510)[0])
            tp = (H + L + C) / 3
            vw = (tp[pre] * V[pre]).sum() / max(V[pre].sum(), 1)
            hi, lo = H[pre].max(), L[pre].min()
            pos = (last - lo) / (hi - lo) if hi > lo else 0.5
            t_ent = x.index[tm == ent][0]
            a20, a50, cc = e20.asof(t_ent), e50.asof(t_ent), c5c.asof(t_ent)
            k830 = (tm >= 510) & (tm < 515)
            v12 = (tm >= ent - 12) & pre
            rows.append({
                "fecha": d, "entrada": ent, "s": s, "mv": abs(mv), "año": d.year,
                "NY 8:30 a favor": s * (last - O[i830]) > 0,
                "Vela 5 min de 8:30 a favor": s * (C[k830][-1] - O[k830][0]) > 0,
                "Últimos 12 min a favor": s * (last - O[v12][0]) > 0,
                "Precio del lado del VWAP (desde 00:00)": s * (last - vw) > 0,
                "EMA20 vs EMA50 (5 min) a favor": s * (a20 - a50) > 0,
                "Precio del lado de la EMA20 (5 min)": s * (cc - a20) > 0,
                "Cerca del extremo de la noche (tercio a favor)": (pos if s == 1 else 1 - pos) >= 2 / 3,
                "Retroceso: tercio en contra del rango": (pos if s == 1 else 1 - pos) <= 1 / 3,
                "Día anterior en la misma dirección": prev_dir is not None and prev_dir == s,
                "Noche 20-50 pts": abs(mv) < 50,
                "Noche >= 50 pts": abs(mv) >= 50,
                "Lunes-jueves (sin viernes)": x.index[0].dayofweek < 4,
            })
        prev_dir = dir_hoy
    return pd.DataFrame(rows)


def main():
    df = bars("backtest/datos")
    F = features(df)
    days = {d[0]: d for d in g.prep(df)}
    out = []
    for nom, (ent, sl, sal) in CONFIGS.items():
        R = {}
        for d in F.fecha[F.entrada == ent]:
            t = g.run([days[d]], sl, sal, ent, 20)
            if len(t):
                R[d] = float(t.R.iloc[0])
        X = F[(F.entrada == ent) & F.fecha.isin(R)].copy()
        X["R"] = X.fecha.map(R)
        base = X.R.mean(); by = X.groupby("año").R.mean()
        out.append({"config": nom, "confirmación": "BASE (sin confirmación)", "ops": len(X), "% días": 100.0,
                    "R/op si pasa": base, "R/op si NO pasa": np.nan, "R total si pasa": X.R.sum(),
                    "2024": by.get(2024), "2025": by.get(2025), "2026": by.get(2026),
                    "% positivas": (X.R > 0).mean() * 100, "caída R": dd(X.R), "robusta": None})
        cols = [c for c in X.columns if c not in ("fecha", "entrada", "s", "mv", "año", "R")]
        pares = [(c, X[c]) for c in cols]
        pares += [("NY 8:30 a favor + VWAP", X["NY 8:30 a favor"] & X["Precio del lado del VWAP (desde 00:00)"]),
                  ("NY 8:30 a favor + EMA20>EMA50", X["NY 8:30 a favor"] & X["EMA20 vs EMA50 (5 min) a favor"]),
                  ("VWAP + EMA20>EMA50", X["Precio del lado del VWAP (desde 00:00)"] & X["EMA20 vs EMA50 (5 min) a favor"]),
                  ("NY 8:30 + VWAP + EMA20>EMA50", X["NY 8:30 a favor"] & X["Precio del lado del VWAP (desde 00:00)"] & X["EMA20 vs EMA50 (5 min) a favor"])]
        for nm, m in pares:
            m = m.astype(bool)
            if m.sum() < 30:
                continue
            Y = X[m]; yb = Y.groupby("año").R.mean()
            rob = all(yb.get(a, -9) > by.get(a, 9) for a in (2024, 2025, 2026))
            out.append({"config": nom, "confirmación": nm, "ops": int(m.sum()), "% días": m.mean() * 100,
                        "R/op si pasa": Y.R.mean(), "R/op si NO pasa": X.R[~m].mean(), "R total si pasa": Y.R.sum(),
                        "2024": yb.get(2024), "2025": yb.get(2025), "2026": yb.get(2026),
                        "% positivas": (Y.R > 0).mean() * 100, "caída R": dd(Y.R), "robusta": rob})
    T = pd.DataFrame(out)
    T.to_csv("backtest/resultados/confirmaciones.csv", index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 48)
    for nom, x in T.groupby("config", sort=False):
        print("\n==", nom)
        print(x.drop(columns="config").round(3).to_string(index=False))


def dd(r):
    eq = r.cumsum()
    return float((eq.cummax().clip(lower=0) - eq).max())


if __name__ == "__main__":
    main()
