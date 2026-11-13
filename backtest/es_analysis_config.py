"""Análisis detallado de una configuración concreta del backtest ES.

Por defecto: modelo B (9:12 hora de Ciudad de México), tendencia EMA 20 de
velas de 3 minutos, SL 45 ticks, TP1 30 ticks, TP2 60 ticks, 2 contratos.

    python backtest/es_analysis_config.py  ->  results/es/analisis_B_CDMX_45_30_60/
"""
import json
import os

import numpy as np
import pandas as pd

from es_backtest import (COST_T, TICK, TICK_USD, NEWS, ROOT, SIGN_TRENDS, day_paths,
                         first_hit, load, trend_series)

CFG = dict(name="B_CDMX_45_30_60", time="9:12", tz="America/Mexico_City",
           trend="EMA20 3m", sl=45, tp1=30, tp2=60, contracts=2)
OUT = os.path.join(ROOT, "results", "es", "analisis_" + CFG["name"])


def trade_detail(e, side, g, sl, tp1, tp2):
    """Simula los 2 contratos y devuelve el detalle de la operación."""
    h, l, c = g["h"].to_numpy(), g["l"].to_numpy(), g["c"].to_numpy()
    fav = ((h - e) if side > 0 else (e - l)) / TICK
    adv = ((e - l) if side > 0 else (h - e)) / TICK
    cf, ca = np.maximum.accumulate(fav), np.maximum.accumulate(adv)
    i_sl, i_tp1 = first_hit(ca, sl), first_hit(cf, tp1)
    last = (c[-1] - e) / TICK * side
    # contrato 1
    if i_sl is not None and (i_tp1 is None or i_sl <= i_tp1):
        r1, x1, k1 = -sl, "SL", i_sl
    elif i_tp1 is not None:
        r1, x1, k1 = tp1, "TP1", i_tp1
    else:
        r1, x1, k1 = last, "CIERRE", len(c) - 1
    # contrato 2
    if x1 == "SL":
        r2, x2, k2 = -sl, "SL", i_sl
    elif x1 == "CIERRE":
        r2, x2, k2 = last, "CIERRE", len(c) - 1
    else:
        i_tp2 = first_hit(cf, tp2)
        if i_tp2 is not None and i_tp2 == i_tp1:
            r2, x2, k2 = tp2, "TP2", i_tp2
        else:
            k = i_tp1 + 1
            cf2, ca2 = np.maximum.accumulate(fav[k:]), np.maximum.accumulate(adv[k:])
            j_tp, j_be = first_hit(cf2, tp2), first_hit(ca2, 0.0)
            if j_be is not None and (j_tp is None or j_be <= j_tp):
                r2, x2, k2 = 0.0, "BE", k + j_be
            elif j_tp is not None:
                r2, x2, k2 = tp2, "TP2", k + j_tp
            else:
                r2, x2, k2 = last, "CIERRE", len(c) - 1
    k_end = max(k1, k2)
    # excursiones máximas en los primeros 60 minutos y hasta el cierre del trade
    w60 = min(60, len(c))
    return dict(r1=r1, r2=r2, ticks=r1 + r2, x1=x1, x2=x2,
                outcome={("SL", "SL"): "Stop (−2)", ("TP1", "BE"): "TP1 + BE",
                         ("TP1", "TP2"): "TP1 + TP2"}.get((x1, x2), "Cierre 15:59" if x1 == "CIERRE" else "TP1 + cierre"),
                mins=int(k_end) + 1, mins_tp1=(int(i_tp1) + 1) if x1 == "TP1" else None,
                mfe_trade=float(cf[k_end]), mae_trade=float(ca[k_end]),
                mfe60=float(cf[w60 - 1]), mae60=float(ca[w60 - 1]))


def stats(usd):
    usd = np.asarray(usd, float)
    eq = np.cumsum(usd)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    run = worst = 0
    for v in usd:
        run = run + 1 if v < 0 else 0
        worst = max(worst, run)
    gw, gl = usd[usd > 0].sum(), -usd[usd < 0].sum()
    sd = usd.std(ddof=1)
    return dict(n=len(usd), winrate=float((usd > 0).mean()), pf=float(gw / gl) if gl else None,
                net=float(usd.sum()), avg=float(usd.mean()), maxdd=float(-dd.min()),
                worst_streak=int(worst), t=float(usd.mean() / sd * np.sqrt(len(usd))),
                avg_win=float(usd[usd > 0].mean()), avg_loss=float(usd[usd < 0].mean()))


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    trends = trend_series(df)
    tr = trends[CFG["trend"]]
    paths = day_paths(df, CFG["time"], CFG["tz"])
    news = pd.read_csv(NEWS)
    cat = dict(zip(pd.to_datetime(news.date).dt.date,
                   news.event.map(lambda e: "NFP/CPI 8:30" if e in ("NFP", "CPI") else "FOMC")))
    # volatilidad: rango del día anterior (sesión 9:30-16:00 NY) en puntos
    rth = df.between_time("09:30", "15:59")
    rng = (rth["h"].groupby(rth.index.normalize()).max() - rth["l"].groupby(rth.index.normalize()).min())
    prev_rng = rng.shift(1)
    atr = rng.rolling(10).mean().shift(1)   # rango medio de las 10 sesiones previas (puntos)

    def levels(d, tp_f=None, sl_f=None):
        """SL, TP1 y TP2 en ticks: fijos, o en % del rango medio si CFG tiene 'atr'."""
        if "atr" not in CFG:
            return CFG["sl"], CFG["tp1"], CFG["tp2"]
        tp_f = CFG["atr"][0] if tp_f is None else tp_f
        sl_f = CFG["atr"][1] if sl_f is None else sl_f
        a = atr.get(pd.Timestamp(d), np.nan)
        if np.isnan(a):
            return None
        tp1 = max(4, round(a * tp_f / TICK))
        return max(20, round(a * sl_f / TICK)), tp1, 2 * tp1

    rows = []
    for d, t0, g in paths:
        e = g["o"].iloc[0]
        ref = tr.get(t0, np.nan)
        if np.isnan(ref):
            continue
        side = int(ref) if CFG["trend"] in SIGN_TRENDS else (1 if e > ref else -1)
        if side == 0:
            continue
        lv = levels(d)
        if lv is None:
            continue
        det = trade_detail(e, side, g, *lv)
        usd = det["ticks"] * TICK_USD - CFG["contracts"] * COST_T * TICK_USD
        rows.append(dict(date=pd.Timestamp(d), entry_ny=t0.strftime("%H:%M"), side="Compra" if side > 0 else "Venta",
                         sl_ticks=lv[0], tp1_ticks=lv[1], tp2_ticks=lv[2],
                         entry=round(e, 2), usd=round(usd, 2), news=cat.get(d, "Sin noticia"),
                         prev_range=prev_rng.get(pd.Timestamp(d), np.nan), **det))
    t = pd.DataFrame(rows)
    t["win"] = t.usd > 0
    t["year"] = t.date.dt.year
    t["month"] = t.date.dt.to_period("M").astype(str)
    t["weekday"] = t.date.dt.weekday.map(dict(enumerate(["Lun", "Mar", "Mié", "Jue", "Vie"])))
    t["wom"] = "Semana " + ((t.date.dt.day - 1) // 7 + 1).astype(str)
    t["horario_ny"] = np.where(t.entry_ny == "10:12", "10:12 NY (invierno)", "11:12 NY (verano)")
    t["vol"] = pd.qcut(t.prev_range, 3, labels=["Baja", "Media", "Alta"]).astype(str)
    t.to_csv(os.path.join(OUT, "operaciones.csv"), index=False)

    out = dict(config=CFG, cost_per_trade_usd=CFG["contracts"] * COST_T * TICK_USD, stats=stats(t.usd))
    r = t.usd.to_numpy()
    rng_ = np.random.default_rng(7)
    boot = rng_.choice(r, (20000, len(r))).mean(1)
    out["bootstrap"] = dict(ci_avg=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                            p_avg_le_0=float((boot <= 0).mean()))
    # Monte Carlo: reordenar las operaciones para ver drawdowns y rachas posibles
    dds, streaks, nets100 = [], [], []
    for _ in range(5000):
        s = rng_.permutation(r)
        eq = np.cumsum(s)
        dds.append(float(-(eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()))
        run = w = 0
        for v in s:
            run = run + 1 if v < 0 else 0
            w = max(w, run)
        streaks.append(w)
        nets100.append(float(rng_.choice(r, 100).sum()))
    out["montecarlo"] = dict(dd_p50=float(np.median(dds)), dd_p95=float(np.percentile(dds, 95)),
                             streak_p50=float(np.median(streaks)), streak_p95=float(np.percentile(streaks, 95)),
                             p_loss_100=float(np.mean(np.array(nets100) < 0)))

    def grp(col):
        g = t.groupby(col).agg(n=("usd", "size"), winrate=("win", "mean"), net=("usd", "sum"),
                               avg=("usd", "mean")).reset_index()
        return g.rename(columns={col: "k"}).round(4).to_dict("records")

    for col in ["outcome", "side", "year", "month", "weekday", "wom", "news", "horario_ny", "vol"]:
        out[col] = grp(col)
    tp1 = t.mins_tp1.dropna()
    out["timing"] = dict(median_min_to_exit=float(t.mins.median()), median_min_to_tp1=float(tp1.median()),
                         pct_tp1_15min=float((tp1 <= 15).mean()),
                         stops_median_min=float(t.loc[t.outcome == "Stop (−2)", "mins"].median()))
    out["excursion"] = dict(mfe60_p50=float(t.mfe60.median()), mae60_p50=float(t.mae60.median()),
                            stops_mfe_p50=float(t.loc[t.outcome == "Stop (−2)", "mfe_trade"].median()),
                            stops_reached_20=float((t.loc[t.outcome == "Stop (−2)", "mfe_trade"] >= 20).mean()))
    # sensibilidad alrededor de la configuración
    sens = []
    if "atr" in CFG:
        for slf in (0.35, 0.5, 0.65, 0.8):
            for tpf in (0.02, 0.03, 0.04, 0.05):
                u = []
                for d, t0, g in paths:
                    e = g["o"].iloc[0]
                    ref = tr.get(t0, np.nan)
                    lv = levels(d, tpf, slf)
                    if np.isnan(ref) or lv is None:
                        continue
                    det = trade_detail(e, 1 if e > ref else -1, g, *lv)
                    u.append(det["ticks"] * TICK_USD - 2 * COST_T * TICK_USD)
                s = stats(u)
                sens.append(dict(sl=round(slf * 100), tp1=round(tpf * 100), tp2=round(2 * tpf * 100),
                                 pf=s["pf"], net=s["net"], winrate=s["winrate"], t=s["t"]))
    b_sl, b_tp = CFG.get("sl", 0), CFG.get("tp1", 0)
    sl_grid = [] if "atr" in CFG else sorted({max(5, b_sl - 15), max(5, b_sl - 5), b_sl, b_sl + 5, b_sl + 15})
    tp_grid = [(max(5, b_tp - 10), 2 * max(5, b_tp - 10)), (b_tp, 2 * b_tp), (b_tp + 10, 2 * (b_tp + 10))]
    for sl in sl_grid:
        for tp1_, tp2_ in tp_grid:
            u = []
            for d, t0, g in paths:
                e = g["o"].iloc[0]
                ref = tr.get(t0, np.nan)
                if np.isnan(ref):
                    continue
                side = 1 if e > ref else -1
                det = trade_detail(e, side, g, sl, tp1_, tp2_)
                u.append(det["ticks"] * TICK_USD - 2 * COST_T * TICK_USD)
            s = stats(u)
            sens.append(dict(sl=sl, tp1=tp1_, tp2=tp2_, pf=s["pf"], net=s["net"], winrate=s["winrate"], t=s["t"]))
    out["sensitivity"] = sens
    with open(os.path.join(OUT, "analisis.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    return t, out


if __name__ == "__main__":
    t, out = main()
    print(json.dumps({k: out[k] for k in ["stats", "bootstrap", "montecarlo", "timing", "excursion"]}, indent=1))
    for k in ["outcome", "side", "year", "horario_ny", "vol", "news", "weekday", "wom"]:
        print(k, [(r["k"], r["n"], round(r["winrate"], 2), round(r["net"])) for r in out[k]])
    print("sens", [(s["sl"], s["tp1"], s["tp2"], round(s["pf"], 2), round(s["net"]), round(s["t"], 2)) for s in out["sensitivity"]])
