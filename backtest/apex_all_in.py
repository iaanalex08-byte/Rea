#!/usr/bin/env python3
"""Apex 25K Intraday Trail "todo en una operación": ¿qué probabilidad hay de pasar? ¿y con 10 cuentas?

Reglas (captura del usuario): objetivo $1,500, pérdida máxima $1,000 con arrastre INTRADÍA (sigue al máximo de la
cuenta incluyendo ganancias no realizadas; deja de subir en +$100), 1 día mínimo, máx. 4 minis / 40 micros, 30 días.

"Todo en una operación": se entra en la señal del día (8:30, 10:30 o SMC; o al azar a las 10:30 como referencia)
con un tamaño tal que la caída permitida ($1,000) quede a N puntos. Se sale al llegar a +$1,500 (pasa) o al tocar el
límite que arrastra (se quema). Si al cierre (15:55 CDMX) no pasó nada, se cierra y al día siguiente se repite con el
saldo que quede, hasta 21 días hábiles.

10 cuentas: (a) las 10 copian la misma operación -> pasan o se queman juntas.
            (b) cada cuenta empieza un día distinto (escalonadas) -> resultados casi independientes (campana).

    python3 backtest/apex_all_in.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as cn  # noqa: E402
import poc_backtest as pb  # noqa: E402
import retroceso_1100 as rf  # noqa: E402
import smc_mss as sm  # noqa: E402
from apertura_ny_fvg import load, resample  # noqa: E402

TARGET, DD, LOCK, MAXD = 1500, 1000, 100, 21
COM_MINI = 4.0   # ida y vuelta por mini (aprox.)
SIZES = {"1 mini (caída = 50 pts)": 1, "2 minis (25 pts)": 2, "4 minis (12.5 pts)": 4}


def poc_entries(h, judas):
    hh, mm = map(int, h.split(":")); ws = hh * 60 + mm + 12
    a = pb.parse_args(["backtest/datos_NQ", "--tf", "3", "--prof-hour", str(hh), "--prof-min", str(mm), "--prof-dur", "12",
                       "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--win-end", "13:30", "--sl", "66.5", "--rr", "1", "--single"])
    d, _ = pb.filter_days(cn.bars(3), a)
    a.dir_map = judas
    tr, _ = pb.run(d, a)
    return pd.DataFrame({"date": tr.date, "t": tr.entry_time + pd.Timedelta(minutes=3), "dir": np.where(tr.dir == "COMPRA", 1, -1), "px": tr.entry})


def main():
    m1 = rf.bars()
    tm = (m1.index.hour * 60 + m1.index.minute).to_numpy()
    H, L, C = m1.high.to_numpy(), m1.low.to_numpy(), m1.close.to_numpy()
    o00 = m1.groupby(m1.index.date).open.first()
    lc = m1[tm < 360].groupby(m1[tm < 360].index.date).close.last()
    judas = {d: -int(np.sign(lc[d] - o00[d])) for d in o00.index if d in lc.index}
    sig = {"8:30 contra Londres": poc_entries("08:30", judas), "10:30 con tendencia": poc_entries("10:30", None)}
    s = sm.run(resample(load("backtest/datos_NQ"), 5), 180, "FVG", False, "nuevo extremo", 1.5, entry_from=570)
    sig["SMC 5 min"] = pd.DataFrame({"date": s.date, "t": s.entry_time.dt.tz_convert(m1.index.tz) + pd.Timedelta(minutes=5), "dir": s.side, "px": s.ent})
    # referencia: a las 10:30 a mercado, dirección al azar
    rng = np.random.default_rng(7)
    i1030 = np.flatnonzero(tm == 630)
    sig["Al azar 10:30 (referencia)"] = pd.DataFrame({"date": m1.index[i1030].date, "t": m1.index[i1030] + pd.Timedelta(minutes=1),
                                                      "dir": rng.choice([-1, 1], len(i1030)), "px": m1.open.to_numpy()[i1030]})
    days = pd.bdate_range("2024-01-02", "2026-11-06").date
    pos_of = {t: i for i, t in enumerate(m1.index)}

    def trade(sg, day, bal, peak, c):
        """Una operación desde el saldo bal (pico peak). Devuelve (estado, bal, peak)."""
        i = m1.index.searchsorted(sg.t)
        pv = 20 * c * sg.dir
        cost = COM_MINI * c
        while i < len(C) and m1.index[i].date() == day and tm[i] < 955:
            adv = (L[i] if sg.dir == 1 else H[i]) - sg.px
            fav = (H[i] if sg.dir == 1 else L[i]) - sg.px
            thr = min(peak - DD, LOCK)
            if bal + adv * pv - cost <= thr:
                return "quemada", thr, peak
            eq_f = bal + fav * pv - cost
            if eq_f >= TARGET:
                return "pasa", TARGET, max(peak, TARGET)
            peak = max(peak, eq_f)
            i += 1
        last = C[min(i, len(C) - 1) - 1]
        bal = bal + (last - sg.px) * pv - cost
        return "sigue", bal, max(peak, bal)

    def account(S, k0, c):
        """Cuenta que empieza el día hábil k0; toma la señal de cada día. Devuelve (pasa?, días)."""
        bal = peak = 0.0
        for n, d in enumerate(days[k0:k0 + MAXD]):
            if d not in S.index:
                continue
            st, bal, peak = trade(S.loc[d], d, bal, peak, c)
            if st != "sigue":
                return st == "pasa", n + 1
        return False, MAXD

    rows, dist = [], []
    for nm, S in sig.items():
        S = S.dropna().drop_duplicates("date").set_index("date")
        for sz, c in SIZES.items():
            res = [account(S, k, c) for k in range(len(days) - MAXD - 10)]
            ok = np.array([r[0] for r in res]); dd = np.array([r[1] for r in res])
            # 10 cuentas escalonadas (empiezan días hábiles consecutivos)
            n10 = np.array([ok[k:k + 10].sum() for k in range(len(ok) - 10)])
            p = ok.mean()
            rows.append({"estrategia": nm, "tamaño": sz, "contratos": c, "p_pasa": round(p, 4), "dias_prom": round(dd[ok].mean(), 1) if ok.any() else None,
                         "p_al_menos_1_de_10": round((n10 >= 1).mean(), 4), "pasan_prom_de_10": round(n10.mean(), 2),
                         "p_al_menos_1_binomial": round(1 - (1 - p) ** 10, 4)})
            for k in range(11):
                dist.append({"estrategia": nm, "tamaño": sz, "pasan": k, "prob_real": round((n10 == k).mean(), 4),
                             "prob_binomial": round(float(pd.Series([p]).apply(lambda q: __import__("math").comb(10, k) * q ** k * (1 - q) ** (10 - k)).iloc[0]), 4)})
        print(nm, "listo", file=sys.stderr, flush=True)
    R = pd.DataFrame(rows); D = pd.DataFrame(dist)
    R.to_csv("backtest/resultados/apex_all_in.csv", index=False); D.to_csv("backtest/resultados/apex_all_in_dist.csv", index=False)
    pd.set_option("display.width", 220)
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
