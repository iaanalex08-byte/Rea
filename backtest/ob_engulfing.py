#!/usr/bin/env python3
"""Estrategia Order Block + envolvente (NQ, sesión de NY en hora ET real, 2024-2026, un trade al día).

  Desplazamiento: dos velas seguidas en la misma dirección con cuerpo >= 0.6 ATR(14) y cierre que rompe
                  el máximo (o mínimo) de las 10 velas previas. Una vela sola no cuenta.
  Order block:    la última vela contraria antes del desplazamiento. Zona = OB completo o su 50 %.
  Entrada:        el precio regresa a la zona con al menos 2 velas de retroceso y aparece una vela
                  envolvente a favor: se entra al cierre de la envolvente.
  Invalidación:   cierre más allá del OB antes de entrar.
  SL:             fijo (15 / 23 / 35 pts) o estructural (otro lado del OB + 2 pts). TP a R:R fijo.
  Filtros:        ninguno / premium-descuento del día anterior / sin días de noticias fuertes.
  Ventana:        setups de 9:30 a 11:30 ET; cierre forzado 12:00 ET.

    python3 backtest/ob_engulfing.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import noticias as nt  # noqa: E402
from apertura_ny_fvg import load, resample, T0  # noqa: E402

NEWS = {pd.Timestamp(x).date() for x in nt.FOMC + nt.CPI + nt.NFP + nt.PPI}
SLS = ["15", "23", "35", "estructural"]
RRS = [1.0, 1.5, 2.0]


def setups(df, zona):
    """Una entrada como máximo por día: [fecha, lado, índice de entrada, precio, OB bajo, OB alto, extremo previo]."""
    tm = df.index.hour * 60 + df.index.minute
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    body = C - O
    dates = df.index.date
    # rango del día anterior (sesión 9:30-16:00 ET)
    rth = df[(tm >= 570) & (tm < 960)]
    pr = rth.groupby(rth.index.date).agg(h=("high", "max"), l=("low", "min"))
    pmid = ((pr.h + pr.l) / 2).shift(1)
    out = []
    idx = np.where((tm >= 570) & (tm < 690))[0]
    by_day = pd.Series(idx).groupby(dates[idx])
    for d, ii in by_day:
        if d < pd.Timestamp(T0).date():
            continue
        ii = ii.to_numpy()
        lo_i, hi_i = ii[0], ii[-1]
        pend = {1: None, -1: None}
        done = False
        for i in range(lo_i, hi_i + 1):
            if done:
                break
            # nuevo desplazamiento terminando en i
            for side in (1, -1):
                if i - 12 < 0 or np.isnan(atr[i]):
                    continue
                b1, b2 = body[i - 1] * side, body[i] * side
                if b1 >= 0.6 * atr[i] and b2 >= 0.6 * atr[i]:
                    brk = C[i] > H[i - 11:i - 1].max() if side == 1 else C[i] < L[i - 11:i - 1].min()
                    if brk:
                        k = i - 2
                        while k > i - 7 and body[k] * side > 0:
                            k -= 1
                        if body[k] * side < 0:
                            pend[side] = {"lo": L[k], "hi": H[k], "start": i, "retro": 0, "touch": False}
            for side in (1, -1):
                p = pend[side]
                if p is None or i <= p["start"]:
                    continue
                mid = (p["lo"] + p["hi"]) / 2
                edge = (p["hi"] if zona == "OB" else mid) if side == 1 else (p["lo"] if zona == "OB" else mid)
                if (C[i] < p["lo"]) if side == 1 else (C[i] > p["hi"]):
                    pend[side] = None
                    continue
                if body[i] * side < 0:
                    p["retro"] += 1
                if (L[i] <= edge) if side == 1 else (H[i] >= edge):
                    p["touch"] = True
                eng = body[i] * side > 0 and body[i - 1] * side < 0 and \
                    ((C[i] >= O[i - 1] and O[i] <= C[i - 1]) if side == 1 else (C[i] <= O[i - 1] and O[i] >= C[i - 1]))
                if p["touch"] and p["retro"] >= 2 and eng:
                    pm = pmid.get(d, np.nan)
                    out.append({"date": d, "side": side, "i": i, "ent": C[i], "ob_lo": p["lo"], "ob_hi": p["hi"],
                                "pd_ok": bool(np.isnan(pm) or ((C[i] < pm) if side == 1 else (C[i] > pm)))})
                    done = True
                    break
    return pd.DataFrame(out), (O, H, L, C, tm)


def outcome(S, arrs, sl_mode, rr):
    O, H, L, C, tm = arrs
    res = []
    for s in S.itertuples():
        side, ent = s.side, s.ent
        if sl_mode == "estructural":
            sl = s.ob_lo - 2 if side == 1 else s.ob_hi + 2
        else:
            sl = ent - side * float(sl_mode)
        risk = (ent - sl) * side
        if risk < 4 or risk > 120:
            res.append(np.nan); continue
        tp = ent + side * rr * risk
        r = None
        for k in range(s.i + 1, min(s.i + 400, len(C))):
            if tm[k] >= 720 or tm[k] < 570:
                r = (O[k] - ent) * side / risk; break
            if (L[k] <= sl) if side == 1 else (H[k] >= sl):
                r = -1.0; break
            if (H[k] >= tp) if side == 1 else (L[k] <= tp):
                r = rr; break
        res.append(np.nan if r is None else r - 0.5 / risk)
    return np.array(res)


def main():
    nq1 = load("backtest/datos_NQ")
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq1, tf)
        for zona in ("OB", "50% OB"):
            S, arrs = setups(df, zona)
            if S.empty:
                continue
            y = pd.to_datetime(S.date).dt.year.to_numpy()
            for sl_mode in SLS:
                for rr in RRS:
                    R = outcome(S, arrs, sl_mode, rr)
                    for filtro, m in (("ninguno", np.ones(len(S), bool)), ("premium/descuento", S.pd_ok.to_numpy()),
                                      ("sin noticias", ~S.date.isin(NEWS).to_numpy())):
                        mm = m & ~np.isnan(R)
                        r, yy = R[mm], y[mm]
                        if len(r) == 0:
                            continue
                        rows.append({"tf": tf, "zona": zona, "SL": sl_mode, "RR": rr, "filtro": filtro, "ops": len(r),
                                     "acierto": round(100 * (r > 0).mean(), 1), "R_IS": round(r[yy <= 2025].sum(), 1),
                                     "R_OOS": round(r[yy == 2026].sum(), 1), "R_total": round(r.sum(), 1),
                                     "R_op": round(r.mean(), 3)})
            print(f"tf {tf} {zona}: {len(S)} setups", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/ob_engulfing.csv", index=False)
    pd.set_option("display.width", 220)
    g = T.groupby(["tf", "zona", "filtro"])
    print(pd.DataFrame({"ops": g.ops.max(), "acierto prom": g.acierto.mean().round(1), "R/op prom": g.R_op.mean().round(3),
                        "robustas": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum()), "de": g.size()}).to_string())
    print("\nSL 23 fijo, sin filtro:")
    print(T[(T.SL == "23") & (T.filtro == "ninguno")].to_string(index=False))
    print("\nMayor acierto (ops >= 100):")
    print(T[T.ops >= 100].sort_values("acierto", ascending=False).head(10).to_string(index=False))
    print("\nMejores robustas:")
    print(T[(T.R_IS > 0) & (T.R_OOS > 0)].sort_values("R_total", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
