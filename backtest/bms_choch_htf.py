#!/usr/bin/env python3
"""BMS/CHoCH -> POI (FVG u OB) -> entrada (límite o 1.ª/2.ª fractal) en 1 h y 4 h. NQ, 2024-2026.

En temporalidades altas no se limita a NY: los setups pueden darse a cualquier hora y la operación sigue
hasta SL o TP ("swing"), o se cierra a las 16:00 ET del mismo día ("intradía"). Una operación a la vez.
Mismas reglas que backtest/bms_choch.py. Costo: 1 pt por operación (comisión + deslizamiento).

    python3 backtest/bms_choch_htf.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from smc_mss import swings  # noqa: E402

BUF, COST = 2.0, 1.0


def run(df, kinds, poi_mode, entry_mode, tp_mode, hold, buf_k):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    idx = df.index
    sh, sl = swings(H, L)
    tr = np.maximum(H - L, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    highs, lows = [], []
    used_h = used_l = None
    setup, out = None, []
    i = 2
    t0 = pd.Timestamp("2024-01-01", tz="America/New_York")
    while i < len(C):
        if sh[i - 2]:
            highs.append((i - 2, H[i - 2]))
        if sl[i - 2]:
            lows.append((i - 2, L[i - 2]))
        if len(highs) < 2 or len(lows) < 2 or idx[i] < t0:
            i += 1; continue
        trend = 1 if (highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]) else \
            (-1 if (highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]) else 0)
        trade = None
        if setup is None:
            for side, lvl, used in ((1, highs[-1], used_h), (-1, lows[-1], used_l)):
                if used == lvl[0] or not ((C[i] > lvl[1]) if side == 1 else (C[i] < lvl[1])):
                    continue
                if side == 1:
                    used_h = lvl[0]
                else:
                    used_l = lvl[0]
                kind = "BMS" if trend == side else ("CHoCH" if trend == -side else None)
                if kind not in kinds:
                    continue
                start = lows[-1][0] if side == 1 else highs[-1][0]
                poi = None
                if poi_mode == "FVG":
                    for k in range(i, max(start + 1, i - 30), -1):
                        if side == 1 and L[k] > H[k - 2]:
                            poi = (L[k], H[k - 2]); break
                        if side == -1 and H[k] < L[k - 2]:
                            poi = (H[k], L[k - 2]); break
                else:
                    for k in range(i - 1, max(start - 1, i - 30), -1):
                        if (C[k] - O[k]) * side < 0:
                            poi = (H[k], L[k]) if side == 1 else (L[k], H[k]); break
                if poi is not None:
                    setup = {"side": side, "edge": poi[0], "far": poi[1], "brk": i, "ext": H[i] if side == 1 else L[i],
                             "touched": False, "fr": 0, "fb": None}
                break
            i += 1; continue
        s = setup; side = s["side"]; b = buf_k * atr[i]
        if i - s["brk"] > 30:
            setup = None; i += 1; continue
        if not s["touched"]:
            s["ext"] = max(s["ext"], H[i]) if side == 1 else min(s["ext"], L[i])
        if (C[i] < s["far"] - b) if side == 1 else (C[i] > s["far"] + b):
            setup = None; i += 1; continue
        hit = (L[i] <= s["edge"]) if side == 1 else (H[i] >= s["edge"])
        if hit and not s["touched"]:
            s["touched"] = True
            if entry_mode == "límite":
                trade = (i, side, s["edge"], s["far"] - side * b, s["ext"])
        elif s["touched"] and entry_mode != "límite":
            f = i - 2
            if (sl[f] if side == 1 else sh[f]) and f > s["brk"]:
                s["fb"] = f
            fb = s["fb"]
            if fb is not None and ((C[i] > H[fb]) if side == 1 else (C[i] < L[fb])):
                s["fr"] += 1; s["fb"] = None
                if s["fr"] == (1 if entry_mode == "1.ª fractal" else 2):
                    stop = min(L[fb], s["far"]) - b if side == 1 else max(H[fb], s["far"]) + b
                    trade = (i, side, C[i], stop, s["ext"])
        if trade is None:
            i += 1; continue
        setup = None
        i0, side, ent, stop, ext = trade
        risk = (ent - stop) * side
        tgt = ext if tp_mode == "extremo" else ent + side * float(tp_mode) * risk
        if risk <= 0 or (tgt - ent) * side < risk:
            i += 1; continue
        rr = (tgt - ent) * side / risk
        r = -1.0 if (entry_mode == "límite" and ((L[i0] <= stop) if side == 1 else (H[i0] >= stop))) else None
        k = i0 + 1
        day = idx[i0].date()
        while r is None and k < len(C):
            if hold == "intradía" and (idx[k].date() != day or idx[k].hour >= 16):
                r = (O[k] - ent) * side / risk; break
            if (L[k] <= stop) if side == 1 else (H[k] >= stop):
                r = -1.0; break
            if (H[k] >= tgt) if side == 1 else (L[k] <= tgt):
                r = rr; break
            k += 1
        if r is None:
            r = (C[-1] - ent) * side / risk
        out.append({"date": idx[i0].date(), "side": side, "risk": risk, "R": r - COST / risk, "bars": k - i0})
        i = k + 1  # una operación a la vez
    return pd.DataFrame(out)


def main():
    nq1 = load("backtest/datos_NQ")
    rows = []
    for tf, lab, bk in ((60, "1 h", 0.1), (240, "4 h", 0.1)):
        df = resample(nq1, tf)
        for kinds, kn in ((("BMS", "CHoCH"), "BMS o CHoCH"), (("BMS",), "solo BMS"), (("CHoCH",), "solo CHoCH")):
            for poi in ("FVG", "OB"):
                for em in ("límite", "1.ª fractal", "2.ª fractal"):
                    for tp in ("1", "2", "extremo"):
                        for hold in ("swing", "intradía"):
                            t = run(df, kinds, poi, em, tp, hold, bk)
                            if len(t) < 8:
                                continue
                            y = pd.to_datetime(t.date).dt.year
                            rows.append({"velas": lab, "quiebre": kn, "POI": poi, "entrada": em, "TP": tp if tp == "extremo" else tp + "R",
                                         "salida": hold, "ops/año": round(len(t) / 2.85, 1), "acierto %": round(100 * (t.R > 0).mean(), 1),
                                         "SL med pts": round(t.risk.median()), "R/op": round(t.R.mean(), 3),
                                         "R 24-25": round(t.R[y <= 2025].sum(), 1), "R 2026": round(t.R[y == 2026].sum(), 1)})
        print(lab, "listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    T.to_csv("backtest/resultados/bms_choch_htf.csv", index=False)
    pd.set_option("display.width", 230)
    g = T.groupby(["velas", "salida", "entrada"])
    print(pd.DataFrame({"versiones": g.size(), "ops/año prom": g["ops/año"].mean().round(1), "acierto prom": g["acierto %"].mean().round(1),
                        "R/op prom": g["R/op"].mean().round(3), "robustas": g.robusta.sum()}).to_string())
    print("\nMejores robustas con >= 10 ops/año:")
    print(T[T.robusta & (T["ops/año"] >= 10)].sort_values("R/op", ascending=False).head(12).to_string(index=False))
    print(f"\nRobustas: {T.robusta.sum()} de {len(T)}")


if __name__ == "__main__":
    main()
