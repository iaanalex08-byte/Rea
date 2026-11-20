#!/usr/bin/env python3
"""¿Qué se le puede agregar al POC 10:30 del NQ? Filtros sacados de todo lo probado.

Operaciones base: perfil 10:30-10:42 CDMX (UTC-6), 3 min, SL 66.5, 1:1, salida única, cierre 14:30.
Cada filtro se evalúa en 2024-2025 y en 2026 por separado: solo sirve si mejora el R por operación en los dos.

    python3 backtest/mejoras_1030.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as c  # noqa: E402
import poc_backtest as pb  # noqa: E402

SL = 66.5


def main():
    b = c.trades(c.BASE)  # incluye cierre 14:30 y deslizamiento
    a = pb.parse_args(["backtest/datos_NQ", "--prof-hour", "10", "--prof-min", "30", "--win-start", "10:42",
                                   "--sl", "66.5", "--rr", "1", "--single"])
    df3 = c.bars(3)
    d, _ = pb.filter_days(df3, a)
    raw, _ = pb.run(d, a)
    raw = raw.set_index("date")
    b = b.set_index("date")
    b["trend_pts"] = raw.trend_pts.reindex(b.index)
    b["prof_range"] = raw.prof_range.reindex(b.index)
    b["espera_min"] = ((raw.entry_time - raw.brk_time).dt.total_seconds() / 60).reindex(b.index)
    b = b.reset_index()
    tm = df3.index.hour * 60 + df3.index.minute
    dates = df3.index.date
    day = df3.groupby(dates).agg(h=("high", "max"), l=("low", "min"))
    prev_rng = (day.h - day.l).shift(1)
    o0 = df3[tm == 0].groupby(dates[tm == 0]).open.first()
    lc = df3[tm < 360].groupby(dates[tm < 360]).close.last()
    lon = df3[tm < 360].groupby(dates[tm < 360]).agg(lh=("high", "max"), ll=("low", "min"))
    asia = df3[tm >= 18 * 60].copy(); asia_key = (asia.index + pd.Timedelta(days=1)).date
    ag = asia.groupby(asia_key).agg(ah=("high", "max"), al=("low", "min"))
    c15 = df3.close.resample("15min").last().dropna()
    e20, e50 = c15.ewm(span=20, adjust=False).mean(), c15.ewm(span=50, adjust=False).mean()
    # VWAP de la sesión desde las 7:30 CDMX
    rth = df3[(tm >= 450)]
    tp_ = (rth.high + rth.low + rth.close) / 3
    vw = (tp_ * rth.volume).groupby(rth.index.date).cumsum() / rth.volume.groupby(rth.index.date).cumsum()
    feats = []
    for r in b.itertuples():
        dd, side = r.date, r.dir
        e = pd.Timestamp(r.entry)
        k15 = c15.index.searchsorted(e) - 1
        v = vw.asof(e) if e >= vw.index[0] else np.nan
        px = df3.close.asof(e)
        g = df3[(dates == dd) & (tm >= 450) & (tm < 630)]  # 7:30-10:30
        ny_h, ny_l = (g.high.max(), g.low.min()) if len(g) else (np.nan, np.nan)
        swept_low = ny_l < min(lon.ll.get(dd, np.inf), ag.al.get(dd, np.inf))
        swept_high = ny_h > max(lon.lh.get(dd, -np.inf), ag.ah.get(dd, -np.inf))
        feats.append({
            "londres_a_favor": -np.sign(lc.get(dd, np.nan) - o0.get(dd, np.nan)) == side,  # 'contra Londres' coincide
            "ema15_a_favor": (1 if e20.iloc[k15] > e50.iloc[k15] else -1) == side,
            "vwap_a_favor": np.sign(px - v) == side if not np.isnan(v) else np.nan,
            "barrida_previa_a_favor": (swept_low and not swept_high) if side == 1 else (swept_high and not swept_low),
            "barrida_en_contra": (swept_high and not swept_low) if side == 1 else (swept_low and not swept_high),
            "rango_prev": prev_rng.get(dd, np.nan),
            "verano": e.tz_convert("America/New_York").utcoffset() == pd.Timedelta(hours=-4),
            "dow": pd.Timestamp(dd).dayofweek,
            "hora_entrada": e.tz_convert("Etc/GMT+6").hour + e.tz_convert("Etc/GMT+6").minute / 60,
        })
    F = pd.concat([b.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    F["y"] = pd.to_datetime(F.date).dt.year
    F["tend_abs"] = F.trend_pts.abs()
    F.to_csv("backtest/resultados/mejoras_1030_ops.csv", index=False)

    def rep(name, mask):
        mask = mask.fillna(False).astype(bool)
        out = {"filtro": name, "ops": int(mask.sum())}
        for per, sel in (("24-25", F.y <= 2025), ("2026", F.y == 2026)):
            k = F[mask & sel]
            out[f"acierto {per}"] = round(100 * (k.R > 0).mean(), 1) if len(k) else np.nan
            out[f"R/op {per}"] = round(k.R.mean(), 3) if len(k) else np.nan
        out["R total"] = round(F[mask].R.sum(), 1)
        return out

    base = rep("BASE (todas)", pd.Series(True, index=F.index))
    rows = [base]
    q = lambda col, p: F[col] >= F[col].quantile(p)
    tests = {
        "Londres coincide (contra Londres = misma dirección)": F.londres_a_favor,
        "Londres NO coincide": ~F.londres_a_favor,
        "EMA 20/50 de 15 min a favor": F.ema15_a_favor,
        "VWAP (desde 7:30) a favor": F.vwap_a_favor == True,
        "Barrida de Asia/Londres a favor antes de 10:30": F.barrida_previa_a_favor,
        "Sin barrida en contra": ~F.barrida_en_contra,
        "Tendencia 00:00->10:30 fuerte (mitad superior)": q("tend_abs", 0.5),
        "Tendencia débil (mitad inferior)": ~q("tend_abs", 0.5),
        "Perfil ancho (mitad superior)": q("prof_range", 0.5),
        "Perfil angosto (mitad inferior)": ~q("prof_range", 0.5),
        "Retroceso rápido (<= 15 min tras ruptura)": F.espera_min <= 15,
        "Retroceso lento (> 15 min)": F.espera_min > 15,
        "Entrada antes de 11:30": F.hora_entrada < 11.5,
        "Entrada desde 11:30": F.hora_entrada >= 11.5,
        "Rango del día anterior alto (mitad superior)": q("rango_prev", 0.5),
        "Sin lunes": F.dow != 0,
        "Solo mié-jue-vie": F.dow >= 2,
        "Solo compras": F.dir == 1,
        "Solo ventas": F.dir == -1,
    }
    for n, m in tests.items():
        rows.append(rep(n, m))
    T = pd.DataFrame(rows)
    T["mejora en ambos"] = (T["R/op 24-25"] > base["R/op 24-25"]) & (T["R/op 2026"] > base["R/op 2026"])
    pd.set_option("display.width", 230)
    print(T.to_string(index=False))
    # combinaciones de los que mejoran en ambos
    good = [n for n, ok in zip(T.filtro, T["mejora en ambos"]) if ok]
    print("\nMejoran en ambos periodos:", good)
    from itertools import combinations
    combo = []
    for k in (2, 3):
        for cs in combinations(good, k):
            m = np.logical_and.reduce([tests[x].fillna(False).astype(bool) for x in cs])
            r = rep(" + ".join(cs), pd.Series(m, index=F.index))
            if r["ops"] >= 100:
                combo.append(r)
    if combo:
        C = pd.DataFrame(combo).sort_values("R total", ascending=False)
        print("\nCombinaciones (>= 100 ops):"); print(C.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
