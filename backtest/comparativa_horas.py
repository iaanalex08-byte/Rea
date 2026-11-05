#!/usr/bin/env python3
"""Compara la entrada a mercado (cierre 14:00 o el que se indique, ej. 14:30) a varias horas (8 MES, TP 4 / SL 20.75, tendencia, cierre 14:00),
marca días de noticias y simula cuentas de fondeo (reglas tipo LucidFlex).

    python3 backtest/comparativa_horas.py backtest/datos
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid  # noqa: E402
import noticias as nw  # noqa: E402
import poc_backtest as pb  # noqa: E402

HORAS = ["08:30", "10:30", "11:00"]
TP, SL, TICK, K, COM = 4.0, 20.75, 0.25, 40.0, 9.92
CLOSE = 14 * 60


def trade(H, L, O, tm, i, d):
    e = round(O[i] / TICK) * TICK
    tp, sl = e + d * TP, e - d * SL
    mae = 0.0
    for k in range(i, len(H)):
        if tm[k] >= CLOSE:
            pnl = (O[k] - e) * d
            return "CIERRE", pnl, mae, e, k
        adv = (e - L[k]) if d == 1 else (H[k] - e)
        s = L[k] <= sl if d == 1 else H[k] >= sl
        t = H[k] >= tp if d == 1 else L[k] <= tp
        if s:
            return "PERDIDA", -SL, SL, e, k
        mae = max(mae, adv)
        if t:
            return "GANADA", TP, mae, e, k
    return "CIERRE", (O[-1] - e) * d, mae, e, len(H) - 1


def main():
    global CLOSE
    data = sys.argv[1] if len(sys.argv) > 1 else "backtest/datos"
    sufijo = ""
    if len(sys.argv) > 2:  # hora de cierre HH:MM
        hh, mm = map(int, sys.argv[2].split(":"))
        CLOSE = hh * 60 + mm
        sufijo = "_" + sys.argv[2].replace(":", "")
    a = pb.parse_args([data, "--tf", "1", "--prof-hour", "7", "--prof-dur", "30", "--win-end", "13:30"])
    df = pb.load_bars([data], a.input_tz, a.tz, 1, "auto")
    df = df[(df.index >= pd.Timestamp("2024-01-01", tz=a.tz)) & (df.index < pd.Timestamp("2026-11-05", tz=a.tz))]
    df, _ = pb.filter_days(df, a)
    news = {**{d: "FOMC" for d in nw.FOMC}}
    rows = []
    for day, g in df.groupby(df.index.date):
        tm = (g.index.hour * 60 + g.index.minute).to_numpy()
        if tm[0] != 0:
            continue
        pre = g[tm < 7 * 60]
        if pre.empty:
            continue
        trend = pre.close.iloc[-1] - g.open.iloc[0]
        if trend == 0:
            continue
        d = 1 if trend > 0 else -1
        H, L, O = g.high.to_numpy(), g.low.to_numpy(), g.open.to_numpy()
        ds = str(day)
        tags = [n for n, lst in (("FOMC", nw.FOMC), ("CPI", nw.CPI), ("NFP", nw.NFP), ("PPI", nw.PPI)) if ds in lst]
        for h in HORAS:
            hh, mm = map(int, h.split(":"))
            i = int(np.searchsorted(tm, hh * 60 + mm))
            if i >= len(g):
                continue
            res, pts, mae, e, k = trade(H, L, O, tm, i, d)
            rows.append({"hora": h, "date": ds, "anio": day.year, "dir": "COMPRA" if d == 1 else "VENTA",
                         "entry": e, "result": res, "pts": round(pts, 2), "usd": round(pts * K - COM, 2),
                         "mae_usd": round(mae * K + COM if res != "PERDIDA" else SL * K + COM, 2),
                         "noticia": "+".join(tags) if tags else "Sin noticia",
                         "fomc": "FOMC" in tags, "cpi": "CPI" in tags, "nfp": "NFP" in tags, "ppi": "PPI" in tags})
    t = pd.DataFrame(rows)
    out = Path("backtest/resultados")
    t.to_csv(out / f"comparativa_horas{sufijo}.csv", index=False)

    cfg = SimpleNamespace(dd=1000, lock=100, objetivo=1250, min_dia=150, dias=5, tope=1000, min_retiro=500, split=0.9)
    resumen, rachas, lucid_rows, news_rows = [], [], [], []
    for h in HORAS:
        g = t[t.hora == h].reset_index(drop=True)
        c = g.result.value_counts()
        w, l, cl = c.get("GANADA", 0), c.get("PERDIDA", 0), c.get("CIERRE", 0)
        eq = g.usd.cumsum()
        dd = (eq - eq.cummax().clip(lower=0)).min()
        # rachas
        best = worst = cur_w = cur_l = 0
        bstart = wstart = None
        s_w = s_l = None
        for k, r in enumerate(g.result):
            if r == "GANADA":
                cur_w += 1; s_w = s_w if cur_w > 1 else g.date[k]
                cur_l = 0
            elif r == "PERDIDA":
                cur_l += 1; s_l = s_l if cur_l > 1 else g.date[k]
                cur_w = 0
            if cur_w > best:
                best, bstart, bend = cur_w, s_w, g.date[k]
            if cur_l > worst:
                worst, wstart, wend = cur_l, s_l, g.date[k]
        # peor racha en dólares (máxima caída)
        dd_end = int((eq - eq.cummax()).idxmin())
        dd_start = int(eq[:dd_end + 1].idxmax()) if dd_end > 0 else 0
        resumen.append({"hora": h, "operaciones": len(g), "ganadas": w, "perdidas": l, "cierres_14": cl,
                        "acierto": round(w / (w + l), 4), "cierres_usd": round(g[g.result == "CIERRE"].usd.sum(), 2),
                        "neto_usd": round(g.usd.sum(), 2), "max_dd_usd": round(dd, 2),
                        "prob_5_tp_antes_sl": round((w / (w + l)) ** 5, 4)})
        rachas.append({"hora": h, "mejor_racha_ganadas": best, "mejor_desde": bstart, "mejor_hasta": bend,
                       "peor_racha_perdidas": worst, "peor_desde": wstart, "peor_hasta": wend,
                       "peor_caida_usd": round(dd, 2), "caida_desde": g.date[dd_start], "caida_hasta": g.date[dd_end]})
        days = list(zip(g.usd.to_numpy(), g.mae_usd.to_numpy()))
        runs = [lucid.account(days, s, cfg, False) for s in range(len(days))]
        runs = [r for r in runs if r is not None]
        n = np.array([r[2] for r in runs]); cob = np.array([r[1] for r in runs])
        lucid_rows.append({"hora": h, "cuentas_con_retiro": round(np.mean(n >= 1), 4),
                           "cuentas_2_retiros": round(np.mean(n >= 2), 4), "cobro_promedio_fondeada": round(cob.mean(), 2),
                           "roi_eval_50": round((0.5 * cob.mean() - 45) / 45, 4)})
        for tag in ["Sin noticia", "FOMC", "CPI", "NFP", "PPI"]:
            sub = g[g.noticia == "Sin noticia"] if tag == "Sin noticia" else g[g[tag.lower()]]
            cc = sub.result.value_counts()
            ww, ll = cc.get("GANADA", 0), cc.get("PERDIDA", 0)
            news_rows.append({"hora": h, "noticia": tag, "dias": len(sub), "ganadas": ww, "perdidas": ll,
                              "cierres_14": cc.get("CIERRE", 0), "acierto": round(ww / (ww + ll), 4) if ww + ll else None,
                              "neto_usd": round(sub.usd.sum(), 2)})
    R, RA, LU, NE = map(pd.DataFrame, (resumen, rachas, lucid_rows, news_rows))
    for name, x in (("resumen_horas", R), ("rachas_horas", RA), ("lucid_horas", LU), ("noticias_horas", NE)):
        x.to_csv(out / f"{name}{sufijo}.csv", index=False)
    pd.set_option("display.width", 250)
    for x in (R, RA, LU, NE):
        print(x.to_string(index=False)); print()
    print("Por año:")
    print(t.groupby(["hora", "anio"]).apply(lambda s: pd.Series({
        "ops": len(s), "acierto": round(100 * (s.result == "GANADA").sum() / s.result.isin(["GANADA", "PERDIDA"]).sum(), 1),
        "neto": round(s.usd.sum())})).to_string())


if __name__ == "__main__":
    main()
