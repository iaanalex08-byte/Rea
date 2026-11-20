#!/usr/bin/env python3
"""NY: BMS o CHoCH -> POI (OB o FVG) -> entrada en la 1.ª o 2.ª fractal. NQ, 2024-2026, hora ET real.

  Estructura: swings fractales (2 velas a cada lado). Tendencia alcista = último máximo y último mínimo más altos que
  los anteriores (bajista al revés).
  BMS: cierre que rompe el último swing a favor de la tendencia.  CHoCH: cierre que rompe el último swing en contra.
  POI: el FVG del tramo que rompió (o el OB = última vela contraria antes del tramo).
  Entrada (compra; venta = espejo), cuando el precio regresa al POI:
    "límite": orden en el borde del POI.
    "1.ª fractal" / "2.ª fractal": dentro o tras tocar el POI se forma un mínimo fractal; se entra cuando una vela cierra
    por encima del máximo de la vela fractal (primera o segunda vez que ocurre).
  SL: 2 pts más allá del extremo (POI o fractal, el más lejano). TP: R:R fijo o el extremo del tramo que rompió.
  Setups 9:30-11:30 ET (estructura desde 8:00), cierre 12:00 ET, una operación al día.

    python3 backtest/bms_choch.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample  # noqa: E402
from smc_mss import swings  # noqa: E402

BUF, MIN_RISK, MAX_RISK = 2.0, 4.0, 80.0


def run(df, kinds, poi_mode, entry_mode, tp_mode):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tm = (df.index.hour * 60 + df.index.minute).to_numpy()
    dates = df.index.date
    sh, sl = swings(H, L)
    out = []
    for d, ii in pd.Series(np.arange(len(df))).groupby(dates):
        if d < pd.Timestamp("2024-01-01").date():
            continue
        ii = ii.to_numpy(); t = tm[ii]
        if 570 not in t:
            continue
        highs, lows = [], []  # (índice, precio) de swings confirmados
        setup = None; trade = None; used_h = used_l = None
        for i in ii[(t >= 480) & (t < 690)]:
            if sh[i - 2]:
                highs.append((i - 2, H[i - 2]))
            if sl[i - 2]:
                lows.append((i - 2, L[i - 2]))
            if len(highs) < 2 or len(lows) < 2:
                continue
            trend = 1 if (highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]) else \
                (-1 if (highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]) else 0)
            if tm[i] >= 570 and setup is None:
                for side, lvl, used in ((1, highs[-1], used_h), (-1, lows[-1], used_l)):
                    if used == lvl[0]:
                        continue
                    if (C[i] > lvl[1]) if side == 1 else (C[i] < lvl[1]):
                        kind = "BMS" if trend == side else ("CHoCH" if trend == -side else None)
                        if side == 1:
                            used_h = lvl[0]
                        else:
                            used_l = lvl[0]
                        if kind not in kinds:
                            continue
                        start = (lows[-1][0] if side == 1 else highs[-1][0])  # origen del tramo que rompió
                        poi = None
                        if poi_mode in ("FVG", "FVG u OB"):
                            for k in range(i, max(start + 1, i - 40), -1):
                                if side == 1 and L[k] > H[k - 2]:
                                    poi = (L[k], H[k - 2]); break
                                if side == -1 and H[k] < L[k - 2]:
                                    poi = (H[k], L[k - 2]); break
                        if poi is None and poi_mode in ("OB", "FVG u OB"):
                            for k in range(i - 1, max(start - 1, i - 40), -1):
                                if (C[k] - O[k]) * side < 0:
                                    poi = (H[k], L[k]) if side == 1 else (L[k], H[k]); break
                        if poi is not None:
                            setup = {"side": side, "edge": poi[0], "far": poi[1], "brk": i, "ext": H[i] if side == 1 else L[i],
                                     "touched": False, "fr": 0}
                        break
                continue
            if setup is None:
                continue
            s = setup; side = s["side"]
            if i - s["brk"] > 40 or tm[i] >= 690:
                setup = None; continue
            if not s["touched"]:
                s["ext"] = max(s["ext"], H[i]) if side == 1 else min(s["ext"], L[i])
            if (C[i] < s["far"] - BUF) if side == 1 else (C[i] > s["far"] + BUF):
                setup = None; continue  # el POI se invalidó
            hit = (L[i] <= s["edge"]) if side == 1 else (H[i] >= s["edge"])
            if hit and not s["touched"]:
                s["touched"] = True
                if entry_mode == "límite":
                    ent, stop = s["edge"], s["far"] - side * BUF
                    trade = (i, side, ent, stop, s["ext"]); break
                continue
            if s["touched"] and entry_mode != "límite":
                # fractal a favor confirmada (mínimo para compras) y cierre que rompe el máximo de esa vela
                f = i - 2
                if (sl[f] if side == 1 else sh[f]) and f > s["brk"]:
                    s["fr_bar"] = f
                fb = s.get("fr_bar")
                if fb is not None and ((C[i] > H[fb]) if side == 1 else (C[i] < L[fb])):
                    s["fr"] += 1; s["fr_bar"] = None
                    need = 1 if entry_mode == "1.ª fractal" else 2
                    if s["fr"] == need:
                        ent = C[i]
                        stop = min(L[fb], s["far"]) - BUF if side == 1 else max(H[fb], s["far"]) + BUF
                        trade = (i, side, ent, stop, s["ext"]); break
        if not trade:
            continue
        i0, side, ent, stop, ext = trade
        risk = (ent - stop) * side
        if not (MIN_RISK <= risk <= MAX_RISK):
            continue
        tgt = ext if tp_mode == "extremo" else ent + side * float(tp_mode) * risk
        if (tgt - ent) * side < risk:
            continue
        rr = (tgt - ent) * side / risk
        r = None; k = i0 + (0 if entry_mode == "límite" else 1)
        if entry_mode == "límite" and ((L[i0] <= stop) if side == 1 else (H[i0] >= stop)):
            r = -1.0
        k = i0 + 1
        while r is None and k < len(C) and dates[k] == d:
            if tm[k] >= 720:
                r = (O[k] - ent) * side / risk; break
            if (L[k] <= stop) if side == 1 else (H[k] >= stop):
                r = -1.0; break
            if (H[k] >= tgt) if side == 1 else (L[k] <= tgt):
                r = rr; break
            k += 1
        if r is None:
            r = (C[k - 1] - ent) * side / risk
        out.append({"date": d, "side": side, "risk": risk, "R": r - 0.5 / risk})
    return pd.DataFrame(out)


def main():
    nq1 = load("backtest/datos_NQ")
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq1, tf)
        for kinds, kn in ((("BMS", "CHoCH"), "BMS o CHoCH"), (("BMS",), "solo BMS"), (("CHoCH",), "solo CHoCH")):
            for poi in ("FVG", "OB"):
                for em in ("límite", "1.ª fractal", "2.ª fractal"):
                    for tp in ("1", "2", "extremo"):
                        t = run(df, kinds, poi, em, tp)
                        if len(t) < 10:
                            continue
                        y = pd.to_datetime(t.date).dt.year
                        rows.append({"velas": tf, "quiebre": kn, "POI": poi, "entrada": em, "TP": tp if tp == "extremo" else tp + "R",
                                     "ops/año": round(len(t) / 2.85), "acierto %": round(100 * (t.R > 0).mean(), 1),
                                     "SL med": round(t.risk.median(), 1), "R/op": round(t.R.mean(), 3),
                                     "R 24-25": round(t.R[y <= 2025].sum(), 1), "R 2026": round(t.R[y == 2026].sum(), 1)})
        print(f"{tf} min listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/bms_choch.csv", index=False)
    pd.set_option("display.width", 220)
    T["robusta"] = (T["R 24-25"] > 0) & (T["R 2026"] > 0)
    g = T.groupby(["velas", "entrada"])
    print(pd.DataFrame({"versiones": g.size(), "R/op prom": g["R/op"].mean().round(3), "acierto prom": g["acierto %"].mean().round(1),
                        "robustas": g.robusta.sum()}).to_string())
    g = T.groupby(["quiebre"])
    print(); print(pd.DataFrame({"R/op prom": g["R/op"].mean().round(3), "robustas": g.robusta.sum(), "de": g.size()}).to_string())
    print("\nMejores robustas:")
    print(T[T.robusta].sort_values("R/op", ascending=False).head(12).to_string(index=False))
    print(f"\nRobustas: {T.robusta.sum()} de {len(T)}")


if __name__ == "__main__":
    main()
