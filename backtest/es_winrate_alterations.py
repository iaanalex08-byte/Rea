"""Alteraciones del modelo B (9:12 CDMX, EMA20 3m) para subir el % de operaciones que llegan al TP1.

1. Entrada en retroceso: orden limitada k ticks a mejor precio, válida W minutos.
2. Filtros de confirmación y de día, elegidos con 2025 y comprobados en 2026.
3. TP1 proporcional a la volatilidad (ATR diario).

    python backtest/es_winrate_alterations.py  ->  results/es/alteraciones_winrate/
"""
import itertools
import os

import numpy as np
import pandas as pd

from es_analysis_config import trade_detail
from es_backtest import COST_T, NEWS, ROOT, TICK, TICK_USD, day_paths, load, trend_series

OUT = os.path.join(ROOT, "results", "es", "alteraciones_winrate")
TIME, TZ = "9:12", "America/Mexico_City"


def usd(ticks):
    return ticks * TICK_USD - 2 * COST_T * TICK_USD


def summarize(name, hits, u, years, extra=None):
    hits, u, years = np.asarray(hits, bool), np.asarray(u, float), np.asarray(years)
    gl = -u[u < 0].sum()
    d = dict(alteracion=name, n=len(u), tp1_rate=hits.mean() if len(u) else np.nan,
             tp1_25=hits[years == 2025].mean() if (years == 2025).any() else np.nan,
             tp1_26=hits[years == 2026].mean() if (years == 2026).any() else np.nan,
             pf=u[u > 0].sum() / gl if gl else np.nan, net=u.sum(), avg=u.mean() if len(u) else np.nan,
             avg25=u[years == 2025].mean() if (years == 2025).any() else np.nan,
             avg26=u[years == 2026].mean() if (years == 2026).any() else np.nan)
    if extra:
        d.update(extra)
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    trends = trend_series(df)
    e20 = trends["EMA20 3m"]
    news = pd.read_csv(NEWS)
    news_days = set(pd.to_datetime(news.date).dt.date)
    rth = df.between_time("09:30", "15:59")
    day = rth.index.normalize()
    rng = rth["h"].groupby(day).max() - rth["l"].groupby(day).min()
    atr = rng.rolling(10).mean().shift(1)            # rango medio de las 10 sesiones previas
    prev_rng = rng.shift(1)
    rth_open = rth["o"].groupby(day).first()
    c3 = df["c"].resample("3min").last().dropna()
    o3 = df["o"].resample("3min").first().dropna()
    last3 = np.sign(c3 - o3).shift(1).reindex(df.index, method="ffill")
    last3_3 = np.sign(c3 - o3).rolling(3).sum().shift(1).reindex(df.index, method="ffill")

    base = []
    for d, t0, g in day_paths(df, TIME, TZ):
        ref = e20.get(t0, np.nan)
        if np.isnan(ref):
            continue
        e = g["o"].iloc[0]
        side = 1 if e > ref else -1
        D = pd.Timestamp(d)
        o930 = rth_open.get(D, np.nan)
        agree = sum(int(np.sign(e - trends[k].get(t0, np.nan)) == side)
                    for k in ("EMA50 3m", "EMA50 5m", "EMA20 1h") if not np.isnan(trends[k].get(t0, np.nan)))
        base.append(dict(
            date=D, year=D.year, side=side, e=e, g=g,
            weekday=D.weekday(), news=d in news_days, prev_rng=prev_rng.get(D, np.nan), atr=atr.get(D, np.nan),
            dist_ema=abs(e - ref) / TICK, last3_ok=last3.get(t0, 0) * side > 0,
            last3x3=last3_3.get(t0, 0) * side, agree=agree,
            morning=(e - o930) / TICK * side if not np.isnan(o930) else np.nan,
            summer=t0.hour == 11,
        ))
    B = pd.DataFrame(base)
    rows = []

    # ---- 0) referencia y TP fijos
    for sl, tp1 in ((60, 15), (60, 10), (60, 8), (45, 10), (45, 8), (80, 10)):
        det = [trade_detail(r.e, r.side, r.g, sl, tp1, 2 * tp1) for r in B.itertuples()]
        rows.append(summarize(f"Entrada 9:12 a mercado · SL {sl} · TP {tp1}/{2 * tp1}",
                              [x["x1"] == "TP1" for x in det], [usd(x["ticks"]) for x in det], B.year,
                              dict(tipo="Referencia", sl=sl, tp1=tp1)))

    # ---- 1) entrada en retroceso con orden limitada
    for k, W, sl, tp1 in itertools.product((4, 8, 12, 16, 20), (10, 20, 40), (45, 60), (10, 15)):
        hits, u, yrs = [], [], []
        for r in B.itertuples():
            g = r.g.iloc[:W]
            lvl = r.e - r.side * k * TICK
            touched = (g["l"] <= lvl) if r.side > 0 else (g["h"] >= lvl)
            if not touched.any():
                continue
            i = int(np.argmax(touched.to_numpy()))
            # en la vela de entrada solo cuenta lo que pasa después del toque: se usa desde la siguiente vela
            gg = r.g.iloc[i + 1:] if i + 1 < len(r.g) else None
            if gg is None or len(gg) < 2:
                continue
            x = trade_detail(lvl, r.side, gg, sl, tp1, 2 * tp1)
            hits.append(x["x1"] == "TP1"); u.append(usd(x["ticks"])); yrs.append(r.year)
        rows.append(summarize(f"Limitada {k} ticks a favor, válida {W} min · SL {sl} · TP {tp1}/{2 * tp1}",
                              hits, u, yrs, dict(tipo="Entrada en retroceso", sl=sl, tp1=tp1, k=k, W=W,
                                                 pct_dias=len(u) / len(B))))

    # ---- 2) TP1 según ATR
    for f, sl_f in itertools.product((0.03, 0.05, 0.08, 0.1), (0.25, 0.35, 0.5)):
        hits, u, yrs = [], [], []
        for r in B.itertuples():
            if np.isnan(r.atr):
                continue
            tp1 = max(4, round(r.atr * f / TICK)); sl = max(20, round(r.atr * sl_f / TICK))
            x = trade_detail(r.e, r.side, r.g, sl, tp1, 2 * tp1)
            hits.append(x["x1"] == "TP1"); u.append(usd(x["ticks"])); yrs.append(r.year)
        rows.append(summarize(f"TP1 = {f:.0%} del rango medio · SL = {sl_f:.0%} del rango medio", hits, u, yrs,
                              dict(tipo="Objetivo según volatilidad")))

    # ---- 3) filtros sobre la configuración del usuario (SL 60 · TP 15/30): elegir con 2025, probar en 2026
    det = [trade_detail(r.e, r.side, r.g, 60, 15, 30) for r in B.itertuples()]
    B["hit"] = [x["x1"] == "TP1" for x in det]
    B["usd"] = [usd(x["ticks"]) for x in det]
    q = B.prev_rng.quantile([1 / 3, 2 / 3]).to_numpy()
    FILTERS = {
        "Sin viernes": B.weekday != 4,
        "Sin días de noticia": ~B.news,
        "Sin volatilidad alta el día anterior": B.prev_rng <= q[1],
        "Solo volatilidad baja el día anterior": B.prev_rng <= q[0],
        "Solo horario de verano (11:12 NY)": B.summer,
        "Última vela de 3 min a favor": B.last3_ok,
        "Las 3 últimas velas de 3 min a favor": B.last3x3 >= 3,
        "Las 4 tendencias de acuerdo": B.agree == 3,
        "Al menos 3 tendencias de acuerdo": B.agree >= 2,
        "Cerca de la EMA 20 (< 20 ticks)": B.dist_ema < 20,
        "Lejos de la EMA 20 (> 40 ticks)": B.dist_ema > 40,
        "Mañana a favor (> 10 pts desde 9:30)": B.morning > 40,
        "Mañana lateral (±10 pts)": B.morning.abs() <= 40,
        "Solo compras": B.side > 0,
        "Solo ventas": B.side < 0,
    }
    frows = []
    for n_comb in (1, 2, 3):
        for combo in itertools.combinations(FILTERS, n_comb):
            m = np.logical_and.reduce([FILTERS[c].to_numpy() for c in combo])
            sub = B[m]
            if len(sub) < 40:
                continue
            frows.append(summarize(" + ".join(combo), sub.hit, sub.usd, sub.year,
                                   dict(tipo="Filtros (SL 60 · TP 15/30)", n_filtros=n_comb, pct_dias=len(sub) / len(B))))
    F = pd.DataFrame(frows)
    # selección honesta: mejor en 2025 (sin mirar 2026)
    F["rank25"] = F.tp1_25.rank(ascending=False)
    rows += frows

    R = pd.DataFrame(rows)
    R.round(4).to_csv(os.path.join(OUT, "alteraciones.csv"), index=False)
    B.drop(columns=["g"]).to_csv(os.path.join(OUT, "operaciones_base.csv"), index=False)
    return R, F


if __name__ == "__main__":
    R, F = main()
    pd.set_option("display.width", 230); pd.set_option("display.max_colwidth", 80)
    cols = ["alteracion", "n", "tp1_rate", "tp1_25", "tp1_26", "pf", "net", "avg25", "avg26"]
    print("REFERENCIA"); print(R[R.tipo == "Referencia"][cols].round(3).to_string(index=False))
    pb = R[R.tipo == "Entrada en retroceso"].sort_values("tp1_rate", ascending=False)
    print("RETROCESO (top por % TP1)"); print(pb.head(10)[cols + ["pct_dias"]].round(3).to_string(index=False))
    print("RETROCESO >=91% y neto>0:"); print(pb[(pb.tp1_rate >= .91) & (pb.net > 0)][cols + ["pct_dias"]].round(3).to_string(index=False))
    print("ATR"); print(R[R.tipo == "Objetivo según volatilidad"].sort_values("tp1_rate", ascending=False).head(6)[cols].round(3).to_string(index=False))
    print("FILTROS: mejores en 2025 (elegidos sin ver 2026), n>=40")
    print(F.sort_values("tp1_25", ascending=False).head(12)[cols + ["pct_dias"]].round(3).to_string(index=False))
    print("FILTROS con >=91% en ambos años:", ((F.tp1_25 >= .91) & (F.tp1_26 >= .91)).sum(), "de", len(F))
    print(F[(F.tp1_25 >= .91) & (F.tp1_26 >= .91)].sort_values("net", ascending=False).head(10)[cols + ["pct_dias"]].round(3).to_string(index=False))
