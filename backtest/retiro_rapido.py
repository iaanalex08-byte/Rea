#!/usr/bin/env python3
"""Cómo llegar más rápido al primer retiro de Lucid 25K Flex con la SMC (entradas desde 9:30 ET).

Primer retiro: 5 días de >= $100 y ganancia >= $1,000. Drawdown $1,000 al cierre del día (se fija en +$100).
Se comparan tamaños fijos, tamaño que cambia según el colchón, y sumar las otras estrategias.

    python3 backtest/retiro_rapido.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

PV, COM, DD, LOCK = 2.0, 1.24, 1000.0, 100.0


def smc_ops(entry_from):
    nq1 = load("backtest/datos_NQ")
    s = sm.run(resample(nq1, 5), 180, "FVG", False, "nuevo extremo", 1.0, entry_from=entry_from)
    out = []
    for r in s.itertuples():
        w = nq1.loc[r.entry_time:r.exit_time]
        ref = w.close.iloc[0] if len(w) else np.nan
        adv = (w.high.max() - ref) if r.side == -1 else (ref - w.low.min())
        out.append({"est": "SMC", "date": r.entry_time.tz_convert("Etc/GMT+6").date(), "entry": r.entry_time.tz_convert("UTC"),
                    "exit": r.exit_time.tz_convert("UTC"), "pts": r.R * r.risk,
                    "mae": r.risk if r.how == "SL" else float(np.clip(adv, 0, r.risk))})
    return pd.DataFrame(out)


def per_day(T, ests, dates):
    """Por día: lista de (pnl, mae) por 1 contrato de cada estrategia, sin solapar posiciones."""
    t = T[T.est.isin(ests)].sort_values("entry")
    keep, busy = [], None
    for r in t.itertuples():
        if busy is not None and r.entry < busy:
            continue
        keep.append(r.Index); busy = r.exit
    t = t.loc[keep]
    g = {d: [] for d in dates}
    for r in t.itertuples():
        g[r.date].append((r.est, r.pts * PV - COM, r.mae * PV + COM))
    return [g[d] for d in dates]


def sim(days, sizer, start, max_days=400):
    bal = peak = 0.0; good = 0
    for n, ops in enumerate(days[start:start + max_days]):
        thr = min(peak - DD, LOCK)
        pnl = sum(sizer(bal, e) * p for e, p, _ in ops)
        mae = sum(sizer(bal, e) * m for e, _, m in ops)
        if bal - mae <= thr or bal + pnl < thr:
            return False, n + 1
        bal += pnl; peak = max(peak, bal); good += pnl >= 100
        if good >= 5 and bal >= 1000:
            return True, n + 1
    return None, None


def main():
    allday = list(pd.bdate_range("2024-01-02", "2026-11-06").date)
    poc = pd.read_csv("backtest/resultados/tres_estrategias_ops.csv", parse_dates=["entry", "exit"])
    poc = poc[poc.est != "C SMC"].assign(est=lambda x: x.est.map({"A 8:30": "830", "B 10:30": "1030"}))
    poc["entry"] = pd.to_datetime(poc.entry, utc=True); poc["exit"] = pd.to_datetime(poc.exit, utc=True)
    poc["date"] = pd.to_datetime(poc.date).dt.date
    smc930, smc300 = smc_ops(570), smc_ops(0)
    cases = []
    T1 = pd.concat([poc, smc930], ignore_index=True)
    T2 = pd.concat([poc, smc300], ignore_index=True)
    fixed = lambda k: (lambda bal, e: k)
    cush = lambda lo, hi, at: (lambda bal, e: hi if bal >= at else lo)
    protect = lambda hi, lo, at: (lambda bal, e: lo if bal < at else hi)
    cases += [
        ("SMC sola x1 (desde 8:30 CDMX)", T1, ["SMC"], fixed(1)),
        ("SMC sola x2", T1, ["SMC"], fixed(2)),
        ("SMC x1, sube a x2 con +$300 de colchón", T1, ["SMC"], cush(1, 2, 300)),
        ("SMC x2, baja a x1 si va -$300", T1, ["SMC"], protect(2, 1, -300)),
        ("SMC sola x1 vigilando desde 2:00 CDMX", T2, ["SMC"], fixed(1)),
        ("10:30 + SMC x1", T1, ["1030", "SMC"], fixed(1)),
        ("8:30 + 10:30 + SMC x1", T1, ["830", "1030", "SMC"], fixed(1)),
        ("8:30 + 10:30 + SMC x1, todo x2 con +$300", T1, ["830", "1030", "SMC"], cush(1, 2, 300)),
        ("8:30 + 10:30 x1 + SMC x2", T1, ["830", "1030", "SMC"], lambda bal, e: 2 if e == "SMC" else 1),
    ]
    rows = []
    for name, T, ests, sizer in cases:
        days = per_day(T, ests, allday)
        r = [sim(days, sizer, s) for s in range(0, len(days) - 120)]
        r = [x for x in r if x[0] is not None]
        ok = [x[1] for x in r if x[0]]
        rows.append({"plan fondeada": name, "llega al 1er retiro %": round(100 * np.mean([x[0] for x in r]), 1),
                     "días hábiles (mediana)": np.median(ok), "días hábiles (p75)": np.percentile(ok, 75)})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
