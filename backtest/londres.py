#!/usr/bin/env python3
"""Manipulación de Londres -> dirección de Nueva York (NQ, 2024-2026, hora CDMX fija UTC-6).

Rango de Asia: 18:00-23:59 del día anterior. Londres: 01:00-05:59.
Señales de dirección para el día:
  tendencia : la regla actual (precio en la hora de entrada vs apertura de las 00:00).
  barrida   : Londres barre SOLO el mínimo de Asia -> compras; SOLO el máximo -> ventas.
  rechazo   : barrida y Londres cierra (05:59) de vuelta dentro del rango de Asia.
  judas     : contra el movimiento de Londres (00:00 -> 05:59).
  barr+tend : barrida solo cuando coincide con la tendencia.
Se prueba: (1) acierto de dirección hasta las 14:30, (2) entrada a mercado, (3) POC con esa dirección.

    python3 backtest/londres.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

T0, T1 = "2024-01-01", "2026-11-07"
ENTRADAS = ["07:30", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00"]
SLS, RRS = [46.0, 66.5, 87.0], [1.0, 1.25, 1.5, 2.0]
CIERRE = 14 * 60 + 30
SENALES = ["tendencia", "barrida", "rechazo", "judas", "barr+tend"]


def hm(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def main():
    a0 = pb.parse_args(["backtest/datos_NQ", "--tf", "1"])
    df = pb.load_bars(a0.csv, a0.input_tz, a0.tz, 1, a0.nt_tz)
    df = df[(df.index >= pd.Timestamp(T0, tz=a0.tz) - pd.Timedelta(days=1)) & (df.index < pd.Timestamp(T1, tz=a0.tz))]
    tm = df.index.hour * 60 + df.index.minute
    # Asia (18:00-23:59) se asigna al día siguiente
    asia = df[tm >= 18 * 60]
    ag = asia.groupby((asia.index + pd.Timedelta(days=1)).date).agg(aH=("high", "max"), aL=("low", "min"))
    lon = df[(tm >= 60) & (tm < 6 * 60)]
    lg = lon.groupby(lon.index.date).agg(lH=("high", "max"), lL=("low", "min"), lC=("close", "last"))
    day = df[tm < 15 * 60]
    days = {}
    for d, g in day.groupby(day.index.date):
        t = (g.index.hour * 60 + g.index.minute).to_numpy()
        if t[0] != 0 or d < pd.Timestamp(T0).date() or d not in ag.index or d not in lg.index:
            continue
        days[d] = (t, g.open.to_numpy(), g.high.to_numpy(), g.low.to_numpy())
    print(f"{len(days)} días con Asia, Londres y NY", file=sys.stderr)

    def sig_base(d):
        r, l = ag.loc[d], lg.loc[d]
        hi, lo = l.lH > r.aH, l.lL < r.aL
        b = 1 if (lo and not hi) else (-1 if (hi and not lo) else 0)
        rech = b if (b == 1 and l.lC > r.aL) or (b == -1 and l.lC < r.aH) else 0
        o0 = days[d][1][0]
        j = -int(np.sign(l.lC - o0))
        return b, rech, j

    base = {d: sig_base(d) for d in days}

    def price_at(d, e):
        t, O = days[d][0], days[d][1]
        i = int(np.searchsorted(t, e))
        return (i, O[i]) if i < len(t) and t[i] == e else (None, None)

    def direction(d, s, e):
        b, rech, j = base[d]
        i, px = price_at(d, e)
        if i is None:
            return 0
        tr = int(np.sign(px - days[d][1][0]))
        return {"tendencia": tr, "barrida": b, "rechazo": rech, "judas": j, "barr+tend": b if b == tr else 0}[s]

    # (1) acierto de dirección: de la hora de entrada a las 14:30
    acc = []
    for e in ENTRADAS:
        E = hm(e)
        for s in SENALES:
            hits, mv = [], []
            for d in days:
                dd = direction(d, s, E)
                i, px = price_at(d, E)
                j, pc = price_at(d, CIERRE)
                if dd == 0 or i is None or j is None:
                    continue
                m = (pc - px) * dd
                hits.append(m > 0); mv.append(m)
            acc.append({"entrada": e, "señal": s, "días": len(hits), "acierto_dir": round(100 * np.mean(hits), 1),
                        "pts_prom": round(np.mean(mv), 1)})
    A = pd.DataFrame(acc)

    # (2) entrada a mercado con SL / TP y cierre 14:30
    mk = []
    for e in ENTRADAS:
        E = hm(e)
        for s in SENALES:
            dirs = {d: direction(d, s, E) for d in days}
            for sl in SLS:
                for rr in RRS:
                    R, Y = [], []
                    for d, dd in dirs.items():
                        if dd == 0:
                            continue
                        t, O, H, L = days[d]
                        i, px = price_at(d, E)
                        if i is None:
                            continue
                        tp, st = px + dd * sl * rr, px - dd * sl
                        r = None
                        for k in range(i, len(t)):
                            if t[k] >= CIERRE:
                                r = (O[k] - px) * dd / sl
                                break
                            if (L[k] <= st) if dd == 1 else (H[k] >= st):
                                r = -1.0; break
                            if (H[k] >= tp) if dd == 1 else (L[k] <= tp):
                                r = rr; break
                        if r is None:
                            continue
                        R.append(r - 0.25 / sl); Y.append(d.year)
                    R, Y = np.array(R), np.array(Y)
                    mk.append({"entrada": e, "señal": s, "SL": sl, "RR": rr, "ops": len(R),
                               "acierto": round(100 * (R > 0).mean(), 1), "R_IS": round(R[Y <= 2025].sum(), 1),
                               "R_OOS": round(R[Y == 2026].sum(), 1), "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
        print(f"mercado {e} listo", file=sys.stderr)
    M = pd.DataFrame(mk)

    # (3) POC con la dirección de cada señal
    d3m = df.resample("3min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    d3m = d3m[d3m.index >= pd.Timestamp(T0, tz=a0.tz)]
    poc = []
    for p in ENTRADAS[:-1]:
        P = hm(p); ws = P + 12
        argv = ["backtest/datos_NQ", "--tf", "3", "--prof-hour", p[:2], "--prof-min", p[3:], "--prof-dur", "12",
                "--win-start", f"{ws // 60:02d}:{ws % 60:02d}", "--single"]
        dd3, _ = pb.filter_days(d3m, pb.parse_args(argv))
        for s in SENALES:
            dmap = None if s == "tendencia" else {d: direction(d, s, P) for d in days}
            for sl in SLS:
                for rr in RRS:
                    a = pb.parse_args(argv + ["--sl", str(sl), "--rr", str(rr)])
                    a.dir_map = dmap
                    tr, _ = pb.run(dd3, a)
                    tr = tr[tr.result.isin(["GANADA", "PERDIDA"])]
                    if tr.empty:
                        continue
                    y = pd.to_datetime(tr.date).dt.year
                    R = tr.pts / sl
                    poc.append({"perfil": p, "señal": s, "SL": sl, "RR": rr, "ops": len(tr),
                                "acierto": round(100 * (tr.result == "GANADA").mean(), 1),
                                "R_IS": round(R[y <= 2025].sum(), 1), "R_OOS": round(R[y == 2026].sum(), 1),
                                "R_total": round(R.sum(), 1), "R_op": round(R.mean(), 3)})
        print(f"POC {p} listo", file=sys.stderr)
    Pq = pd.DataFrame(poc)

    for n, T in (("londres_direccion", A), ("londres_mercado", M), ("londres_poc", Pq)):
        T.to_csv(f"backtest/resultados/{n}.csv", index=False)
    pd.set_option("display.width", 230)
    print("===== (1) Acierto de dirección hasta las 14:30 =====")
    print(A.pivot_table(index="entrada", columns="señal", values="acierto_dir").round(1)[SENALES].to_string())
    print("\nDías con señal por entrada")
    print(A.pivot_table(index="entrada", columns="señal", values="días")[SENALES].to_string())
    print("\nPuntos promedio a favor (hasta 14:30)")
    print(A.pivot_table(index="entrada", columns="señal", values="pts_prom").round(1)[SENALES].to_string())
    for name, T, key in (("(2) ENTRADA A MERCADO", M, "entrada"), ("(3) POC", Pq, "perfil")):
        print(f"\n===== {name}: robustas (IS y OOS > 0) por señal, y R/op promedio =====")
        g = T.groupby("señal")
        print(pd.DataFrame({"combos": g.size(), "robustas": g.apply(lambda x: ((x.R_IS > 0) & (x.R_OOS > 0)).sum()),
                            "R/op prom": g.R_op.mean().round(3)}).loc[SENALES].to_string())
        print(f"\nR/op promedio por {key} y señal")
        print(T.pivot_table(index=key, columns="señal", values="R_op").round(3)[SENALES].to_string())
        rob = T[(T.R_IS > 0) & (T.R_OOS > 0)].sort_values("R_total", ascending=False)
        print("\nMejores robustas")
        print(rob.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
