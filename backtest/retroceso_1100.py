#!/usr/bin/env python3
"""NQ: entrada a mercado a favor de la noche después de un retroceso pequeño (CDMX, velas de 1 min, 2024-2026).

Dirección = cierre 8:29 vs apertura 00:00 (la noche). A la hora H se mide el retroceso desde las 8:29
(en contra de la noche). Si está dentro de la banda, entrada a mercado en la apertura de la vela de H a favor
de la noche. SL fijo; TP en R o sin TP (cierre a las 14:30). Costo 1 pt.

    python3 backtest/retroceso_1100.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

COST = 1.0
_df = None


def bars():
    global _df
    if _df is None:
        a = pb.parse_args(["backtest/datos_NQ", "--tf", "1"])
        df = pb.load_bars(a.csv, a.input_tz, a.tz, 1, a.nt_tz)
        _df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-07", tz=a.tz))]
    return _df


def trades(hora=660, banda=(-50, 0), sl=60.0, tp=None, min_night=0.0):
    df = bars()
    out = []
    for d, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] > 5 or (tm == hora).sum() == 0 or (tm < 510).sum() == 0:
            continue
        O, H, L, C = (g[c].to_numpy() for c in ("open", "high", "low", "close"))
        o00 = O[0]; p829 = C[tm < 510][-1]
        nd = np.sign(p829 - o00)
        if nd == 0 or abs(p829 - o00) < min_night:
            continue
        i = int(np.flatnonzero(tm == hora)[0])
        back = (C[i - 1] - p829) * nd
        if not (banda[0] <= back < banda[1]):
            continue
        ent = O[i]; stop = ent - nd * sl; tgt = None if tp is None else ent + nd * tp * sl
        res, j = None, i
        while j < len(C):
            if tm[j] >= 870:
                res = (O[j] - ent) * nd; break
            if (L[j] <= stop) if nd == 1 else (H[j] >= stop):
                res = -sl; break
            if tgt is not None and ((H[j] >= tgt) if nd == 1 else (L[j] <= tgt)):
                res = tp * sl; break
            j += 1
        if res is None:
            res = (C[-1] - ent) * nd
        out.append({"date": d, "entry": g.index[i], "exit": g.index[min(j, len(g) - 1)], "dir": int(nd),
                    "pts": res - COST, "R": (res - COST) / sl, "mae": sl if res <= -sl else 0.0})
    return pd.DataFrame(out)


def main():
    rows = []
    for hora in (600, 630, 660, 690):
        for banda in ((-50, 0), (-80, 0), (-30, 0), (-50, -10)):
            for sl in (40, 60, 80, 120):
                for tp in (None, 1.0, 2.0):
                    t = trades(hora, banda, sl, tp)
                    y = pd.to_datetime(t.date).dt.year
                    usd = t.pts * 2 - 1.24; eq = usd.cumsum()
                    rows.append({"hora": f"{hora // 60}:{hora % 60:02d}", "banda": f"{banda[0]} a {banda[1]}", "SL": sl, "TP": tp or "cierre",
                                 "ops": len(t), "acierto %": round(100 * (t.pts > 0).mean(), 1), "R/op": round(t.R.mean(), 3),
                                 "R 24-25": round(t.R[y <= 2025].mean(), 3), "R 2026": round(t.R[y == 2026].mean(), 3),
                                 "neto $ 1 MNQ": round(usd.sum()), "caída $": round((eq.cummax().clip(lower=0) - eq).max())})
        print(hora, "listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/retroceso_1100.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"{len(T)} versiones, robustas {T.robusta.sum()}")
    print(T.groupby("hora").robusta.agg(["sum", "size"]).to_string())
    print(T[T.hora == "11:00"].to_string(index=False))


if __name__ == "__main__":
    main()
