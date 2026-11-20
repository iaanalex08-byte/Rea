#!/usr/bin/env python3
"""Backtest aproximado del "SS Model" (SMT NQ/ES + vela envolvente), velas de 1 min, hora NY.

Reglas (traducción a reglas fijas de un método visual):
- Niveles: swings (fractal de K velas a cada lado) del activo operado entre 7:00 y la hora límite, no mitigados.
  El nivel del otro activo es su máximo/mínimo en +-2 velas de ese swing.
- SMT (desde 9:36 hasta 10:00 NY): en una vela, un activo supera su nivel y el otro no ha superado el suyo.
  SMT bajista en máximos, alcista en mínimos.
- Entrada: última vela de color contrario del activo operado (antes o en la SMT); se entra al cierre de la
  primera vela que cierra más allá de su apertura. Si antes hace un nuevo extremo, el extremo se actualiza.
- SL: extremo + 10 % de la distancia extremo-entrada. TP: R:R fijo (3 por defecto). Una operación por día.
- Sin días de CPI, PPI ni NFP (opcional). Cierre a las 16:00 NY si no se resolvió.

    python3 backtest/ss_model.py [--operar NQ|ES] [--rr 3] [--k 3] [--entrada-hasta 10:15]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import noticias as nw  # noqa: E402
import poc_backtest as pb  # noqa: E402

TZ = "America/New_York"
CARP = {"ES": "backtest/datos", "NQ": "backtest/datos_NQ"}
TICK = 0.25


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def load():
    out = {}
    for r, c in CARP.items():
        df = pb.load_bars([c], "Etc/GMT+6", "UTC", 1, "auto")
        df.index = df.index.tz_convert(TZ)
        out[r] = df[(df.index >= pd.Timestamp("2024-01-01", tz=TZ)) & (df.index < pd.Timestamp("2026-11-07", tz=TZ))]
    j = out["NQ"].join(out["ES"], lsuffix="_NQ", rsuffix="_ES", how="inner")
    return j


def swings(H, L, k):
    n = len(H)
    sh, sl = [], []
    for i in range(k, n - k):
        if H[i] > H[i - k:i].max() and H[i] >= H[i + 1:i + k + 1].max():
            sh.append(i)
        if L[i] < L[i - k:i].min() and L[i] <= L[i + 1:i + k + 1].min():
            sl.append(i)
    return sh, sl


def dia(g, a, news_days):
    tm = (g.index.hour * 60 + g.index.minute).to_numpy()
    T, O = a.operar, "ES" if a.operar == "NQ" else "NQ"
    Ht, Lt, Ot, Ct = (g[f"{c}_{T}"].to_numpy() for c in ("high", "low", "open", "close"))
    Ho, Lo = g[f"high_{O}"].to_numpy(), g[f"low_{O}"].to_numpy()
    i0 = int(np.searchsorted(tm, 7 * 60))
    i936, i10, iE, i16 = (int(np.searchsorted(tm, hm(x))) for x in ("09:36", "10:00", a.entrada_hasta, "16:00"))
    if i936 >= len(g) or i10 >= len(g):
        return None
    sh, sl = swings(Ht, Lt, a.k)
    smt = None
    for t in range(i936, i10):
        # niveles conocidos en t: swings con i + k < t, desde las 7:00
        for kind, idxs in (("H", sh), ("L", sl)):
            for s in idxs:
                if s < i0 or s + a.k >= t:
                    continue
                lo_, hi_ = max(0, s - 2), min(len(g), s + 3)
                if kind == "H":
                    lt, lo = Ht[s], Ho[lo_:hi_].max()
                    pre_t, pre_o = Ht[s + 1:t].max(initial=-np.inf), Ho[s + 1:t].max(initial=-np.inf)
                    if pre_t > lt or pre_o > lo:
                        continue  # mitigado antes
                    a_t, a_o = Ht[t] > lt, Ho[t] > lo
                else:
                    lt, lo = Lt[s], Lo[lo_:hi_].min()
                    pre_t, pre_o = Lt[s + 1:t].min(initial=np.inf), Lo[s + 1:t].min(initial=np.inf)
                    if pre_t < lt or pre_o < lo:
                        continue
                    a_t, a_o = Lt[t] < lt, Lo[t] < lo
                if a_t != a_o:
                    smt = (t, -1 if kind == "H" else 1)
                    break
            if smt:
                break
        if smt:
            break
    if not smt:
        return {"estado": "sin SMT"}
    t, d = smt
    # extremo y última vela de color contrario
    ext = Ht[t] if d == -1 else Lt[t]
    j = t
    while j >= max(i0, t - 20):
        if (Ct[j] > Ot[j]) if d == -1 else (Ct[j] < Ot[j]):
            break
        j -= 1
    ref = Ot[j]
    entry_i = None
    for u in range(t + 1, min(iE, len(g))):
        if d == -1:
            if Ht[u] > ext:
                ext = Ht[u]
                if Ct[u] > Ot[u]:
                    ref = Ot[u]
            if Ct[u] < ref:
                entry_i = u
                break
        else:
            if Lt[u] < ext:
                ext = Lt[u]
                if Ct[u] < Ot[u]:
                    ref = Ot[u]
            if Ct[u] > ref:
                entry_i = u
                break
    if entry_i is None:
        return {"estado": "SMT sin envolvente"}
    e = Ct[entry_i]
    dist = abs(ext - e)
    if dist < 2 * TICK:
        return {"estado": "riesgo demasiado chico"}
    risk = dist * 1.1
    slv, tpv = e - d * risk, e + d * risk * a.rr
    res, R = "SIN RESOLVER", None
    for u in range(entry_i + 1, min(i16 + 1, len(g))):
        if (Lt[u] <= slv) if d == 1 else (Ht[u] >= slv):
            res, R = "PERDIDA", -1.0
            break
        if (Ht[u] >= tpv) if d == 1 else (Lt[u] <= tpv):
            res, R = "GANADA", a.rr
            break
    if R is None:
        last = min(i16, len(g) - 1)
        R = (Ct[last] - e) * d / risk
    return {"estado": "operó", "dir": "COMPRA" if d == 1 else "VENTA", "hora_smt": g.index[t].strftime("%H:%M"),
            "hora_entrada": g.index[entry_i].strftime("%H:%M"), "entrada": e, "riesgo_pts": risk, "result": res, "R": R}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--operar", default="NQ", choices=["NQ", "ES"])
    p.add_argument("--rr", type=float, default=3.0)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--entrada-hasta", default="10:15")
    p.add_argument("--con-noticias", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    j = load()
    news = set() if a.con_noticias else set(nw.CPI) | set(nw.PPI) | set(nw.NFP)
    rows = []
    for day, g in j.groupby(j.index.date):
        if str(day) in news or g.index[0].hour > 7:
            continue
        r = dia(g, a, news)
        if r is None:
            continue
        r["date"] = str(day)
        rows.append(r)
    t = pd.DataFrame(rows)
    tr = t[t.estado == "operó"].copy()
    tr["anio"] = pd.to_datetime(tr.date).dt.year
    w, l = (tr.result == "GANADA").sum(), (tr.result == "PERDIDA").sum()
    print(f"Operar {a.operar}, R:R 1:{a.rr:g}, fractal {a.k}, entrada hasta {a.entrada_hasta}, "
          f"{'con' if a.con_noticias else 'sin'} días de noticias")
    print("Días:", t.estado.value_counts().to_dict())
    print(f"Operaciones {len(tr)} | ganadas {w} perdidas {l} sin resolver {len(tr) - w - l} | winrate {100 * w / max(1, w + l):.1f}% "
          f"(equilibrio {100 / (1 + a.rr):.1f}%) | R total {tr.R.sum():+.1f} | R/op {tr.R.mean():+.3f} | riesgo mediano {tr.riesgo_pts.median():.1f} pts")
    for yy, g in tr.groupby("anio"):
        ww, ll = (g.result == "GANADA").sum(), (g.result == "PERDIDA").sum()
        print(f"   {yy}: {len(g)} ops, winrate {100 * ww / max(1, ww + ll):.1f}%, R {g.R.sum():+.1f}")
    if not a.quiet:
        print(tr.groupby("dir").R.agg(["count", "sum", "mean"]).round(2).to_string())
    tr.to_csv(f"backtest/resultados/ss_model_{a.operar}_rr{a.rr:g}_k{a.k}.csv", index=False)


if __name__ == "__main__":
    main()
