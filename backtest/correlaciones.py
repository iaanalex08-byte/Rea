#!/usr/bin/env python3
"""¿Algún activo avisa la dirección de otro? ES, NQ y GC, 2024-2026, hora UTC-6.

    python3 backtest/correlaciones.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

T0, T1 = pd.Timestamp("2024-01-01", tz="Etc/GMT+6"), pd.Timestamp("2026-11-07", tz="Etc/GMT+6")
CARP = {"ES": "backtest/datos", "NQ": "backtest/datos_NQ", "GC": "backtest/datos_GC"}


def load(r):
    df = pb.load_bars([CARP[r]], "Etc/GMT+6", "Etc/GMT+6", 1, "auto")
    return df[(df.index >= T0) & (df.index < T1)]


def px(df, hhmm):
    """Precio (open) a una hora del día, por fecha."""
    h, m = hhmm
    s = df[(df.index.hour == h) & (df.index.minute == m)].open
    return pd.Series(s.values, index=s.index.date)


def main():
    D = {r: load(r) for r in CARP}
    first = {r: D[r].groupby(D[r].index.date).open.first() for r in D}
    P = {r: {t: px(D[r], t) for t in [(0, 0), (7, 0), (9, 0), (10, 0), (10, 30), (11, 0), (12, 0), (14, 30)]} for r in D}
    days = sorted(set.intersection(*[set(P[r][(11, 0)].index) & set(P[r][(14, 30)].index) & set(P[r][(7, 0)].index) for r in D]))
    print(f"Días con los tres activos: {len(days)}")

    def ret(r, a, b):
        return (P[r][b].reindex(days) / P[r][a].reindex(days) - 1) * 100

    print("\n1) Correlación del mismo día (rendimiento 7:00 -> 14:30)")
    R = pd.DataFrame({r: ret(r, (7, 0), (14, 30)) for r in D})
    print(R.corr().round(2).to_string())

    print("\n2) ¿El movimiento de un activo AVISA el siguiente movimiento de otro?")
    print("   (% de veces que la dirección del 'aviso' coincide con la dirección siguiente; 50 % = azar)")
    rows = []
    for (a0, a1, b1, lab) in [((10, 0), (11, 0), (12, 0), "10:00-11:00 -> 11:00-12:00"),
                              ((10, 30), (11, 0), (14, 30), "10:30-11:00 -> 11:00-14:30"),
                              ((0, 0), (7, 0), (14, 30), "00:00-7:00 -> 11:00-14:30"),
                              ((7, 0), (11, 0), (14, 30), "7:00-11:00 -> 11:00-14:30")]:
        for src in D:
            for dst in D:
                s = np.sign(ret(src, a0, a1))
                t = np.sign(ret(dst, a1 if b1 != (14, 30) or a1 == (11, 0) else (11, 0), b1)) if a1 == (11, 0) else np.sign(ret(dst, (11, 0), b1))
                ok = (s != 0) & (t != 0)
                rows.append({"ventana": lab, "aviso": src, "objetivo": dst, "acierto %": round(100 * (s[ok] == t[ok]).mean(), 1), "días": int(ok.sum())})
    A = pd.DataFrame(rows)
    print(A.pivot_table(index=["ventana", "aviso"], columns="objetivo", values="acierto %").to_string())

    print("\n3) Filtro para la entrada a mercado del ES a las 11:00 (tendencia 00:00-7:00, TP 4 / SL 20.75)")
    t = pd.read_csv("backtest/resultados/comparativa_horas_1430.csv")
    t = t[t.hora == "11:00"].copy()
    t["date"] = pd.to_datetime(t.date).dt.date
    t = t[t.date.isin(days)]
    es_dir = np.sign(ret("ES", (0, 0), (7, 0))).reindex(t.date).values
    for other in ("NQ", "GC"):
        o = np.sign(ret(other, (0, 0), (7, 0))).reindex(t.date).values
        for lab, mask in (("coincide", o == es_dir), ("opuesto", o == -es_dir)):
            s = t[mask]
            w, l = (s.result == "GANADA").sum(), (s.result == "PERDIDA").sum()
            y = pd.to_datetime(s.date).dt.year
            wi = lambda q: 100 * (q.result == "GANADA").sum() / max(1, q.result.isin(["GANADA", "PERDIDA"]).sum())
            print(f"   {other} {lab:9s} con la tendencia del ES: {len(s):3d} días, winrate {100 * w / (w + l):.1f}% "
                  f"(24-25 {wi(s[y <= 2025]):.1f}% / 2026 {wi(s[y == 2026]):.1f}%), neto ${s.usd.sum():,.0f}")
    w, l = (t.result == "GANADA").sum(), (t.result == "PERDIDA").sum()
    print(f"   Sin filtro: {len(t)} días, winrate {100 * w / (w + l):.1f}%, neto ${t.usd.sum():,.0f}")


if __name__ == "__main__":
    main()
