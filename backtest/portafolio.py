#!/usr/bin/env python3
"""Portafolio para retirar: combina las piezas con ventaja y mide semanas y meses positivos (2024-2026).

Piezas (cada una ya probada por separado; todas en micros con comisión $1.24):
  A  NQ 8:30 contra Londres (POC, SL 66.5, 1:1.25) solo si la noche se movió >= 40 pts
  B  NQ 10:30 con tendencia (POC, SL 66.5, 1:1) con "Evitar días malos"
  C  NQ SMC 5 min (barrida + MSS + FVG desde 9:30 ET, R:R >= 1.5)
  D  NQ primer extremo de la noche (SL 40, hasta 16:00 ET)
  E  NQ 9:00 a favor (POC, SL 66.5, 1:2)
  F  NQ 11:00 retroceso 0-30 pts contra la noche, a mercado, SL 80, cierre 14:30
  G  ES 9:00 a favor (POC, SL 13, 1:1.5)
  H  ES 8:30 contra Londres (POC, SL 13, 1:1.25)
Cuenta propia: varias posiciones a la vez están permitidas (cada pieza con sus contratos).

    python3 backtest/portafolio.py
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as cn  # noqa: E402
import poc_1030_inversa as pi  # noqa: E402
import poc_backtest as pb  # noqa: E402
import retroceso_1100 as rf  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

COM = 1.24
OUT = Path("backtest/resultados/portafolio_piezas.csv")


def es_trades(h, sl, rr, judas):
    a = pb.parse_args(["backtest/datos", "--tf", "3"])
    df = pb.load_bars(a.csv, a.input_tz, a.tz, 3, a.nt_tz)
    df = df[(df.index >= pd.Timestamp(cn.T0, tz=a.tz)) & (df.index < pd.Timestamp(cn.T1, tz=a.tz))]
    old = cn._cache.get(3); cn._cache[3] = df
    try:
        dmap = None
        if judas:
            tm = df.index.hour * 60 + df.index.minute
            o0 = df[tm == 0].groupby(df[tm == 0].index.date).open.first()
            lc = df[tm < 360].groupby(df[tm < 360].index.date).close.last()
            dmap = {d: -int(np.sign(lc[d] - o0[d])) for d in o0.index if d in lc.index}
        hh, mm = map(int, h.split(":")); ws = hh * 60 + mm + 12
        t = cn.trades({"tf": 3, "ph": hh, "pm": mm, "dur": 12, "ws": f"{ws // 60:02d}:{ws % 60:02d}", "sl": sl, "rr": rr, "dmap": dmap})
    finally:
        if old is not None:
            cn._cache[3] = old
        else:
            cn._cache.pop(3)
    return t


def piezas():
    if OUT.exists():
        return pd.read_csv(OUT, parse_dates=["fecha"])
    rows = []
    def add(k, fechas, usd):  # noqa: E306
        rows.append(pd.DataFrame({"pieza": k, "fecha": pd.to_datetime(pd.Series(fechas).astype(str)), "usd": np.asarray(usd, float)}))
    nq = rf.bars()
    tm = nq.index.hour * 60 + nq.index.minute
    o00 = nq.groupby(nq.index.date).open.first()
    c829 = nq[tm < 510].groupby(nq[tm < 510].index.date).close.last()
    night = (c829 - o00).abs()
    t = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv")
    a = t[t.est == "A 8:30"]
    a = a[[night.get(pd.Timestamp(d).date(), 0) >= 40 for d in a.date]]
    add("A", a.date, a.pts * 2 - COM)
    b = pd.read_csv("backtest/resultados/mejoras_1030_smc_ops.csv")
    bad = b["Último quiebre de 5 min en contra"].fillna(False).astype(bool) | b["ES diverge (SMT)"].fillna(False).astype(bool)
    b = b[~bad]; add("B", b.date, b.pts * 2 - COM)
    s = sm.run(resample(load("backtest/datos_NQ"), 5), 180, "FVG", False, "nuevo extremo", 1.5, entry_from=570)
    add("C", s.entry_time.dt.date, s.R * s.risk * 2 - COM)
    d = pd.read_csv("backtest/resultados/estrategia_d_ops.csv"); add("D", d.date, d.pts * 2 - COM)
    e = pi.trades("09:00", 66.5, 2.0, "favor"); add("E", e.date, e.pts * 2 - COM)
    f = rf.trades(660, (-30, 0), 80.0, None); add("F", f.date, f.pts * 2 - COM)
    g = es_trades("09:00", 13, 1.5, False); add("G", g.date, g.pts * 5 - COM)
    h = es_trades("08:30", 13, 1.25, True); add("H", h.date, h.pts * 5 - COM)
    P = pd.concat(rows, ignore_index=True)
    P.to_csv(OUT, index=False)
    return P


def metricas(P, w, years=2.85):
    u = P.usd * P.pieza.map(w).fillna(0)
    day = u.groupby(P.fecha).sum()
    alld = pd.bdate_range("2024-01-02", "2026-11-06")
    day = day.reindex(alld, fill_value=0.0)
    wk = day.resample("W-FRI").sum(); mo = day.resample("ME").sum()
    eq = day.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
    y = day.index.year
    return {"neto/año": round(day.sum() / years), "caída máx": round(dd), "peor día": round(day.min()), "peor semana": round(wk.min()),
            "peor mes": round(mo.min()), "semanas +": round(100 * (wk > 0).mean(), 1), "meses +": round(100 * (mo > 0).mean(), 1),
            "meses + 24-25": round(100 * (mo[mo.index.year <= 2025] > 0).mean(), 1), "meses + 2026": round(100 * (mo[mo.index.year == 2026] > 0).mean(), 1),
            "neto 24-25": round(day[y <= 2025].sum()), "neto 2026": round(day[y == 2026].sum()), "neto/caída": round(day.sum() / years / dd, 2) if dd else np.inf}


def main():
    P = piezas()
    pd.set_option("display.width", 250)
    print("Cada pieza sola (1 micro):")
    ind = pd.DataFrame({k: metricas(P, {k: 1}) for k in sorted(P.pieza.unique())}).T
    print(ind.to_string())
    print("\nCorrelación de resultados diarios:")
    piv = P.pivot_table(index="fecha", columns="pieza", values="usd", aggfunc="sum").fillna(0)
    print(piv.corr().round(2).to_string())
    # combinaciones con pesos 0-2 de las piezas que ganan en ambos periodos
    ok = [k for k in ind.index if ind.loc[k, "neto 24-25"] > 0 and ind.loc[k, "neto 2026"] > 0]
    print("\nPiezas que ganan en ambos periodos:", ok)
    res = []
    for ws in itertools.product(*[(0, 1, 2)] * len(ok)):
        if sum(ws) == 0:
            continue
        w = dict(zip(ok, ws)); m = metricas(P, w)
        res.append({"pesos": " ".join(f"{k}{v}" for k, v in w.items() if v), **m})
    R = pd.DataFrame(res)
    R.to_csv("backtest/resultados/portafolio_combos.csv", index=False)
    for lim in (1000, 2000, 3000):
        x = R[R["caída máx"] <= lim].sort_values(["meses +", "neto/caída"], ascending=False).head(6)
        print(f"\nCaída máx <= ${lim}: mejores por % de meses positivos:")
        print(x.to_string(index=False))


if __name__ == "__main__":
    main()
