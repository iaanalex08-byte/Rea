#!/usr/bin/env python3
"""¿Qué conceptos de las otras estrategias (FVG, OB, BMS/CHoCH, barrida/SMC, mechas/equilibrio, SMT con ES)
mejoran el POC 10:30 del NQ? Cada concepto es un filtro sobre las mismas 447 operaciones.
Solo vale si mejora el R por operación en 2024-2025 Y en 2026.

Requiere backtest/resultados/mejoras_1030_ops.csv (correr antes mejoras_1030.py).
    python3 backtest/mejoras_1030_smc.py
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as c  # noqa: E402
import poc_backtest as pb  # noqa: E402
import smc_mss as sm  # noqa: E402
import wick_theory as wt  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402
from smc_mss import swings  # noqa: E402


def main():
    F = pd.read_csv("backtest/resultados/mejoras_1030_ops.csv", parse_dates=["entry", "exit"])
    F["date"] = pd.to_datetime(F.date).dt.date
    a = pb.parse_args(["backtest/datos_NQ", "--prof-hour", "10", "--prof-min", "30", "--win-start", "10:42",
                       "--sl", "66.5", "--rr", "1", "--single"])
    df3 = c.bars(3)
    d3, _ = pb.filter_days(df3, a)
    raw, _ = pb.run(d3, a)
    raw = raw.set_index("date")
    F["brk"] = raw.brk_time.reindex(F.date).tolist()
    F["poc"] = raw.entry.reindex(F.date).values
    O, H, L, C = (df3[x].to_numpy() for x in ("open", "high", "low", "close"))
    pos = {t: k for k, t in enumerate(df3.index)}
    sh3, sl3 = swings(H, L)
    # 5 min para estructura (BMS / CHoCH)
    d5 = df3.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    H5, L5, C5 = d5.high.to_numpy(), d5.low.to_numpy(), d5.close.to_numpy()
    sh5, sl5 = swings(H5, L5)
    # SMC (5 min, NY) del mismo día
    nq1 = load("backtest/datos_NQ")
    smc = sm.run(resample(nq1, 5), 180, "FVG", False, "nuevo extremo", 1.0)
    smc["d"] = smc.entry_time.dt.tz_convert("Etc/GMT+6").dt.date
    smc_by = smc.groupby("d").apply(lambda g: list(zip(g.entry_time, g.side)))
    # equilibrio y mechas de 30 min (24 h antes de la apertura de NY)
    ctx = wt.context(nq1)
    # ES para SMT / correlación
    es = pb.load_bars(["backtest/datos"], "Etc/GMT+6", "Etc/GMT+6", 3, "auto")
    tm_es = es.index.hour * 60 + es.index.minute
    es_o0 = es[tm_es == 0].groupby(es[tm_es == 0].index.date).open.first()
    tm3 = df3.index.hour * 60 + df3.index.minute
    nq_o0 = df3[tm3 == 0].groupby(df3[tm3 == 0].index.date).open.first()
    feats = []
    for r in F.itertuples():
        side, e = r.dir, pd.Timestamp(r.entry).tz_convert("Etc/GMT+6")
        ie, ib = pos.get(e), pos.get(pd.Timestamp(r.brk))
        f = {}
        if ie is None or ib is None or ib >= ie:
            feats.append(f); continue
        i_pe = ib  # inicio del tramo: desde 10:42 hasta la ruptura
        while i_pe > 0 and (df3.index[i_pe].hour * 60 + df3.index[i_pe].minute) > 642:
            i_pe -= 1
        # FVG a favor en el tramo de ruptura / POC dentro de un FVG a favor
        fv = [(L[k], H[k - 2]) if side == 1 else (H[k], L[k - 2]) for k in range(i_pe + 2, ie)
              if (side == 1 and L[k] > H[k - 2]) or (side == -1 and H[k] < L[k - 2])]
        f["FVG a favor en la ruptura"] = len(fv) > 0
        f["POC dentro de un FVG a favor"] = any(min(x) - 2 <= r.poc <= max(x) + 2 for x in fv)
        # OB: última vela contraria antes de la ruptura que contiene el POC
        ob = None
        for k in range(ib - 1, i_pe - 1, -1):
            if (C[k] - O[k]) * side < 0:
                ob = (L[k], H[k]); break
        f["POC dentro de un OB"] = ob is not None and ob[0] - 2 <= r.poc <= ob[1] + 2
        # barrida durante el retroceso: el precio pasa un swing de 3 min en contra y vuelve
        sw = [L[k] for k in range(i_pe, ie - 1) if sl3[k]] if side == 1 else [H[k] for k in range(i_pe, ie - 1) if sh3[k]]
        f["Barrida de liquidez en el retroceso"] = bool(sw) and ((L[ib:ie + 1].min() < min(sw)) if side == 1 else (H[ib:ie + 1].max() > max(sw)))
        # estructura de 5 min al momento de entrar: BMS (a favor) / CHoCH (cambio a favor) desde las 7:30
        k5 = d5.index.searchsorted(e) - 1
        hs, ls, last_evt = [], [], None
        for k in range(max(2, k5 - 120), k5 + 1):
            if sh5[k - 2]:
                hs.append(H5[k - 2])
            if sl5[k - 2]:
                ls.append(L5[k - 2])
            if len(hs) >= 2 and len(ls) >= 2 and d5.index[k].hour * 60 + d5.index[k].minute >= 450:
                tr = 1 if (hs[-1] > hs[-2] and ls[-1] > ls[-2]) else (-1 if (hs[-1] < hs[-2] and ls[-1] < ls[-2]) else 0)
                if C5[k] > hs[-1]:
                    last_evt = ("BMS" if tr == 1 else "CHoCH", 1)
                elif C5[k] < ls[-1]:
                    last_evt = ("BMS" if tr == -1 else "CHoCH", -1)
        f["Último quiebre de 5 min a favor (BMS o CHoCH)"] = last_evt is not None and last_evt[1] == side
        f["Último quiebre de 5 min es BMS a favor"] = last_evt == ("BMS", side)
        f["Último quiebre de 5 min es CHoCH a favor"] = last_evt == ("CHoCH", side)
        f["Último quiebre de 5 min en contra"] = last_evt is not None and last_evt[1] == -side
        # SMC del mismo día
        lst = smc_by.get(r.date, [])
        f["SMC del día en la misma dirección (antes de entrar)"] = any(s == side and t.tz_convert("Etc/GMT+6") <= e for t, s in lst)
        f["SMC del día en contra (antes de entrar)"] = any(s == -side and t.tz_convert("Etc/GMT+6") <= e for t, s in lst)
        # mechas / equilibrio (fecha de NY = misma fecha)
        cx = ctx.get(r.date)
        if cx:
            f["Equilibrio 24 h a favor"] = np.sign(r.poc - cx["eq"]) == side
            f["Última mecha de 30 min a favor"] = (not np.isnan(cx["last"])) and np.sign(r.poc - cx["last"]) == side
        # ES: misma dirección 00:00 -> entrada (correlación) o divergencia (SMT)
        esp = es.close.asof(e) if e >= es.index[0] else np.nan
        es_dir = np.sign(esp - es_o0.get(r.date, np.nan))
        f["ES va en la misma dirección desde 00:00"] = es_dir == side
        f["ES diverge (SMT)"] = es_dir == -side
        feats.append(f)
    G = pd.concat([F, pd.DataFrame(feats)], axis=1)
    cols = list(pd.DataFrame(feats).columns)
    G.to_csv("backtest/resultados/mejoras_1030_smc_ops.csv", index=False)

    def rep(name, mask):
        mask = pd.Series(mask, index=G.index).fillna(False).astype(bool)
        out = {"filtro": name, "ops": int(mask.sum())}
        for per, sel in (("24-25", G.y <= 2025), ("2026", G.y == 2026)):
            k = G[mask & sel]
            out[f"acierto {per}"] = round(100 * (k.R > 0).mean(), 1) if len(k) else np.nan
            out[f"R/op {per}"] = round(k.R.mean(), 3) if len(k) else np.nan
        out["R total"] = round(G[mask].R.sum(), 1)
        return out

    base = rep("BASE", np.ones(len(G), bool))
    rows = [base] + [rep(cn, G[cn]) for cn in cols] + [rep("NO: " + cn, ~G[cn].fillna(False).astype(bool)) for cn in cols]
    T = pd.DataFrame(rows)
    T["mejora en ambos"] = (T["R/op 24-25"] > base["R/op 24-25"]) & (T["R/op 2026"] > base["R/op 2026"]) & (T.ops >= 60)
    pd.set_option("display.width", 240)
    print(T.to_string(index=False))
    # con los dos filtros que ya funcionaron (tendencia fuerte + EMA 15 min)
    strong = (G.tend_abs >= 100) & G.ema15_a_favor
    print("\nSobre la 10:30 ya filtrada (tendencia >= 100 pts + EMA 15 min a favor):")
    b2 = rep("Filtrada", strong)
    rows2 = [b2] + [rep("Filtrada + " + cn, strong & G[cn].fillna(False).astype(bool)) for cn in cols]
    T2 = pd.DataFrame(rows2)
    T2["mejora en ambos"] = (T2["R/op 24-25"] > b2["R/op 24-25"]) & (T2["R/op 2026"] > b2["R/op 2026"]) & (T2.ops >= 50)
    print(T2.to_string(index=False))


if __name__ == "__main__":
    main()
