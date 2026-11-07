#!/usr/bin/env python3
"""Barrida con mecha + cambio de estructura (MSS) con vela de cuerpo fuerte + retroceso a POI (FVG u OB).

NQ, hora ET real, 2024-2026, un trade al día. Para ventas (las compras son el espejo):
  1. Barrida: una vela pasa con MECHA sobre el último máximo de estructura (swing) y cierra por debajo.
  2. MSS: en las 30 velas siguientes, una vela bajista de cuerpo fuerte (>= 60 % de su rango y >= 1 ATR)
     cierra debajo del último mínimo de estructura.
  3. POI: el FVG bajista o el order block (última vela alcista) del tramo que rompió.
  4. Retroceso al POI (orden límite en el borde del POI). Filtro opcional: se cancela si el retroceso
     tiene 3 o más velas alcistas fuertes seguidas.
  5. SL: arriba del máximo de la barrida + 2 pts. TP: el nuevo mínimo creado (o R:R fijo para comparar).
  Ventanas: NY 9:30-11:30 ET, o Londres + NY 3:00-11:30 ET. Cierre forzado 12:00 ET.

    python3 backtest/smc_mss.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load, resample, T0  # noqa: E402

BUF, MIN_RISK, MAX_RISK = 2.0, 5.0, 80.0


def swings(H, L, n=2):
    sh = np.zeros(len(H), bool); sl = np.zeros(len(H), bool)
    for i in range(n, len(H) - n):
        sh[i] = H[i] == H[i - n:i + n + 1].max()
        sl[i] = L[i] == L[i - n:i + n + 1].min()
    return sh, sl


def run(df, start, poi_mode, filt, tp_mode, min_rr):
    O, H, L, C = (df[c].to_numpy() for c in ("open", "high", "low", "close"))
    tm = (df.index.hour * 60 + df.index.minute).to_numpy()
    dates = df.index.date
    rng = H - L
    tr = np.maximum(rng, np.maximum(abs(H - np.roll(C, 1)), abs(L - np.roll(C, 1))))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    body = C - O
    sh, sl = swings(H, L)
    out = []
    day_idx = pd.Series(np.arange(len(df))).groupby(dates)
    for d, ii in day_idx:
        if d < pd.Timestamp(T0).date():
            continue
        ii = ii.to_numpy()
        win = ii[(tm[ii] >= start) & (tm[ii] < 690)]
        if len(win) < 10:
            continue
        trade = None
        for side in (-1, 1):  # se evalúan ambos y se toma el que entra primero
            setup = None
            last_sh = last_sl = None
            for i in range(win[0] - 60, win[-1] + 1):
                # swings confirmados 2 velas después
                if i - 2 >= 0 and sh[i - 2]:
                    last_sh = H[i - 2]
                if i - 2 >= 0 and sl[i - 2]:
                    last_sl = L[i - 2]
                if i < win[0] or last_sh is None or last_sl is None:
                    continue
                if setup is None:
                    lvl = last_sh if side == -1 else last_sl
                    swept = (H[i] > lvl and C[i] < lvl) if side == -1 else (L[i] < lvl and C[i] > lvl)
                    if swept:
                        setup = {"t": i, "ext": H[i] if side == -1 else L[i], "struct": last_sl if side == -1 else last_sh,
                                 "stage": 1}
                    continue
                s = setup
                if s["stage"] == 1:
                    s["ext"] = max(s["ext"], H[i]) if side == -1 else min(s["ext"], L[i])
                    if i - s["t"] > 30:
                        setup = None; continue
                    strong = abs(body[i]) >= 0.6 * rng[i] and abs(body[i]) >= atr[i] and body[i] * side > 0
                    if strong and ((C[i] < s["struct"]) if side == -1 else (C[i] > s["struct"])):
                        # POI del tramo barrida -> MSS
                        poi = None
                        if poi_mode in ("FVG", "FVG u OB"):
                            for k in range(i, s["t"] + 1, -1):
                                if side == -1 and H[k] < L[k - 2]:
                                    poi = (H[k], L[k - 2]); break
                                if side == 1 and L[k] > H[k - 2]:
                                    poi = (L[k], H[k - 2]); break
                        if poi is None and poi_mode in ("OB", "FVG u OB"):
                            for k in range(i - 1, s["t"] - 1, -1):
                                if body[k] * side < 0:
                                    poi = (L[k], H[k]) if side == -1 else (H[k], L[k]); break
                        if poi is None:
                            setup = None; continue
                        s.update(stage=2, mss=i, edge=poi[0], low=L[i] if side == -1 else H[i], run=0)
                    continue
                if s["stage"] == 2:
                    if i - s["mss"] > 60 or tm[i] >= 690:
                        setup = None; continue
                    # nuevo extremo del tramo antes del retroceso = objetivo
                    if (L[i] < s["low"]) if side == -1 else (H[i] > s["low"]):
                        s["low"] = L[i] if side == -1 else H[i]
                    if filt:
                        sb = body[i] * side < 0 and abs(body[i]) >= 0.5 * atr[i]
                        s["run"] = s["run"] + 1 if sb else 0
                        if s["run"] >= 3:
                            setup = None; continue
                    if (H[i] >= s["ext"]) if side == -1 else (L[i] <= s["ext"]):
                        setup = None; continue
                    if (H[i] >= s["edge"]) if side == -1 else (L[i] <= s["edge"]):
                        ent = s["edge"]; stop = s["ext"] + BUF if side == -1 else s["ext"] - BUF
                        risk = (stop - ent) * (-side) * -1 if False else abs(stop - ent)
                        tgt_dist = abs(ent - s["low"])
                        rr = tgt_dist / risk if risk else 0
                        if MIN_RISK <= risk <= MAX_RISK and (tp_mode != "nuevo extremo" or rr >= min_rr):
                            trade = trade if trade and trade["i"] <= i else {"i": i, "side": side, "ent": ent, "stop": stop,
                                                                           "risk": risk, "rr": rr if tp_mode == "nuevo extremo" else float(tp_mode)}
                        setup = None
                        break
        if trade is None:
            continue
        side, ent, stop, risk, rr, i0 = trade["side"], trade["ent"], trade["stop"], trade["risk"], trade["rr"], trade["i"]
        tp = ent + side * rr * risk
        res = None
        if (H[i0] >= stop) if side == -1 else (L[i0] <= stop):
            res = -1.0
        k = i0 + 1
        while res is None and k < len(C) and dates[k] == d:
            if tm[k] >= 720:
                res = (O[k] - ent) * side / risk; break
            if (H[k] >= stop) if side == -1 else (L[k] <= stop):
                res = -1.0; break
            if (L[k] <= tp) if side == -1 else (H[k] >= tp):
                res = rr; break
            k += 1
        if res is None:
            res = (C[k - 1] - ent) * side / risk
        out.append({"date": d, "side": side, "risk": risk, "rr": rr, "R": res - 0.5 / risk})
    return pd.DataFrame(out)


def main():
    nq1 = load("backtest/datos_NQ")
    rows = []
    for tf in (1, 3, 5):
        df = resample(nq1, tf)
        for vent, start in (("NY 9:30", 570), ("Londres+NY 3:00", 180)):
            for poi in ("FVG", "OB", "FVG u OB"):
                for filt in (False, True):
                    for tp_mode, mrr in (("nuevo extremo", 0.0), ("nuevo extremo", 1.0), ("1", 0), ("2", 0)):
                        t = run(df, start, poi, filt, tp_mode, mrr)
                        if t.empty:
                            continue
                        y = pd.to_datetime(t.date).dt.year
                        rows.append({"tf": tf, "ventana": vent, "POI": poi, "filtro_retroceso": "sí" if filt else "no",
                                     "TP": tp_mode + (f" (RR>={mrr:g})" if tp_mode == "nuevo extremo" and mrr else ""),
                                     "ops": len(t), "acierto": round(100 * (t.R > 0).mean(), 1), "RR_medio": round(t.rr.median(), 2),
                                     "riesgo_med": round(t.risk.median(), 1), "R_IS": round(t.R[y <= 2025].sum(), 1),
                                     "R_OOS": round(t.R[y == 2026].sum(), 1), "R_total": round(t.R.sum(), 1),
                                     "R_op": round(t.R.mean(), 3)})
            print(f"tf {tf} {vent} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/smc_mss.csv", index=False)
    pd.set_option("display.width", 230)
    g = T.groupby(["tf", "ventana"])
    print(pd.DataFrame({"combos": g.size(), "R/op prom": g.R_op.mean().round(3), "acierto prom": g.acierto.mean().round(1),
                        "robustas": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum())}).to_string())
    print("\nPor tipo de TP:")
    g = T.groupby("TP")
    print(pd.DataFrame({"R/op prom": g.R_op.mean().round(3), "acierto prom": g.acierto.mean().round(1), "RR medio": g.RR_medio.mean().round(2),
                        "robustas": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum()), "de": g.size()}).to_string())
    print("\nFiltro de retroceso:")
    print(T.groupby("filtro_retroceso").R_op.mean().round(3).to_string())
    print("\nTu regla exacta (TP = nuevo extremo, con filtro), NY:")
    print(T[(T.TP == "nuevo extremo") & (T.filtro_retroceso == "sí") & (T.ventana == "NY 9:30")].to_string(index=False))
    print("\nMejores robustas:")
    print(T[(T.R_IS > 0) & (T.R_OOS > 0) & (T.ops >= 80)].sort_values("R_total", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
