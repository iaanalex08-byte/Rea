#!/usr/bin/env python3
"""Estrategia D (primer extremo de la noche que rompe NY, SL 40, hasta las 16:00 ET) junto a tus estrategias.

  A) POC 8:30 contra Londres · B) POC 10:30 con tendencia · C) SMC 5 min desde la apertura de NY · D) nueva.
Reglas de convivencia:
  "una a la vez": nunca dos posiciones abiertas (la primera manda).
  "D en paralelo": D puede estar abierta junto con otra si van en la MISMA dirección; si va en contra, la otra se omite.
Se mide correlación, choques y Lucid 25K Flex (evaluación y primer retiro de la fondeada).

    python3 backtest/cuatro_estrategias.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lucid_flex25k as L  # noqa: E402
import retiro_rapido as rr  # noqa: E402
from apertura_ny_fvg import load  # noqa: E402

PV, COM, COST = 2.0, 1.24, 1.0


def d_trades(nq):
    out = []
    for d, g in nq.groupby(nq.index.date):
        t = (g.index.hour * 60 + g.index.minute).to_numpy()
        r = g[(t >= 570) & (t < 960)]
        if len(r) < 370:
            continue
        on = g[t < 570]
        if not len(on):
            continue
        onh, onl = on.high.max(), on.low.min()
        O, H, Lw, C = r.open.values, r.high.values, r.low.values, r.close.values
        tr = None
        for i in range(len(O)):
            if H[i] > onh and Lw[i] < onl:
                break
            if H[i] > onh:
                tr = (i, 1, max(onh, O[i])); break
            if Lw[i] < onl:
                tr = (i, -1, min(onl, O[i])); break
        if not tr or tr[0] > 180:
            continue
        i0, s, e = tr
        sl = e - s * 40; out_pts, k_exit, mae = None, len(O) - 1, 0.0
        for k in range(i0 + 1, len(O)):
            mae = max(mae, (e - (Lw[k] if s == 1 else H[k])) * s)
            if (Lw[k] <= sl) if s == 1 else (H[k] >= sl):
                out_pts, k_exit = -40.0, k; break
        if out_pts is None:
            out_pts = (C[-1] - e) * s
        out.append({"est": "D", "date": r.index[i0].tz_convert("Etc/GMT+6").date(), "entry": r.index[i0].tz_convert("UTC"),
                    "exit": r.index[k_exit].tz_convert("UTC"), "dir": s, "pts": out_pts - COST, "mae": min(mae, 40) + COST})
    return pd.DataFrame(out)


def main():
    nq = load("backtest/datos_NQ")
    D = d_trades(nq)
    poc = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry", "exit"])
    poc = poc[poc.est != "C SMC"].assign(est=lambda x: x.est.map({"A 8:30": "A", "B 10:30": "B"}))
    poc["entry"] = pd.to_datetime(poc.entry, utc=True); poc["exit"] = pd.to_datetime(poc.exit, utc=True)
    poc["date"] = pd.to_datetime(poc.date).dt.date
    smc = rr.smc_ops(570); smc["est"] = "C"
    import smc_mss as sm  # dirección de la SMC
    from apertura_ny_fvg import resample
    s_raw = sm.run(resample(nq, 5), 180, "FVG", False, "nuevo extremo", 1.0, entry_from=570)
    smc["dir"] = s_raw.side.values
    T = pd.concat([poc[["est", "date", "entry", "exit", "dir", "pts", "mae"]], smc[["est", "date", "entry", "exit", "dir", "pts", "mae"]],
                   D[["est", "date", "entry", "exit", "dir", "pts", "mae"]]], ignore_index=True).sort_values("entry").reset_index(drop=True)
    y = pd.to_datetime(pd.Series(D.date)).dt.year
    print(f"D sola: {len(D)} ops · acierto {100 * (D.pts > 0).mean():.1f}% · pts/op 24-25 {D.pts[y <= 2025].mean():+.1f} · 2026 {D.pts[y == 2026].mean():+.1f}")
    dp = T.pivot_table(index="date", columns="est", values="pts", aggfunc="sum").fillna(0)
    print("\nCorrelación diaria:"); print(dp.corr().round(2).to_string())
    for e in ("A", "B", "C"):
        m = T[T.est == e].merge(D, on="date", suffixes=("", "_d"))
        ov = (m.entry < m.exit_d) & (m.exit > m.entry_d)
        print(f"Choques con {e}: {len(m)} días con ambas · abiertas a la vez {int(ov.sum())} · misma dirección {int((ov & (m.dir == m.dir_d)).sum())}")
    allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)

    def select(ests, rule):
        t = T[T.est.isin(ests)]
        keep, open_ = [], []  # open_: lista de (exit, est, dir)
        for r in t.itertuples():
            open_ = [o for o in open_ if o[0] > r.entry]
            if open_:
                if rule == "D en paralelo" and all((r.est == "D" or o[1] == "D") and o[2] == r.dir for o in open_) and len(open_) == 1:
                    pass
                else:
                    continue
            keep.append(r.Index); open_.append((r.exit, r.est, r.dir))
        return t.loc[keep]

    def days_of(t, k):
        g = {d: [] for d in allday}
        for r in t.itertuples():
            q = k.get(r.est, 1)
            g[r.date].append((r.est, (r.pts * PV - COM) * q, (r.mae * PV + COM) * q))
        return [g[d] for d in allday]

    rows = []
    plans = [("D sola ×1", ["D"], {"D": 1}, "una a la vez"), ("D sola ×2", ["D"], {"D": 2}, "una a la vez"),
             ("B ×1", ["B"], {"B": 1}, "una a la vez"), ("B + D ×1", ["B", "D"], {}, "una a la vez"),
             ("B + D ×1 (D en paralelo)", ["B", "D"], {}, "D en paralelo"),
             ("A + B + C ×1 (plan actual)", ["A", "B", "C"], {}, "una a la vez"),
             ("A + B + C + D ×1", ["A", "B", "C", "D"], {}, "una a la vez"),
             ("A + B + C + D ×1 (D en paralelo)", ["A", "B", "C", "D"], {}, "D en paralelo")]
    for name, ests, k, rule in plans:
        t = select(ests, rule)
        days = days_of(t, k)
        u = np.array([sum(p for _, p, _ in o) for o in days])
        eq = u.cumsum()
        DD = [(sum(p for _, p, _ in o), sum(m for _, _, m in o)) for o in days]
        ev = [(s, L.evaluacion(DD, s)) for s in range(len(DD))]
        ev = [(s, r) for s, r in ev if r[0] is not None]
        res = [rr.sim(days, lambda b, e: 1, s) for s in range(0, len(days) - 120)]
        res = [x for x in res if x[0] is not None]; ok = [x[1] for x in res if x[0]]
        rows.append({"plan": name, "ops": len(t), "neto 3 años $": round(u.sum()), "caída máx $": round((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
                     "peor día $": round(u.min()), "eval pasa %": round(100 * np.mean([r[0] for _, r in ev]), 1),
                     "eval días": float(np.median([r[1] for _, r in ev if r[0]])), "1er retiro %": round(100 * np.mean([x[0] for x in res]), 1),
                     "días 1er retiro": float(np.median(ok)) if ok else None})
    pd.set_option("display.width", 230)
    print(); print(pd.DataFrame(rows).to_string(index=False))
    D.to_csv("backtest/resultados/estrategia_d_ops.csv", index=False)


if __name__ == "__main__":
    main()
