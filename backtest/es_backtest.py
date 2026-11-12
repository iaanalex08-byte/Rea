"""Backtest ES (S&P 500) — entradas a hora fija a favor de la tendencia.

Modelos pedidos:
  A) 9:00  · SL 60 ticks · TP1 60 ticks · TP2 120 ticks
  B) 9:12  · SL 30 ticks · TP1 30 ticks · TP2 60 ticks

Supuestos (todos parametrizables):
  - Se calcula con hora de Nueva York y con hora de Ciudad de México.
    Entrada al precio de apertura del minuto indicado.
  - Tendencia en temporalidad de 3 minutos: precio de entrada vs EMA 20 de
    velas de 3 minutos ya cerradas (arriba = compra, abajo = venta). Se comparan
    otras definiciones en 3m (EMA 9, EMA 50, cruce EMA 9/20, última vela) y en
    otras temporalidades.
  - 2 contratos: uno sale en TP1, otro en TP2. Tras tocar TP1 el stop del
    segundo pasa a break-even (variante sin BE incluida).
  - Si una misma vela de 1 minuto toca stop y objetivo, cuenta como stop.
  - Lo que siga abierto a las 15:59 se cierra a mercado.
  - Costes: 1 tick de deslizamiento + 4,50 USD de comisión por contrato.
  - 1 tick = 0,25 puntos = 12,50 USD.
Datos: SPXUSD 1m (HistData). Es el índice, no el futuro: los niveles difieren
por la base, pero los movimientos intradía son prácticamente iguales.

    python backtest/es_backtest.py   ->  results/es/es_data.json + es_trades.csv
"""
import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "spx")
OUT = os.path.join(ROOT, "results", "es")
NEWS = os.path.join(os.path.dirname(__file__), "news_calendar.csv")
TICK, TICK_USD, COMM, SLIP_T = 0.25, 12.5, 4.5, 1.0
COST_T = SLIP_T + COMM / TICK_USD           # coste por contrato en ticks


def load():
    files = sorted(glob.glob(os.path.join(RAW, "*.csv")))
    df = pd.concat(pd.read_csv(f, sep=";", header=None, names=["dt", "o", "h", "l", "c", "v"])
                   for f in files)
    ts = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S")
    df.index = ts.dt.tz_localize("Etc/GMT+5").dt.tz_convert("America/New_York").dt.tz_localize(None)
    df = df[~df.index.duplicated()].sort_index()[["o", "h", "l", "c"]]
    return df


def trend_series(df):
    """Varias definiciones de tendencia, evaluadas en cada minuto sin mirar al futuro."""
    c5 = df["c"].resample("5min").last().dropna()
    ema5 = c5.ewm(span=50, adjust=False).mean()
    ema5 = ema5.shift(1).reindex(df.index, method="ffill")      # solo velas 5m cerradas
    c60 = df["c"].resample("60min").last().dropna()
    ema60 = c60.ewm(span=20, adjust=False).mean().shift(1).reindex(df.index, method="ffill")
    tday = (df.index + pd.Timedelta(hours=6)).normalize()
    globex_open = df["o"].groupby(tday).transform("first")
    daily = df["c"].groupby(tday).last()
    dopen = df["o"].groupby(tday).first()
    prev_dir = np.sign(daily - dopen).shift(1)
    prev = pd.Series(prev_dir.reindex(tday).to_numpy(), index=df.index)
    # temporalidad de 3 minutos (solo velas ya cerradas)
    o3 = df["o"].resample("3min").first().dropna()
    c3 = df["c"].resample("3min").last().dropna()
    def on_1m(s):
        return s.shift(1).reindex(df.index, method="ffill")
    e9, e20, e50 = (c3.ewm(span=n, adjust=False).mean() for n in (9, 20, 50))
    cross = on_1m(np.sign(e9 - e20))
    last3 = on_1m(np.sign(c3 - o3))
    return {
        "EMA20 3m": on_1m(e20), "EMA9 3m": on_1m(e9), "EMA50 3m": on_1m(e50),
        "Cruce EMA9/20 3m": cross, "Vela 3m anterior": last3,
        "EMA50 5m": ema5, "EMA20 1h": ema60, "Apertura Globex": globex_open,
        "Vela diaria anterior": prev,
    }


SIGN_TRENDS = {"Vela diaria anterior", "Cruce EMA9/20 3m", "Vela 3m anterior"}


def day_paths(df, entry_hm, tz="America/New_York"):
    """Para cada día: precio de entrada (hora `entry_hm` en la zona `tz`) y
    trayectoria hasta las 15:59 de Nueva York."""
    hh, mm = map(int, entry_hm.split(":"))
    out = []
    for d, g in df.groupby(df.index.normalize()):
        if d.weekday() >= 5:
            continue
        t0 = (pd.Timestamp(d.date()).tz_localize(tz) + pd.Timedelta(hours=hh, minutes=mm)) \
            .tz_convert("America/New_York").tz_localize(None)
        if t0 not in g.index:
            continue
        g2 = g.loc[t0:d + pd.Timedelta(hours=15, minutes=59)]
        if len(g2) < 30:
            continue
        out.append((d.date(), t0, g2))
    return out


def first_hit(cum, level):
    """Primer índice donde la serie monótona creciente `cum` alcanza `level`."""
    i = np.searchsorted(cum, level - 1e-9, side="left")
    return i if i < len(cum) else None


def simulate(entry, side, h, l, c, sl_t, tp1_t, tp2_t, be=True):
    """Resultado en ticks (suma de 2 contratos, sin costes) y detalle."""
    if side > 0:
        fav, adv = (h - entry) / TICK, (entry - l) / TICK
    else:
        fav, adv = (entry - l) / TICK, (h - entry) / TICK
    cf, ca = np.maximum.accumulate(fav), np.maximum.accumulate(adv)
    i_sl = first_hit(ca, sl_t)
    last = (c[-1] - entry) / TICK * side

    def leg(tp_t):
        i_tp = first_hit(cf, tp_t)
        if i_sl is not None and (i_tp is None or i_sl <= i_tp):
            return -sl_t, i_sl, "SL"
        if i_tp is not None:
            return tp_t, i_tp, "TP"
        return last, len(c) - 1, "CIERRE"

    r1, i1, e1 = leg(tp1_t)
    if tp2_t is None:
        return r1, r1, e1, e1
    r2, i2, e2 = leg(tp2_t)
    if be and e1 == "TP" and not (e2 == "TP" and i2 == i1):
        # tras TP1 el stop del 2º contrato pasa a la entrada
        k = i1 + 1
        if k < len(c):
            cf2 = np.maximum.accumulate(fav[k:])
            ca2 = np.maximum.accumulate(adv[k:])
            j_tp, j_be = first_hit(cf2, tp2_t), first_hit(ca2, 0.0)
            if j_be is not None and (j_tp is None or j_be <= j_tp):
                r2, e2 = 0.0, "BE"
            elif j_tp is not None:
                r2, e2 = tp2_t, "TP"
            else:
                r2, e2 = last, "CIERRE"
    return r1 + r2, r1, e1, e2


def stats(pnl_usd, wins):
    pnl = np.asarray(pnl_usd, float)
    if not len(pnl):
        return {}
    eq = np.cumsum(pnl)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    streak = run = 0
    for x in pnl:
        run = run + 1 if x < 0 else 0
        streak = max(streak, run)
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    sd = pnl.std(ddof=1) if len(pnl) > 1 else 0
    t = float(pnl.mean() / sd * np.sqrt(len(pnl))) if sd else 0.0
    return dict(n=int(len(pnl)), t=t, winrate=float(np.mean(wins)), pf=float(gw / gl) if gl else None,
                net=float(pnl.sum()), avg=float(pnl.mean()), maxdd=float(-dd.min()),
                worst_streak=int(streak))


def run_model(paths, trends, tname, sl, tp1, tp2, be=True, contracts=2):
    rows = []
    tr = trends[tname]
    for d, t0, g in paths:
        e = g["o"].iloc[0]
        ref = tr.get(t0, np.nan)
        if np.isnan(ref):
            continue
        side = (1 if e > ref else -1) if tname not in SIGN_TRENDS else int(ref)
        if side == 0:
            continue
        h, l, c = g["h"].to_numpy(), g["l"].to_numpy(), g["c"].to_numpy()
        if tp2 is None:
            r, r1, e1, e2 = simulate(e, side, h, l, c, sl, tp1, None)
            nc = contracts
            ticks = r * nc
        else:
            ticks, r1, e1, e2 = simulate(e, side, h, l, c, sl, tp1, tp2, be)
            nc = 2
        usd = ticks * TICK_USD - nc * COST_T * TICK_USD
        rows.append(dict(date=d, side="LONG" if side > 0 else "SHORT", entry=e,
                         ticks=ticks, usd=usd, leg1=e1, leg2=e2))
    return pd.DataFrame(rows)


ZONES = {"NY": "America/New_York", "CDMX": "America/Mexico_City"}


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    trends = trend_series(df)
    full = {}
    for zk, tz in ZONES.items():
        print("=== zona", zk)
        full[zk] = run_zone(df, trends, tz, zk)
    meta = full["NY"].pop("meta")
    full["CDMX"].pop("meta")
    with open(os.path.join(OUT, "es_data.json"), "w") as f:
        json.dump(dict(meta=meta, zones=full), f, default=lambda o: None if o is None else float(o))


def run_zone(df, trends, tz, zk):
    news = pd.read_csv(NEWS)
    news_days = set(pd.to_datetime(news["date"]).dt.date)
    nfp_cpi = set(pd.to_datetime(news[news.event.isin(["NFP", "CPI"])]["date"]).dt.date)

    models = {"A": dict(time="9:00", sl=60, tp1=60, tp2=120),
              "B": dict(time="9:12", sl=30, tp1=30, tp2=60)}
    T = "EMA20 3m"
    data = {"meta": dict(start=str(df.index[0].date()), end=str(df.index[-1].date()),
                         tick_usd=TICK_USD, cost_ticks=round(COST_T, 2), trend=T),
            "models": {}}
    all_trades = []
    for key, m in models.items():
        paths = day_paths(df, m["time"], tz)
        tr = run_model(paths, trends, T, m["sl"], m["tp1"], m["tp2"])
        tr["model"] = key
        tr["win"] = tr["usd"] > 0
        tr["date"] = pd.to_datetime(tr["date"])
        tr["news"] = tr["date"].dt.date.isin(news_days)
        all_trades.append(tr)
        base = stats(tr["usd"], tr["win"])

        # ---- variantes del modelo (2 contratos TP1/TP2)
        variants = []
        mult = [0.5, 0.75, 1, 1.5, 2] if key == "A" else [0.5, 1, 1.5, 2, 3]
        for f_sl in mult:
            for f_tp in mult:
                sl, tp1, tp2 = m["sl"] * f_sl, m["tp1"] * f_tp, m["tp2"] * f_tp
                v = run_model(paths, trends, T, sl, tp1, tp2)
                s = stats(v["usd"], v["usd"] > 0)
                variants.append(dict(sl=sl, tp1=tp1, tp2=tp2, **s))
        for be in (False,):
            v = run_model(paths, trends, T, m["sl"], m["tp1"], m["tp2"], be=be)
            s = stats(v["usd"], v["usd"] > 0)
            variants.append(dict(sl=m["sl"], tp1=m["tp1"], tp2=m["tp2"], note="sin BE", **s))

        # ---- superficie 3D: 1 contrato, SL x TP simple
        sls = list(range(10, 130, 10)) if key == "A" else list(range(5, 65, 5))
        tps = list(range(20, 260, 20)) if key == "A" else list(range(10, 130, 10))
        surf_avg, surf_pf, surf_wr = [], [], []
        for tp in tps:
            ra, rp, rw = [], [], []
            for sl in sls:
                v = run_model(paths, trends, T, sl, tp, None, contracts=1)
                s = stats(v["usd"], v["usd"] > 0)
                ra.append(round(s["avg"], 2)); rp.append(round(s["pf"] or 0, 3))
                rw.append(round(s["winrate"], 4))
            surf_avg.append(ra); surf_pf.append(rp); surf_wr.append(rw)

        # ---- 1:1 vs 1:2 (1 contrato)
        rr = []
        for name, tp in [("1:1", m["sl"]), ("1:1.5", m["sl"] * 1.5), ("1:2", m["sl"] * 2), ("1:3", m["sl"] * 3)]:
            v = run_model(paths, trends, T, m["sl"], tp, None, contracts=1)
            s = stats(v["usd"], v["usd"] > 0)
            rr.append(dict(rr=name, sl=m["sl"], tp=tp, **s))

        # ---- definiciones de tendencia
        trend_cmp = []
        for tn in trends:
            v = run_model(paths, trends, tn, m["sl"], m["tp1"], m["tp2"])
            trend_cmp.append(dict(trend=tn, **stats(v["usd"], v["usd"] > 0)))

        # ---- patrones
        wd_names = ["Lun", "Mar", "Mié", "Jue", "Vie"]
        tr["wd"] = tr["date"].dt.weekday
        tr["wom"] = (tr["date"].dt.day - 1) // 7 + 1
        tr["month"] = tr["date"].dt.to_period("M").astype(str)

        def grp(col, labels=None):
            g = tr.groupby(col).agg(n=("usd", "size"), wr=("win", "mean"), net=("usd", "sum"),
                                    avg=("usd", "mean")).reset_index()
            if labels:
                g[col] = g[col].map(lambda x: labels[x])
            return g.rename(columns={col: "k"}).to_dict("records")

        tr["newsk"] = np.where(tr["date"].dt.date.isin(nfp_cpi), "NFP / CPI (8:30)",
                               np.where(tr["news"], "FOMC", "Sin noticia"))
        eq = tr[["date", "usd"]].copy()
        eq["eq"] = eq["usd"].cumsum()
        eq["dd"] = eq["eq"] - eq["eq"].cummax().clip(lower=0)
        data["models"][key] = dict(
            params=m, stats=base,
            stats_no_news=stats(tr.loc[~tr.news, "usd"], tr.loc[~tr.news, "win"]),
            equity=dict(date=eq["date"].dt.strftime("%Y-%m-%d").tolist(),
                        eq=eq["eq"].round(2).tolist(), dd=eq["dd"].round(2).tolist()),
            legs=tr.groupby(["leg1", "leg2"]).size().reset_index(name="n").to_dict("records"),
            weekday=grp("wd", dict(enumerate(wd_names))), weekofmonth=grp("wom", {i: f"Semana {i}" for i in range(1, 6)}),
            month=grp("month"), news=grp("newsk"), side=grp("side"),
            variants=variants, rr=rr, trends=trend_cmp,
            surface=dict(sl=sls, tp=tps, avg=surf_avg, pf=surf_pf, wr=surf_wr),
        )
    # combinado A + B
    allt = pd.concat(all_trades).sort_values("date")
    ce = allt.groupby("date")["usd"].sum().cumsum()
    data["combined"] = dict(stats=stats(allt["usd"], allt["win"]),
                            date=[d.strftime("%Y-%m-%d") for d in ce.index], eq=ce.round(2).tolist())
    allt.drop(columns=["wd", "wom", "month", "newsk"], errors="ignore").to_csv(
        os.path.join(OUT, f"es_trades_{zk}.csv"), index=False)
    for k in "AB":
        mm = data["models"][k]
        print(k, mm["stats"], "\n  sin noticias", mm["stats_no_news"])
        print("  RR", [(r["rr"], round(r["winrate"], 2), round(r["pf"], 2), round(r["net"])) for r in mm["rr"]])
        print("  trend", [(r["trend"], round(r["pf"], 2), round(r["net"])) for r in mm["trends"]])
        print("  weekday", [(r["k"], r["n"], round(r["wr"], 2), round(r["net"])) for r in mm["weekday"]])
        print("  wom", [(r["k"], r["n"], round(r["wr"], 2), round(r["net"])) for r in mm["weekofmonth"]])
        print("  news", [(r["k"], r["n"], round(r["wr"], 2), round(r["net"])) for r in mm["news"]])
        print("  legs", mm["legs"])
        best = sorted(mm["variants"], key=lambda r: -r["net"])[:5]
        print("  best variants", [(r["sl"], r["tp1"], r["tp2"], round(r["pf"], 2), round(r["net"])) for r in best])
    print("combined", data["combined"]["stats"])
    return data


if __name__ == "__main__":
    main()
