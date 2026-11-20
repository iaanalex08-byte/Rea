#!/usr/bin/env python3
"""Estrategia "apertura de NY": barrida de liquidez + (SMT opcional) + entrada en Fair Value Gap.

Hora de Nueva York real (America/New_York, con horario de verano), NQ 2024-2026, un trade al día.
  Ventana de setups: 9:00-10:00 ET (30 min antes de la apertura y la primera media hora).
  Liquidez (nivel): máximo / mínimo de la noche (18:00-9:00 ET) o de la hora previa (8:00-9:00 ET).
  Barrida: el precio rompe el nivel dentro de la ventana.
  FVG: después de la barrida, hueco de 3 velas en sentido contrario (alcista tras barrer el mínimo).
  Entrada: límite en el borde del FVG. SL: el extremo de la barrida más un margen. TP: R:R fijo.
  SMT (opcional): el ES NO barre su nivel equivalente cuando el NQ sí lo hace.
  Cierre forzado a las 12:00 ET.

    python3 backtest/apertura_ny_fvg.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

ET = "America/New_York"
T0, T1 = "2024-01-01", "2026-11-07"
TICK = 0.25
BUF = 2.0                    # margen bajo / sobre el extremo de la barrida (pts NQ)
MIN_RISK, MAX_RISK = 8.0, 80.0


def load(path):
    a = pb.parse_args([path, "--tf", "1"])
    df = pb.load_bars(a.csv, a.input_tz, a.tz, 1, a.nt_tz)
    df = df[(df.index >= pd.Timestamp(T0, tz=a.tz) - pd.Timedelta(days=2)) & (df.index < pd.Timestamp(T1, tz=a.tz))]
    df.index = df.index.tz_convert(ET)
    return df


def resample(df, tf):
    if tf == 1:
        return df
    return df.resample(f"{tf}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])


def levels(df):
    tm = df.index.hour * 60 + df.index.minute
    night = df[(tm >= 18 * 60) | (tm < 9 * 60)]
    key = np.where(night.index.hour >= 18, (night.index + pd.Timedelta(days=1)).date, night.index.date)
    n = night.groupby(key).agg(nH=("high", "max"), nL=("low", "min"))
    pre = df[(tm >= 8 * 60) & (tm < 9 * 60)]
    p = pre.groupby(pre.index.date).agg(hH=("high", "max"), hL=("low", "min"))
    return n.join(p, how="inner")


def run(nq, es_lv, nq_lv, es, tf, nivel, smt, rr):
    out = []
    tm_all = nq.index.hour * 60 + nq.index.minute
    es_win = {}
    if smt:
        etm = es.index.hour * 60 + es.index.minute
        w = es[(etm >= 9 * 60) & (etm < 10 * 60)]
        for dd, eg in w.groupby(w.index.date):
            es_win[dd] = (eg.index.asi8, np.maximum.accumulate(eg.high.to_numpy()), np.minimum.accumulate(eg.low.to_numpy()))
    for d, g in nq[(tm_all >= 9 * 60) & (tm_all < 12 * 60)].groupby(nq[(tm_all >= 9 * 60) & (tm_all < 12 * 60)].index.date):
        if d < pd.Timestamp(T0).date() or d not in nq_lv.index:
            continue
        t = (g.index.hour * 60 + g.index.minute).to_numpy()
        if t[0] != 9 * 60:
            continue
        O, H, L, C = g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy(), g.close.to_numpy()
        lv = nq_lv.loc[d]
        hiL, loL = (lv.nH, lv.nL) if nivel == "noche" else (lv.hH, lv.hL)
        if smt:
            if d not in es_lv.index:
                continue
            el = es_lv.loc[d]
            ehi, elo = (el.nH, el.nL) if nivel == "noche" else (el.hH, el.hL)
            if d not in es_win:
                continue
            e_ts, eH, eL = es_win[d]
        # estado por lado: +1 = compra (tras barrer el mínimo), -1 = venta (tras barrer el máximo)
        st = {1: {"sw": None, "ext": None, "ent": None, "sl": None}, -1: {"sw": None, "ext": None, "ent": None, "sl": None}}
        trade = None
        for i in range(len(t)):
            if t[i] >= 10 * 60 and trade is None:
                break
            if trade is not None:
                break
            for side in (1, -1):
                s = st[side]
                # barrida
                if s["sw"] is None:
                    hit = (L[i] < loL) if side == 1 else (H[i] > hiL)
                    if hit:
                        ok = True
                        if smt:
                            k = int(np.searchsorted(e_ts, g.index[i].value, side="right")) - 1
                            ok = k >= 0 and ((eL[k] >= elo) if side == 1 else (eH[k] <= ehi))
                        if ok:
                            s["sw"], s["ext"] = i, (L[i] if side == 1 else H[i])
                    continue
                # extremo de la barrida mientras no haya entrada pendiente
                if s["ent"] is None:
                    s["ext"] = min(s["ext"], L[i]) if side == 1 else max(s["ext"], H[i])
                    if i - 2 > s["sw"] - 1 and i >= 2:
                        fvg = (L[i] > H[i - 2] and C[i - 1] > O[i - 1]) if side == 1 else (H[i] < L[i - 2] and C[i - 1] < O[i - 1])
                        if fvg:
                            ent = H[i - 2] if side == 1 else L[i - 2]
                            sl = s["ext"] - BUF if side == 1 else s["ext"] + BUF
                            risk = (ent - sl) * side
                            if MIN_RISK <= risk <= MAX_RISK:
                                s["ent"], s["sl"], s["i"] = ent, sl, i
                    continue
                # entrada pendiente: se llena si regresa al FVG; se cancela si rompe el SL antes
                if (L[i] <= s["sl"]) if side == 1 else (H[i] >= s["sl"]):
                    if (L[i] <= s["ent"]) if side == 1 else (H[i] >= s["ent"]):
                        trade = {"side": side, "ent": s["ent"], "sl": s["sl"], "i": i, "res": -1.0}
                    else:
                        s.update(sw=None, ent=None)
                    continue
                if (L[i] <= s["ent"]) if side == 1 else (H[i] >= s["ent"]):
                    trade = {"side": side, "ent": s["ent"], "sl": s["sl"], "i": i, "res": None}
                    break
        if trade is None:
            continue
        side, ent, sl, i0 = trade["side"], trade["ent"], trade["sl"], trade["i"]
        risk = (ent - sl) * side
        tp = ent + side * risk * rr
        res = trade["res"]
        if res is None:
            for k in range(i0 + 1, len(t)):
                if t[k] >= 12 * 60:
                    res = (O[k] - ent) * side / risk
                    break
                if (L[k] <= sl) if side == 1 else (H[k] >= sl):
                    res = -1.0; break
                if (H[k] >= tp) if side == 1 else (L[k] <= tp):
                    res = rr; break
            if res is None:
                res = (C[-1] - ent) * side / risk
        out.append({"date": d, "side": side, "hora": g.index[i0].strftime("%H:%M"), "riesgo_pts": risk, "R": res})
    return pd.DataFrame(out)


def main():
    nq1, es1 = load("backtest/datos_NQ"), load("backtest/datos")
    nq_lv, es_lv = levels(nq1), levels(es1)
    rows, keep = [], {}
    for tf in (1, 3):
        nq, es = resample(nq1, tf), resample(es1, tf)
        for nivel in ("noche", "hora previa"):
            for smt in (False, True):
                for rr in (1.0, 1.5, 2.0):
                    tr = run(nq, es_lv, nq_lv, es, tf, nivel, smt, rr)
                    if tr.empty:
                        continue
                    y = pd.to_datetime(tr.date).dt.year
                    R = tr.R - 0.5 / tr.riesgo_pts  # 2 ticks de deslizamiento + comisión aprox.
                    w = (tr.R > 0).mean()
                    rows.append({"tf": tf, "liquidez": nivel, "SMT": "sí" if smt else "no", "RR": rr, "ops": len(tr),
                                 "dias_%": round(100 * len(tr) / 735, 0), "acierto": round(100 * w, 1),
                                 "riesgo_med_pts": round(tr.riesgo_pts.median(), 1),
                                 "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
                                 "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
                    keep[(tf, nivel, smt, rr)] = tr
            print(f"tf {tf} listo", file=sys.stderr)
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/apertura_ny_fvg.csv", index=False)
    pd.set_option("display.width", 220)
    print(T.to_string(index=False))
    pd.to_pickle(keep, "backtest/resultados/apertura_ny_fvg_ops.pkl")


if __name__ == "__main__":
    main()
