#!/usr/bin/env python3
"""Reversión en el oro (GC): entrar en contra del movimiento de la mañana. UTC-6, velas de 1 min.

    python3 backtest/oro_reversion.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

TICK, USD, COM = 0.10, 10.0, 1.24  # MGC
VENTANAS = [("07:00", "11:00"), ("08:00", "11:00"), ("09:30", "11:00"), ("07:00", "10:30"), ("07:00", "11:30")]
SLS = [5.0, 8.0, 12.0]
RRS = [1.0, 1.5, 2.0]
CLOSE = 14 * 60 + 30


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def main():
    df = pb.load_bars(["backtest/datos_GC"], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz="Etc/GMT+6")) & (df.index < pd.Timestamp("2026-11-07", tz="Etc/GMT+6"))]
    days = []
    for day, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        days.append((day, tm, g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()))
    rows = []
    for a, b in VENTANAS:
        ta, tb = hm(a), hm(b)
        base = []
        for day, tm, O, H, L, C in days:
            ia, ib = int(np.searchsorted(tm, ta)), int(np.searchsorted(tm, tb))
            if ia >= len(tm) or ib >= len(tm) or tm[ia] != ta or tm[ib] != tb:
                continue
            mv = O[ib] - O[ia]
            if mv == 0:
                continue
            base.append((day, -np.sign(mv), abs(mv), ib, tm, O, H, L, C))
        med = np.median([x[2] for x in base])
        for filt in ("todos", "mov > mediana"):
            sel = base if filt == "todos" else [x for x in base if x[2] > med]
            # salida al cierre 14:30
            res = []
            for day, d, mv, ib, tm, O, H, L, C in sel:
                ic = int(np.searchsorted(tm, CLOSE))
                if ic >= len(tm):
                    continue
                res.append((day.year, (O[ic] - O[ib]) * d))
            r = pd.DataFrame(res, columns=["anio", "pts"])
            rows.append({"ventana": f"{a}->{b}", "filtro": filt, "salida": "hasta 14:30", "ops": len(r),
                         "acierto %": round(100 * (r.pts > 0).mean(), 1), "equilibrio %": None,
                         "pts 24-25": round(r.pts[r.anio <= 2025].sum(), 1), "pts 2026": round(r.pts[r.anio == 2026].sum(), 1),
                         "pts/op": round(r.pts.mean(), 2), "$ 1 MGC": round((r.pts * USD - COM).sum())})
            for sl in SLS:
                for rr in RRS:
                    tp = sl * rr
                    res = []
                    for day, d, mv, ib, tm, O, H, L, C in sel:
                        e = O[ib]
                        out = None
                        for k in range(ib, len(tm)):
                            if tm[k] >= CLOSE:
                                out = (O[k] - e) * d
                                break
                            if (L[k] <= e - sl) if d == 1 else (H[k] >= e + sl):
                                out = -sl
                                break
                            if (H[k] >= e + tp) if d == 1 else (L[k] <= e - tp):
                                out = tp
                                break
                        if out is None:
                            out = (C[-1] - e) * d
                        res.append((day.year, out))
                    r = pd.DataFrame(res, columns=["anio", "pts"])
                    w, l = (r.pts >= tp - 1e-9).sum(), (r.pts <= -sl + 1e-9).sum()
                    rows.append({"ventana": f"{a}->{b}", "filtro": filt, "salida": f"SL {sl:g} / TP {tp:g}", "ops": len(r),
                                 "acierto %": round(100 * w / max(1, w + l), 1), "equilibrio %": round(100 / (1 + rr), 1),
                                 "pts 24-25": round(r.pts[r.anio <= 2025].sum(), 1), "pts 2026": round(r.pts[r.anio == 2026].sum(), 1),
                                 "pts/op": round(r.pts.mean(), 2), "$ 1 MGC": round((r.pts * USD - COM).sum())})
    t = pd.DataFrame(rows)
    t.to_csv("backtest/resultados/oro_reversion.csv", index=False)
    pd.set_option("display.width", 220)
    print("Salida hasta 14:30 (reversión pura):")
    print(t[t.salida == "hasta 14:30"].to_string(index=False))
    rob = t[(t["pts 24-25"] > 0) & (t["pts 2026"] > 0)]
    print(f"\nCombinaciones positivas en ambos periodos: {len(rob)} de {len(t)}")
    print(rob.sort_values("pts/op", ascending=False).head(15).to_string(index=False))


if __name__ == "__main__":
    main()
