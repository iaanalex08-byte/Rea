#!/usr/bin/env python3
"""Tres estrategias en NQ y su uso en Lucid 25K Flex.

  A) POC 8:30 contra Londres (3 min, SL 66.5, 1:1.25)
  B) POC 10:30 con tendencia (3 min, SL 66.5, 1:1)
  C) Barrida + MSS + FVG (5 min, 3:00-11:30 ET, TP en el nuevo extremo si >= 1R)

Reglas de convivencia: "sin solapar" = una sola posición abierta a la vez (la primera en entrar manda).
Se mide: correlación diaria, choques, neto, caída y Lucid (evaluación y fondeada por separado).

    python3 backtest/tres_estrategias.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as c  # noqa: E402
import lucid_flex25k as L  # noqa: E402
import lucid_rapidez as LR  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

PV, COM = 2.0, 1.24


def poc_trades():
    df = c.bars(3)
    tm = df.index.hour * 60 + df.index.minute
    o0 = df[tm == 0].groupby(df[tm == 0].index.date).open.first()
    lc = df[tm < 360].groupby(df[tm < 360].index.date).close.last()
    judas = {d: -int(np.sign(lc[d] - o0[d])) for d in o0.index if d in lc.index}
    a = c.trades({"nombre": "A", "tf": 3, "ph": 8, "pm": 30, "dur": 12, "ws": "08:42", "sl": 66.5, "rr": 1.25, "dmap": judas})
    b = c.trades(c.BASE)
    out = []
    for name, t, sl in (("A 8:30", a, 66.5), ("B 10:30", b, 66.5)):
        out.append(pd.DataFrame({"est": name, "date": t.date, "entry": t.entry, "exit": t.exit, "dir": t.dir,
                                 "pts": t.pts, "mae": t.mae, "R": t.R}))
    return pd.concat(out)


def main():
    poc = poc_trades()
    nq1 = load("backtest/datos_NQ")
    s = sm.run(resample(nq1, 5), 180, "FVG", False, "nuevo extremo", 1.0)
    rows = []
    for r in s.itertuples():
        w = nq1.loc[r.entry_time:r.exit_time]
        # el precio de entrada no se guarda: se reconstruye con R y el resultado no hace falta; MAE aproximado
        # como el máximo movimiento adverso respecto al cierre de la vela de entrada, acotado por el riesgo
        ref = w.close.iloc[0] if len(w) else np.nan
        adv = (w.high.max() - ref) if r.side == -1 else (ref - w.low.min())
        mae = r.risk if r.how == "SL" else float(np.clip(adv, 0, r.risk))
        d = r.entry_time.tz_convert("Etc/GMT+6").date()
        rows.append({"est": "C SMC", "date": d, "entry": r.entry_time, "exit": r.exit_time, "dir": r.side,
                     "pts": r.R * r.risk, "mae": mae, "R": r.R})
    allt = pd.concat([poc, pd.DataFrame(rows)], ignore_index=True)
    allt["entry"] = pd.to_datetime(allt.entry, utc=True)
    allt["exit"] = pd.to_datetime(allt.exit, utc=True)
    allt = allt.sort_values("entry").reset_index(drop=True)

    # correlación diaria y choques
    dR = allt.pivot_table(index="date", columns="est", values="R", aggfunc="sum").fillna(0)
    print("Correlación diaria (R):"); print(dR.corr().round(2).to_string())
    ov = []
    for e1 in ("A 8:30", "B 10:30"):
        x, y = allt[allt.est == e1], allt[allt.est == "C SMC"]
        m = x.merge(y, on="date", suffixes=("", "_c"))
        both_open = ((m.entry_c < m.exit) & (m.exit_c > m.entry))
        ov.append({"con": e1, "días con ambas": len(m), "abiertas a la vez": int(both_open.sum()),
                   "en dirección contraria": int((both_open & (m.dir != m.dir_c)).sum())})
    print("\nChoques con la estrategia C:"); print(pd.DataFrame(ov).to_string(index=False))

    dates = sorted(set(allt.date))

    def select(ests, rule):
        t = allt[allt.est.isin(ests)]
        if rule == "todas":
            return t
        keep, busy = [], None
        for r in t.itertuples():
            if busy is not None and r.entry < busy:
                continue
            keep.append(r.Index); busy = r.exit
        return t.loc[keep]

    def days(t, k):
        u = t.pts * PV * t.est.map(k) - COM * t.est.map(k)
        m = t.mae * PV * t.est.map(k) + COM * t.est.map(k)
        x = pd.DataFrame({"date": t.date, "u": u, "m": m}).groupby("date").sum().reindex(dates).fillna(0)
        return list(zip(x.u, x.m)), x.u

    def stats(name, ests, k, rule="sin solapar"):
        t = select(ests, rule)
        D, u = days(t, k)
        eq = u.cumsum(); dd = (eq.cummax().clip(lower=0) - eq).max()
        y = pd.to_datetime(pd.Series(t.date.values)).dt.year.values
        ev = [(st, L.evaluacion(D, st)) for st in range(len(D))]
        ev = [(st, r) for st, r in ev if r[0] is not None]
        p = np.mean([r[0] for _, r in ev]); dpass = np.median([r[1] for _, r in ev if r[0]])
        fr = [LR.fondeada(D, st) for st in range(0, len(D) - 60)]
        n1 = np.mean([f[1] >= 1 for f in fr]); cob = np.mean([f[0] for f in fr])
        first = [f[3] for f in fr if f[3]]
        return {"combinación": name, "ops": len(t), "R_24_25": round(t.R[y <= 2025].sum(), 1), "R_2026": round(t.R[y == 2026].sum(), 1),
                "neto_$": round(u.sum()), "caída_máx_$": round(dd), "peor_día_$": round(u.min()), "días<-600": int((u <= -600).sum()),
                "eval_pasa%": round(100 * p, 1), "eval_días": int(dpass), "fond_1+retiro%": round(100 * n1, 1),
                "fond_cobrado_$": round(cob), "fond_días_1er": float(np.median(first)) if first else None}

    K = lambda a=0, b=0, cc=0: {"A 8:30": a, "B 10:30": b, "C SMC": cc}
    res = [
        stats("B 10:30 ×1", ["B 10:30"], K(b=1)),
        stats("C SMC ×1", ["C SMC"], K(cc=1)),
        stats("C SMC ×2", ["C SMC"], K(cc=2)),
        stats("B ×1 + C ×1", ["B 10:30", "C SMC"], K(b=1, cc=1)),
        stats("A ×2 + B ×2 (plan actual)", ["A 8:30", "B 10:30"], K(a=2, b=2)),
        stats("A ×2 + B ×2 + C ×1", ["A 8:30", "B 10:30", "C SMC"], K(a=2, b=2, cc=1)),
        stats("A ×2 + B ×2 + C ×2", ["A 8:30", "B 10:30", "C SMC"], K(a=2, b=2, cc=2)),
        stats("A ×1 + B ×1 + C ×1", ["A 8:30", "B 10:30", "C SMC"], K(a=1, b=1, cc=1)),
        stats("A ×2 + B ×2 + C ×1 (todas, con solape)", ["A 8:30", "B 10:30", "C SMC"], K(a=2, b=2, cc=1), "todas"),
    ]
    T = pd.DataFrame(res)
    pd.set_option("display.width", 260)
    print(); print(T.to_string(index=False))
    T.to_csv("backtest/resultados/tres_estrategias.csv", index=False)
    allt.to_csv("backtest/resultados/tres_estrategias_ops.csv", index=False)

    # patrones de C frente a A y B
    c_ = allt[allt.est == "C SMC"].copy()
    df3 = c.bars(3); tm = df3.index.hour * 60 + df3.index.minute
    o0 = df3[tm == 0].groupby(df3[tm == 0].index.date).open.first()
    lc = df3[tm < 360].groupby(df3[tm < 360].index.date).close.last()
    c_["londres_contra"] = [(-np.sign(lc.get(d, np.nan) - o0.get(d, np.nan))) == s for d, s in zip(c_.date, c_.dir)]
    px = df3.close
    c_["con_tendencia"] = [np.sign(px.asof(e.tz_convert("Etc/GMT+6")) - o0.get(d, np.nan)) == s for d, e, s in zip(c_.date, c_.entry, c_.dir)]
    for col, name in (("londres_contra", "C a favor de 'contra Londres'"), ("con_tendencia", "C a favor de la tendencia desde 00:00")):
        g = c_.groupby(col)
        print(f"\n{name}:"); print(pd.DataFrame({"ops": g.size(), "acierto%": (100 * g.R.apply(lambda r: (r > 0).mean())).round(1),
                                                "R/op": g.R.mean().round(3)}).to_string())
    prev = allt[allt.est != "C SMC"].groupby("date").R.sum()
    c_["poc_mismo_dia"] = c_.date.map(lambda d: "sin POC" if d not in prev.index else ("POC ganó" if prev[d] > 0 else "POC perdió"))
    g = c_.groupby("poc_mismo_dia")
    print("\nC según el resultado de los POC del mismo día:")
    print(pd.DataFrame({"ops": g.size(), "acierto%": (100 * g.R.apply(lambda r: (r > 0).mean())).round(1), "R/op": g.R.mean().round(3)}).to_string())


if __name__ == "__main__":
    main()
