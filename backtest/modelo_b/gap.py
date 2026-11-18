#!/usr/bin/env python3
"""¿Sirve el GAP de apertura como filtro en los modelos con filtros?

GAP = apertura de la sesión regular de hoy (9:30 NY) − cierre de la de ayer (16:00 NY), en puntos de ES.
Rasgos medidos antes de la entrada:
  gap a favor / en contra      el signo del gap respecto a la dirección de la operación
  tamaño                       chico (< 5 pts), mediano (5–15) o grande (> 15)
  gap cerrado                  entre las 9:30 NY y la entrada el precio ya tocó el cierre de ayer
Modelos:
  Modelo B "Más dinero": 10:12 NY, EMA 20 de 3 min, A y C por volumen, sin BOS en contra, VWAP; 30/40/160 sin BE.
  SP500 9:00 CDMX con confirmación: noche 20–50 pts y últimos 12 min a favor; SL 60, TP1 60 + BE, TP2 120 ticks.
    (La apertura de 9:30 NY siempre ocurre antes de las 9:00 CDMX.)
Una mejora cuenta solo si sube el PF en 2024, 2025 y 2026 por separado.

    python3 backtest/modelo_b/gap.py
Salida: backtest/resultados/gap_filtro.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
import confirmaciones as cf  # noqa: E402
import sp500_0912_grid as g  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402
from sp500_0912 import bars  # noqa: E402


def gaps(raw):
    """{fecha NY: (cierre de ayer, apertura de hoy, DataFrame de la sesión de hoy en hora NY)}"""
    x = raw.copy()
    x.index = x.index.tz_convert("America/New_York")
    m = x.index.hour * 60 + x.index.minute
    rth = x[(m >= 570) & (m < 960)]
    ses = [(d, s) for d, s in rth.groupby(rth.index.date) if len(s) >= 200]
    out = {}
    for (d0, s0), (d1, s1) in zip(ses[:-1], ses[1:]):
        out[d1] = (s0.close.values[-1], s1.open.values[0], s1)
    return out


def rasgos(G, fecha, t0_ny, s):
    if fecha not in G:
        return None
    c0, o1, ses = G[fecha]
    gp = o1 - c0
    antes = ses[ses.index < t0_ny]
    cerrado = len(antes) > 0 and antes.low.min() <= c0 <= antes.high.max()
    tam = "chico (< 5 pts)" if abs(gp) < 5 else ("mediano (5–15 pts)" if abs(gp) <= 15 else "grande (> 15 pts)")
    return {"Gap a favor": gp * s > 0, "Gap en contra": gp * s < 0, "Gap " + tam: True,
            "Gap cerrado antes de entrar": cerrado, "Gap sin cerrar": not cerrado,
            "Gap a favor sin cerrar": gp * s > 0 and not cerrado, "Gap en contra ya cerrado": gp * s < 0 and cerrado,
            "Gap a favor mediano o grande": gp * s >= 5}


def met(u, y):
    pf = lambda v: v[v > 0].sum() / -v[v <= 0].sum() if (v <= 0).any() else np.inf
    r = dict(ops=len(u), ganadoras=round((u > 0).mean() * 100, 1), pf=round(pf(u), 2), neto=round(u.sum()))
    for a in ("2024", "2025", "2026"):
        v = u[y == a]
        r[f"pf_{a}"] = round(pf(v), 2) if len(v) else None
    return r


def tabla(nombre, fechas, U, R):
    y = np.array([f[:4] for f in fechas])
    filas = [dict(modelo=nombre, filtro="(sin filtro de gap)", **met(U, y))]
    base = filas[0]
    claves = sorted({k for r in R if r for k in r})
    for c in claves:
        m = np.array([bool(r and r.get(c)) for r in R])
        for etiqueta, mk in ((c, m), ("NO " + c, ~m)):
            if mk.sum() >= 25 and not etiqueta.startswith("NO Gap chico") and not etiqueta.startswith("NO Gap mediano") and not etiqueta.startswith("NO Gap grande"):
                r = met(U[mk], y[mk])
                r["mejora_3_anios"] = all((r[f"pf_{a}"] or 0) > (base[f"pf_{a}"] or 0) for a in ("2024", "2025", "2026"))
                filas.append(dict(modelo=nombre, filtro=etiqueta, **r))
    return filas


def main():
    raw = bars(str(HERE.parent / "datos"))
    G = gaps(raw)
    filas = []
    # Modelo B
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    f = pd.DataFrame([V[d["date"]] for d in F])
    m = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    M = [d for d, x in zip(F, m) if x]
    U = np.array([rf.bracket(d, 30, 40, 160, be=False) for d in M])
    R = []
    for d in M:
        t0 = pd.Timestamp(f"{d['date']} {d['hm'][0]:02d}:{d['hm'][1]:02d}", tz="America/Mexico_City").tz_convert("America/New_York")
        R.append(rasgos(G, pd.Timestamp(d["date"]).date(), t0, d["dir"]))
    filas += tabla("Modelo B Más dinero (2 ES)", [d["date"] for d in M], U, R)
    # SP500 9:00 con confirmación
    Fx = cf.features(raw)
    Fx = Fx[(Fx.entrada == 540) & Fx["Últimos 12 min a favor"] & Fx["Noche 20-50 pts"]]
    days = {x[0]: x for x in g.prep(raw)}
    fechas, U2, R2 = [], [], []
    for r in Fx.itertuples():
        t = g.run([days[r.fecha]], 60, "parcial 1:1 + BE + 2R", 540, 20)
        if not len(t):
            continue
        t0 = pd.Timestamp(f"{r.fecha} 09:00", tz="America/Mexico_City").tz_convert("America/New_York")
        fechas.append(str(r.fecha)); U2.append(float(t.R.iloc[0]) * 150); R2.append(rasgos(G, r.fecha, t0, r.s))
    filas += tabla("SP500 9:00 con confirmación (2 MES)", fechas, np.array(U2), R2)
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/gap_filtro.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
