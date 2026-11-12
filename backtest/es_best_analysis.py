"""Análisis de la combinación "Mejor" del modelo B (9:12 CDMX, EMA20 3m):
SL 15 · TP1 55 · TP2 110 ticks, 2 contratos con break-even tras TP1.

Incluye: métricas (con mejor y peor racha), patrones por día y por condición
de mercado, consistencia de cada patrón en 2025 y 2026 por separado, y la
prueba de filtros para ver si alguno mejora el sistema en los dos años.

    python backtest/es_best_analysis.py  ->  results/es/analisis_B_CDMX_15_55_110/
"""
import itertools
import json
import os

import numpy as np
import pandas as pd

from es_backtest import COST_T, NEWS, ROOT, TICK, TICK_USD, day_paths, load, trend_series
from es_analysis_config import trade_detail

CFG = dict(name="B_CDMX_15_55_110", time="9:12", tz="America/Mexico_City", trend="EMA20 3m",
           sl=15, tp1=55, tp2=110)
OUT = os.path.join(ROOT, "results", "es", "analisis_" + CFG["name"])


def streaks(usd):
    best = worst = run_w = run_l = 0
    for v in usd:
        run_w = run_w + 1 if v > 0 else 0
        run_l = run_l + 1 if v < 0 else 0
        best, worst = max(best, run_w), max(worst, run_l)
    return best, worst


def stats(usd):
    usd = np.asarray(usd, float)
    if len(usd) < 2:
        return dict(n=len(usd))
    eq = np.cumsum(usd)
    dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
    best, worst = streaks(usd)
    gw, gl = usd[usd > 0].sum(), -usd[usd < 0].sum()
    sd = usd.std(ddof=1)
    return dict(n=int(len(usd)), winrate=float((usd > 0).mean()), pf=float(gw / gl) if gl else None,
                net=float(usd.sum()), avg=float(usd.mean()), maxdd=float(-dd.min()),
                best_streak=int(best), worst_streak=int(worst),
                t=float(usd.mean() / sd * np.sqrt(len(usd))) if sd else 0.0)


def build_trades():
    df = load()
    tr = trend_series(df)[CFG["trend"]]
    ema3 = tr
    news = pd.read_csv(NEWS)
    cat = dict(zip(pd.to_datetime(news.date).dt.date,
                   news.event.map(lambda e: "NFP/CPI 8:30" if e in ("NFP", "CPI") else "FOMC")))
    rth = df.between_time("09:30", "15:59")
    day = rth.index.normalize()
    rth_open = rth["o"].groupby(day).first()
    rth_close = rth["c"].groupby(day).last()
    rng = rth["h"].groupby(day).max() - rth["l"].groupby(day).min()
    prev_close, prev_rng = rth_close.shift(1), rng.shift(1)
    prev_dir = np.sign(rth_close - rth_open).shift(1)

    rows = []
    for d, t0, g in day_paths(df, CFG["time"], CFG["tz"]):
        ref = ema3.get(t0, np.nan)
        if np.isnan(ref):
            continue
        e = g["o"].iloc[0]
        side = 1 if e > ref else -1
        det = trade_detail(e, side, g, CFG["sl"], CFG["tp1"], CFG["tp2"])
        usd = det["ticks"] * TICK_USD - 2 * COST_T * TICK_USD
        D = pd.Timestamp(d)
        o930, pc = rth_open.get(D, np.nan), prev_close.get(D, np.nan)
        rows.append(dict(
            date=D, entry_ny=t0.strftime("%H:%M"), side="Compra" if side > 0 else "Venta", usd=round(usd, 2),
            outcome=det["outcome"], mins=det["mins"],
            news=cat.get(d, "Sin noticia"),
            prev_range=prev_rng.get(D, np.nan),
            gap_ticks=(o930 - pc) / TICK * side if not np.isnan(o930) and not np.isnan(pc) else np.nan,
            morning_ticks=(e - o930) / TICK * side if not np.isnan(o930) else np.nan,
            prevday_aligned=(prev_dir.get(D, 0) * side) > 0,
            ema_dist_ticks=abs(e - ref) / TICK,
        ))
    t = pd.DataFrame(rows)
    t["win"] = (t.usd > 0).astype(int)
    t["year"] = t.date.dt.year
    t["weekday"] = t.date.dt.weekday.map(dict(enumerate(["Lun", "Mar", "Mié", "Jue", "Vie"])))
    t["wom"] = "Semana " + ((t.date.dt.day - 1) // 7 + 1).astype(str)
    t["month_name"] = t.date.dt.month.map(dict(enumerate(
        ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"], start=1)))
    t["horario_ny"] = np.where(t.entry_ny == "10:12", "10:12 NY (invierno)", "11:12 NY (verano)")
    t["vol"] = pd.qcut(t.prev_range, 3, labels=["Baja", "Media", "Alta"]).astype(str).replace("nan", "")
    t["gap"] = np.select([t.gap_ticks > 20, t.gap_ticks < -20], ["A favor (>5 pts)", "En contra (>5 pts)"], "Pequeño (±5 pts)")
    t["manana"] = np.select([t.morning_ticks > 40, t.morning_ticks < -40], ["A favor (>10 pts)", "En contra (>10 pts)"], "Lateral (±10 pts)")
    t["dia_anterior"] = np.where(t.prevday_aligned, "Mismo sentido", "Sentido contrario")
    t["dist_ema"] = pd.qcut(t.ema_dist_ticks, 3, labels=["Cerca de la EMA", "Media", "Lejos de la EMA"]).astype(str)
    return t


DIMS = {
    "Día de la semana": "weekday", "Semana del mes": "wom", "Mes": "month_name",
    "Horario en NY": "horario_ny", "Volatilidad día anterior": "vol", "Noticias": "news",
    "Lado": "side", "Gap de apertura vs operación": "gap", "Movimiento 9:30 → entrada": "manana",
    "Día anterior vs operación": "dia_anterior", "Distancia a la EMA 20 (3m)": "dist_ema",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    t = build_trades()
    base = stats(t.usd)
    by_year = {y: stats(t.loc[t.year == y, "usd"]) for y in (2025, 2026)}

    # ---- patrones y su consistencia por año
    pats = []
    for dim, col in DIMS.items():
        for k, g in t[t[col] != ""].groupby(col):
            s = stats(g.usd)
            y25, y26 = g[g.year == 2025].usd, g[g.year == 2026].usd
            a25 = y25.mean() if len(y25) else np.nan
            a26 = y26.mean() if len(y26) else np.nan
            better25 = a25 > by_year[2025]["avg"]
            better26 = a26 > by_year[2026]["avg"]
            verdict = ("Mejor en los dos años" if better25 and better26 else
                       "Peor en los dos años" if (not better25 and not better26) else "Cambia según el año")
            pats.append(dict(clave=f"{dim}|{k}", dim=dim, k=k, n=s["n"], winrate=s.get("winrate"), pf=s.get("pf"),
                             net=s.get("net"), avg=s.get("avg"), best_streak=s.get("best_streak"),
                             worst_streak=s.get("worst_streak"),
                             wr25=float((y25 > 0).mean()) if len(y25) else None,
                             wr26=float((y26 > 0).mean()) if len(y26) else None,
                             avg25=float(a25) if len(y25) else None, avg26=float(a26) if len(y26) else None,
                             consistencia=verdict))
    pats = pd.DataFrame(pats)

    # ---- filtros: quitar un grupo "Peor en los dos años" (con al menos 30 operaciones)
    cands = pats[(pats.consistencia == "Peor en los dos años") & (pats.n >= 30)]
    filters = [dict(nombre="Sin filtro (todas)", mask=np.ones(len(t), bool))]
    for _, r in cands.iterrows():
        col = DIMS[r.dim]
        filters.append(dict(nombre=f"Sin {r.dim.lower()}: {r.k}", mask=(t[col] != r.k).to_numpy()))
    # combinaciones de dos filtros
    singles = filters[1:]
    for a, b in itertools.combinations(singles, 2):
        filters.append(dict(nombre=a["nombre"] + " + " + b["nombre"].split(": ", 1)[0].replace("Sin ", "sin ") + ": " + b["nombre"].split(": ", 1)[1],
                            mask=a["mask"] & b["mask"]))
    frows = []
    for f in filters:
        sub = t[f["mask"]]
        s = stats(sub.usd)
        s25, s26 = stats(sub[sub.year == 2025].usd), stats(sub[sub.year == 2026].usd)
        frows.append(dict(filtro=f["nombre"], n=s["n"], pct_dias=s["n"] / len(t), winrate=s["winrate"], pf=s["pf"],
                          net=s["net"], avg=s["avg"], maxdd=s["maxdd"], best_streak=s["best_streak"],
                          worst_streak=s["worst_streak"], t=s["t"], avg25=s25["avg"], avg26=s26["avg"],
                          pf25=s25["pf"], pf26=s26["pf"]))
    frows = pd.DataFrame(frows).sort_values("t", ascending=False)

    # ---- curva con el filtro mejor (por t) para comparar
    best_f = frows.iloc[0].filtro if frows.iloc[0].filtro != "Sin filtro (todas)" else frows.iloc[1].filtro
    bm = next(f["mask"] for f in filters if f["nombre"] == best_f)
    t["en_mejor_filtro"] = bm.astype(int)

    t.to_csv(os.path.join(OUT, "operaciones_completo.csv"), index=False)
    t2 = t.copy()
    t2["date"] = t2.date.dt.strftime("%Y-%m-%d")
    t2[["date", "entry_ny", "side", "usd", "win", "outcome", "mins", "news", "horario_ny", "vol", "weekday", "wom",
        "month_name", "year", "gap", "manana", "dia_anterior", "dist_ema", "en_mejor_filtro"]] \
        .to_csv(os.path.join(OUT, "mejor_operaciones.csv"), index=False)
    pats.round(4).to_csv(os.path.join(OUT, "mejor_patrones.csv"), index=False)
    frows.round(4).to_csv(os.path.join(OUT, "mejor_filtros.csv"), index=False)
    with open(os.path.join(OUT, "resumen.json"), "w") as f:
        json.dump(dict(cfg=CFG, base=base, by_year=by_year, best_filter=best_f), f, indent=1, default=float)
    return t, base, by_year, pats, frows, best_f


if __name__ == "__main__":
    t, base, by_year, pats, frows, best_f = main()
    print("BASE", {k: round(v, 3) if isinstance(v, float) else v for k, v in base.items()})
    for y, s in by_year.items():
        print(y, {k: round(v, 3) if isinstance(v, float) else v for k, v in s.items()})
    pd.set_option("display.width", 220)
    print(pats.sort_values("winrate", ascending=False)[["dim", "k", "n", "winrate", "avg", "avg25", "avg26", "consistencia"]].head(20).to_string())
    print(pats[pats.consistencia != "Cambia según el año"][["dim", "k", "n", "winrate", "avg", "avg25", "avg26", "consistencia"]].to_string())
    print(frows.head(12)[["filtro", "n", "winrate", "pf", "net", "avg", "maxdd", "t", "avg25", "avg26"]].to_string())
    print("mejor filtro:", best_f)


def walk_forward(t):
    """Elige filtros con 2025 y los prueba en 2026 (que el filtro no vio)."""
    tr25, tr26 = t[t.year == 2025], t[t.year == 2026]
    base25, base26 = tr25.usd.mean(), tr26.usd.mean()
    groups = []
    for dim, col in DIMS.items():
        if col == "month_name":
            continue  # un mes de 2025 no dice nada de 2026 con tan pocos datos
        for k, g in tr25[tr25[col] != ""].groupby(col):
            if len(g) >= 25:
                groups.append((g.usd.mean() - base25, dim, col, k, len(g)))
    groups.sort()
    rows = [dict(paso="Sin filtro", filtros="—", n26=len(tr26), avg26=base26, wr26=(tr26.usd > 0).mean(),
                 pf26=tr26.usd[tr26.usd > 0].sum() / -tr26.usd[tr26.usd < 0].sum(), net26=tr26.usd.sum())]
    mask = np.ones(len(tr26), bool)
    names = []
    for i, (diff, dim, col, k, n) in enumerate(groups[:3]):
        mask &= (tr26[col] != k).to_numpy()
        names.append(f"{dim}: {k}")
        s = tr26[mask].usd
        rows.append(dict(paso=f"Quitar {i + 1} peor{'es' if i else ''} de 2025", filtros=" · ".join(names), n26=len(s),
                         avg26=s.mean(), wr26=(s > 0).mean(), pf26=s[s > 0].sum() / -s[s < 0].sum(), net26=s.sum()))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    wf = walk_forward(t)
    wf.round(4).to_csv(os.path.join(OUT, "mejor_fuera_muestra.csv"), index=False)
    print(wf.to_string())
