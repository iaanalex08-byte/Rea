#!/usr/bin/env python3
"""Búsqueda de mezclas con validación fuera de muestra (walk-forward). NQ/ES 2024-2026, micros con comisión.

1. Biblioteca de variantes (cada una = lista de operaciones en $ con 1 micro):
   POC NQ: 7:30 a 11:00 x {a favor, dirección invertida, fade, contra Londres} x SL {45, 66.5, 90} x R:R {1, 1.5, 2},
           cada una con y sin filtro "noche >= 40 pts".
   SMC NQ: TP {nuevo extremo con R:R mín. 1 / 1.5 / 2, 1.5R, 2R, 3R} x POI {FVG, FVG u OB} x entradas {desde 9:30 ET, todo el día}.
   Retroceso a mercado: 10:00 / 10:30 / 11:00 x banda {0-30, 0-50} x SL {80, 120}.
   Más las piezas ya armadas: 10:30 con "Evitar días malos", primer extremo de la noche, ES 9:00, ES 8:30.
2. Se ELIGE la mezcla solo con un periodo (entrenamiento) y se MIDE en otro que no se usó (prueba):
     Prueba A: elegir con 2024-2025, medir en 2026.   Prueba B: elegir con 2025-2026, medir en 2024.
   Elección: se agregan piezas una a una (máx. 6) mientras suba la razón ganancia/variación mensual,
   con caída máxima <= $2,000 en el entrenamiento.
3. Se compara contra el plan actual (8:30 + 10:30 + SMC) en el mismo periodo de prueba.

    python3 backtest/busqueda_total.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as cn  # noqa: E402
import poc_backtest as pb  # noqa: E402
import retroceso_1100 as rf  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

COM = 1.24
LIB = Path("backtest/resultados/biblioteca_variantes.csv")
DAYS = pd.bdate_range("2024-01-02", "2026-11-06")
MODOS = {"a favor": "no", "invertida": "dir", "fade": "fade", "contra Londres": "no"}


def night_moves():
    nq = rf.bars()
    tm = nq.index.hour * 60 + nq.index.minute
    o00 = nq.groupby(nq.index.date).open.first()
    c829 = nq[tm < 510].groupby(nq[tm < 510].index.date).close.last()
    lc = nq[tm < 360].groupby(nq[tm < 360].index.date).close.last()
    judas = {d: -int(np.sign(lc[d] - o00[d])) for d in o00.index if d in lc.index}
    return (c829 - o00).abs(), judas


def poc(h, sl, rr, modo, judas):
    hh, mm = map(int, h.split(":")); ws = hh * 60 + mm + 12
    orig = pb.parse_args
    def patched(argv):  # noqa: E306
        a = orig(argv); a.contra = MODOS[modo]; return a
    pb.parse_args = patched
    try:
        return cn.trades({"tf": 3, "ph": hh, "pm": mm, "dur": 12, "ws": f"{ws // 60:02d}:{ws % 60:02d}", "sl": sl, "rr": rr,
                          "dmap": judas if modo == "contra Londres" else None})
    finally:
        pb.parse_args = orig


def biblioteca():
    if LIB.exists():
        return pd.read_csv(LIB, parse_dates=["fecha"])
    rows = []
    def add(k, fechas, usd):  # noqa: E306
        rows.append(pd.DataFrame({"pieza": k, "fecha": pd.to_datetime(pd.Series(list(fechas)).astype(str)), "usd": np.asarray(usd, float)}))
    night, judas = night_moves()
    for h in ("07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00"):
        for modo in MODOS:
            for sl in (45, 66.5, 90):
                for rr in (1.0, 1.5, 2.0):
                    t = poc(h, sl, rr, modo, judas)
                    if t.empty:
                        continue
                    k = f"POC {h} {modo} SL{sl:g} 1:{rr:g}"
                    add(k, t.date, t.pts * 2 - COM)
                    keep = np.array([night.get(d, 0) >= 40 for d in t.date])
                    if keep.sum() > 30:
                        add(k + " noche>=40", t.date[keep], t.pts[keep] * 2 - COM)
        print("POC", h, "listo", file=sys.stderr, flush=True)
    m5 = resample(load("backtest/datos_NQ"), 5)
    for poi in ("FVG", "FVG u OB"):
        for ef, efn in ((570, "NY"), (0, "todo el día")):
            for tp, mr in (("nuevo extremo", 1.0), ("nuevo extremo", 1.5), ("nuevo extremo", 2.0), ("1.5", 0), ("2", 0), ("3", 0)):
                s = sm.run(m5, 180, poi, False, tp, mr, entry_from=ef)
                k = f"SMC {poi} {efn} TP {tp}" + (f" mín {mr:g}R" if tp == "nuevo extremo" else "R")
                add(k, s.entry_time.dt.date, s.R * s.risk * 2 - COM)
    print("SMC listo", file=sys.stderr, flush=True)
    for hora in (600, 630, 660):
        for banda in ((-30, 0), (-50, 0)):
            for sl in (80.0, 120.0):
                t = rf.trades(hora, banda, sl, None)
                add(f"Retroceso {hora // 60}:{hora % 60:02d} 0-{-banda[0]} SL{sl:g}", t.date, t.pts * 2 - COM)
    old = pd.read_csv("backtest/resultados/portafolio_piezas.csv", parse_dates=["fecha"])
    for k, nm in (("B", "10:30 con tendencia + Evitar días malos"), ("D", "Primer extremo de la noche"), ("G", "ES POC 9:00 a favor"), ("H", "ES POC 8:30 contra Londres")):
        x = old[old.pieza == k]; add(nm, x.fecha, x.usd)
    L = pd.concat(rows, ignore_index=True)
    L.to_csv(LIB, index=False)
    return L


def daily(L, names):
    x = L[L.pieza.isin(names)]
    return x.groupby("fecha").usd.sum().reindex(DAYS, fill_value=0.0)


def metr(d):
    mo = d.resample("ME").sum(); wk = d.resample("W-FRI").sum(); eq = d.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    yrs = len(d) / 252
    return {"neto/año": round(d.sum() / yrs), "caída": round(dd), "meses +": f"{(mo > 0).sum()}/{len(mo)}",
            "% meses +": round(100 * (mo > 0).mean(), 1), "% semanas +": round(100 * (wk > 0).mean(), 1), "peor mes": round(mo.min()),
            "razón mensual": round(mo.mean() / mo.std(), 2) if mo.std() > 0 else 0}


def score(d):
    mo = d.resample("ME").sum(); eq = d.cumsum()
    if (eq.cummax().clip(lower=0) - eq).max() > 2000 or mo.std() == 0:
        return -9
    return mo.mean() / mo.std()


def elegir(L, train):
    D = {k: g.groupby("fecha").usd.sum().reindex(DAYS, fill_value=0.0) for k, g in L.groupby("pieza")}
    cand = [k for k, d in D.items() if d[train].sum() > 0 and (L[(L.pieza == k)].fecha.isin(DAYS[train])).sum() >= 40]
    sel, cur, best = [], pd.Series(0.0, index=DAYS), -9
    for _ in range(6):
        top = None
        for k in cand:
            if k in sel:
                continue
            s = score((cur + D[k])[train])
            if s > best + 0.02:
                best, top = s, k
        if top is None:
            break
        sel.append(top); cur = cur + D[top]
    return sel, cand


def main():
    L = biblioteca()
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
    print(f"Biblioteca: {L.pieza.nunique()} variantes")
    base = ["POC 08:30 contra Londres SL66.5 1:1.25 noche>=40"]
    # el plan actual: A (8:30 contra Londres 1:1.25 no está en la rejilla de R:R), así que se toma de las piezas armadas
    old = pd.read_csv("backtest/resultados/portafolio_piezas.csv", parse_dates=["fecha"])
    plan = old[old.pieza.isin(["A", "B", "C"])].groupby("fecha").usd.sum().reindex(DAYS, fill_value=0.0)
    y = DAYS.year
    folds = {"Prueba A: elegir con 2024-25, medir en 2026": (y <= 2025, y == 2026),
             "Prueba B: elegir con 2025-26, medir en 2024": (y >= 2025, y == 2024)}
    out = []
    for nm, (tr, te) in folds.items():
        sel, cand = elegir(L, tr)
        d = daily(L, sel)
        print(f"\n{nm}  ({len(cand)} variantes ganadoras en el entrenamiento)")
        for k in sel:
            print("   +", k)
        out.append({"prueba": nm, "mezcla": "elegida", "periodo": "entrenamiento", **metr(d[tr])})
        out.append({"prueba": nm, "mezcla": "elegida", "periodo": "PRUEBA", **metr(d[te])})
        out.append({"prueba": nm, "mezcla": "plan actual 8:30+10:30+SMC", "periodo": "PRUEBA", **metr(plan[te])})
    print()
    print(pd.DataFrame(out).to_string(index=False))
    # ¿qué piezas aparecen ganando en ambos periodos de entrenamiento?
    D = {k: g.groupby("fecha").usd.sum().reindex(DAYS, fill_value=0.0) for k, g in L.groupby("pieza")}
    rows = []
    for k, d in D.items():
        r = [d[DAYS.year == yy].sum() for yy in (2024, 2025, 2026)]
        mo = d.resample("ME").sum()
        rows.append({"variante": k, "2024": round(r[0]), "2025": round(r[1]), "2026": round(r[2]), "% meses +": round(100 * (mo > 0).mean(), 1),
                     "razón mensual": round(mo.mean() / mo.std(), 2) if mo.std() else 0})
    V = pd.DataFrame(rows)
    V["gana los 3 años"] = (V[["2024", "2025", "2026"]] > 0).all(axis=1)
    V.to_csv("backtest/resultados/biblioteca_resumen.csv", index=False)
    print(f"\nVariantes que ganan los 3 años: {V['gana los 3 años'].sum()} de {len(V)}")
    print(V[V["gana los 3 años"]].sort_values("razón mensual", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
