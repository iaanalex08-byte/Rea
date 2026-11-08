#!/usr/bin/env python3
"""Convierte los dos patrones más estables de patrones_ny.py en reglas y las mide (NQ, 1 MNQ, costo 1 pt).

A) Hueco que se llena: a las 9:30, si el hueco contra el cierre de ayer mide entre X y Y pts, entrar hacia el cierre
   de ayer. TP = cierre de ayer. SL = k veces el hueco. Cierre forzado 16:00 ET.
B) Primer extremo de la noche: cuando NY rompe primero el máximo (mínimo) de la noche, entrar a favor en esa ruptura.
   SL = mitad del rango de la noche (o R fijo); salida a las 16:00 o TP a R:R fijo.

    python3 backtest/patrones_ny_reglas.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load  # noqa: E402

COST = 1.0


def main():
    nq = load("backtest/datos_NQ")
    t_all = nq.index.hour * 60 + nq.index.minute
    sess, prevc = [], None
    for d, g in nq.groupby(nq.index.date):
        t = (g.index.hour * 60 + g.index.minute).to_numpy()
        r = g[(t >= 570) & (t < 960)]
        if len(r) < 370:
            continue
        on = g[t < 570]
        sess.append((d, r.open.to_numpy(), r.high.to_numpy(), r.low.to_numpy(), r.close.to_numpy(), prevc,
                     on.high.max() if len(on) else np.nan, on.low.min() if len(on) else np.nan))
        prevc = r.close.iloc[-1]
    rows = []
    # A) hueco
    for lo_, hi_ in ((20, 50), (30, 80), (50, 100)):
        for k in (1.0, 1.5, 2.0):
            res = []
            for d, O, H, L, C, pc, onh, onl in sess:
                if pc is None:
                    continue
                gap = O[0] - pc
                if not (lo_ <= abs(gap) < hi_):
                    continue
                side = -1 if gap > 0 else 1
                ent = O[0]; tp = pc; sl = ent - side * k * abs(gap); r_ = None
                for i in range(len(O)):
                    if (L[i] <= sl) if side == 1 else (H[i] >= sl):
                        r_ = sl - ent if side == 1 else ent - sl; break
                    if (H[i] >= tp) if side == 1 else (L[i] <= tp):
                        r_ = abs(gap); break
                if r_ is None:
                    r_ = (C[-1] - ent) * side
                res.append((d.year, r_ - COST, k * abs(gap)))
            x = pd.DataFrame(res, columns=["y", "pts", "risk"])
            rows.append({"regla": f"A) hueco {lo_}-{hi_} pts, SL {k}x hueco", "ops": len(x), "acierto %": round(100 * (x.pts > 0).mean(), 1),
                         "pts/op 24-25": round(x.pts[x.y <= 2025].mean(), 1), "pts/op 2026": round(x.pts[x.y == 2026].mean(), 1),
                         "R/op": round((x.pts / x.risk).mean(), 3), "$ año 1 MNQ": round(x.pts.sum() * 2 / 2.85)})
    # B) primer extremo de la noche
    for stop_mode in ("mitad noche", "40 pts", "80 pts"):
        for exit_mode in ("16:00", "1R", "2R"):
            res = []
            for d, O, H, L, C, pc, onh, onl in sess:
                if np.isnan(onh):
                    continue
                trade = None
                for i in range(len(O)):
                    if H[i] > onh and L[i] < onl:
                        break  # ambigua en la misma vela
                    if H[i] > onh:
                        trade = (i, 1, max(onh, O[i])); break
                    if L[i] < onl:
                        trade = (i, -1, min(onl, O[i])); break
                if not trade or trade[0] > 180:  # solo si rompe antes de las 12:30
                    continue
                i0, side, ent = trade
                risk = abs(ent - (onh + onl) / 2) if stop_mode == "mitad noche" else float(stop_mode.split()[0])
                sl = ent - side * risk
                tp = None if exit_mode == "16:00" else ent + side * float(exit_mode[0]) * risk
                r_ = None
                for k in range(i0 + 1, len(O)):
                    if (L[k] <= sl) if side == 1 else (H[k] >= sl):
                        r_ = -risk; break
                    if tp is not None and ((H[k] >= tp) if side == 1 else (L[k] <= tp)):
                        r_ = abs(tp - ent); break
                if r_ is None:
                    r_ = (C[-1] - ent) * side
                res.append((d.year, r_ - COST, risk))
            x = pd.DataFrame(res, columns=["y", "pts", "risk"])
            rows.append({"regla": f"B) rompe primero extremo de la noche · SL {stop_mode} · salida {exit_mode}", "ops": len(x),
                         "acierto %": round(100 * (x.pts > 0).mean(), 1), "pts/op 24-25": round(x.pts[x.y <= 2025].mean(), 1),
                         "pts/op 2026": round(x.pts[x.y == 2026].mean(), 1), "R/op": round((x.pts / x.risk).mean(), 3),
                         "$ año 1 MNQ": round(x.pts.sum() * 2 / 2.85)})
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
