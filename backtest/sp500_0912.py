#!/usr/bin/env python3
"""Estrategia del video (SP500): tendencia 00:00-9:00 CDMX y entrada a mercado a las 9:12 en esa dirección.

  Dirección: cierre de las 8:59 vs apertura de las 00:00 (alcista = compra, bajista = venta).
  Entrada: apertura de la vela de 1 min de las 9:12, a mercado.
  SL 30 ticks. TP1 a 30 ticks (1:1): se cierra la mitad y el SL pasa a BE. TP2 a 60 ticks.
  Si no se resuelve, cierre a las 15:00 CDMX.
  Vela de 1 min donde se tocan SL y TP a la vez: "conservador" = primero el SL; "optimista" = primero el TP.

Dos formas de contar el resultado de cada operación:
  - Como el registro del video: SL = -1, TP1 + BE = +1, TP2 = +2.
  - En R real (riesgo = SL de toda la posición): SL = -1, TP1 + BE = +0.5, TP2 = +1.5.

    python3 backtest/sp500_0912.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402


def bars(folder):
    a = pb.parse_args([folder, "--tf", "1"])
    df = pb.load_bars(a.csv, a.input_tz, a.tz, 1, a.nt_tz)
    return df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]


def run(df, tick, sl_t=30, tp1_t=30, tp2_t=60, orden="conservador", entry_min=552, trend_end=540, close_min=900):
    out = []
    for d, g in df.groupby(df.index.date):
        if g.index[0].dayofweek >= 5:
            continue
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] > 5 or (tm == entry_min).sum() == 0 or (tm < trend_end).sum() == 0:
            continue
        O, H, L, C = (g[c].to_numpy() for c in ("open", "high", "low", "close"))
        o00, c900 = O[0], C[tm < trend_end][-1]
        s = int(np.sign(c900 - o00))
        if s == 0:
            continue
        i = int(np.flatnonzero(tm == entry_min)[0])
        ent = O[i]
        sl, tp1, tp2 = ent - s * sl_t * tick, ent + s * tp1_t * tick, ent + s * tp2_t * tick
        stage, res = 0, None
        for j in range(i, len(C)):
            if tm[j] >= close_min:
                px = O[j]
                res = ("cierre", (px - ent) * s / (sl_t * tick)) if stage == 0 else ("TP1 + cierre", 0.5 + 0.5 * (px - ent) * s / (sl_t * tick))
                break
            hi, lo = (H[j], L[j]) if s == 1 else (-L[j], -H[j])
            e, slv, t1, t2 = ent * s, sl * s, tp1 * s, tp2 * s
            if stage == 0:
                hit_sl, hit_tp1 = lo <= slv, hi >= t1
                if hit_sl and (not hit_tp1 or orden == "conservador"):
                    res = ("SL", -1.0); break
                if hit_tp1:
                    stage = 1
                    if hi >= t2:
                        res = ("TP2", 1.5); break
                    if lo <= e and orden == "conservador" and j > i:
                        res = ("TP1 + BE", 0.5); break
                    continue
            else:
                hit_be, hit_tp2 = lo <= e, hi >= t2
                if hit_be and (not hit_tp2 or orden == "conservador"):
                    res = ("TP1 + BE", 0.5); break
                if hit_tp2:
                    res = ("TP2", 1.5); break
        if res is None:
            continue
        how, r = res
        video = {"SL": -1.0, "TP1 + BE": 1.0, "TP2": 2.0}.get(how, r * 2 if how.startswith("TP1") else r)
        out.append({"fecha": d, "dir": s, "entrada": ent, "resultado": how, "R": round(r, 3), "unidades_video": round(video, 3)})
    return pd.DataFrame(out)


def resumen(t, col):
    u = t[col]; eq = u.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
    run = w = 0
    for v in u:
        run = run + 1 if v < -0.05 else 0; w = max(w, run)
    g, l = u[u > 0.05], u[u < -0.05]
    return {"días": len(u), "total": round(u.sum(), 1), "por día": round(u.mean(), 2), "días +": f"{(u > 0.05).mean():.0%}",
            "días −": f"{(u < -0.05).mean():.0%}", "en cero": f"{(u.abs() <= 0.05).mean():.0%}", "gan. media": round(g.mean(), 2),
            "pérd. media": round(-l.mean(), 2), "factor benef.": round(g.sum() / -l.sum(), 2), "caída máx": round(dd, 1), "peor racha": w}


def main():
    es = bars("backtest/datos")
    rows = []
    for orden in ("conservador", "optimista"):
        t = run(es, 0.25, orden=orden)
        t.to_csv(f"backtest/resultados/sp500_0912_{orden}.csv", index=False)
        per = t[(t.fecha >= pd.Timestamp("2026-01-05").date()) & (t.fecha <= pd.Timestamp("2026-09-29").date())]
        for lab, x in (("5 ene - 29 sep 2026", per), ("2024", t[pd.to_datetime(t.fecha).dt.year == 2024]),
                       ("2025", t[pd.to_datetime(t.fecha).dt.year == 2025]), ("2024 - 2026 completo", t)):
            for col, nm in (("unidades_video", "como el video"), ("R", "R real")):
                rows.append({"orden en la vela": orden, "periodo": lab, "conteo": nm, **resumen(x, col)})
        if orden == "conservador":
            print("Resultados 5 ene - 29 sep 2026 (conservador):", per.resultado.value_counts().to_dict())
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/sp500_0912_resumen.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
