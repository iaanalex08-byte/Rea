#!/usr/bin/env python3
"""Búsqueda libre de patrones del NQ en la sesión de Nueva York (9:30-16:00 ET), 2024-2026, velas de 1 min.
Cada patrón se mide en 2024-2025 y en 2026 por separado; solo se considera real si se repite en ambos.

    python3 backtest/patrones_ny.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from apertura_ny_fvg import load  # noqa: E402


def build():
    nq = load("backtest/datos_NQ")
    tm = nq.index.hour * 60 + nq.index.minute
    rows = []
    prev = None
    for d, g in nq.groupby(nq.index.date):
        t = (g.index.hour * 60 + g.index.minute).to_numpy()
        r = g[(t >= 570) & (t < 960)]
        if len(r) < 370:  # sin sesión completa (domingos, feriados): se salta sin perder el día anterior
            continue
        rt = (r.index.hour * 60 + r.index.minute).to_numpy()
        at = lambda m: r.open.to_numpy()[np.searchsorted(rt, m)]
        on = g[(t < 570)]
        x = {"date": d, "o": r.open.iloc[0], "c": r.close.iloc[-1], "h": r.high.max(), "l": r.low.min(),
             "p1000": at(600), "p1030": at(630), "p1100": at(660), "p1200": at(720), "p1330": at(810),
             "p1500": at(900), "p1530": at(930), "on_h": on.high.max() if len(on) else np.nan, "on_l": on.low.min() if len(on) else np.nan,
             "t_h": rt[r.high.to_numpy().argmax()], "t_l": rt[r.low.to_numpy().argmin()], "dow": pd.Timestamp(d).dayofweek}
        # quién se toma primero: máximo o mínimo de la noche
        hi_hit = np.where(r.high.to_numpy() > x["on_h"])[0]; lo_hit = np.where(r.low.to_numpy() < x["on_l"])[0]
        x["on_first"] = 0 if (not len(hi_hit) and not len(lo_hit)) else (1 if (len(hi_hit) and (not len(lo_hit) or hi_hit[0] < lo_hit[0])) else -1)
        x["on_both"] = bool(len(hi_hit) and len(lo_hit))
        if prev is not None:
            x.update(pc=prev["c"], pdh=prev["h"], pdl=prev["l"], prng=prev["h"] - prev["l"])
            ph = np.where(r.high.to_numpy() > prev["h"])[0]; pl = np.where(r.low.to_numpy() < prev["l"])[0]
            x["pd_first"] = 0 if (not len(ph) and not len(pl)) else (1 if (len(ph) and (not len(pl) or ph[0] < pl[0])) else -1)
            # ¿se llena el hueco? (vuelve al cierre anterior) y a qué hora
            gap = x["o"] - prev["c"]
            hit = np.where((r.low.to_numpy() <= prev["c"]) if gap > 0 else (r.high.to_numpy() >= prev["c"]))[0]
            x["gap"] = gap; x["gap_fill_t"] = rt[hit[0]] if len(hit) else np.nan
        rows.append(x)
        prev = x
    D = pd.DataFrame(rows).dropna(subset=["pc"]).reset_index(drop=True)
    D["y"] = pd.to_datetime(D.date).dt.year
    D["per"] = np.where(D.y <= 2025, "24-25", "2026")
    D["rng"] = D.h - D.l
    return D


def both(D, s):
    """Imprime el valor de una serie booleana/numérica por periodo."""
    return " | ".join(f"{p}: {s[D.per == p].mean() * (100 if s.dtype == bool else 1):.1f}" for p in ("24-25", "2026"))


def main():
    D = build()
    pd.set_option("display.width", 220)
    print(f"{len(D)} sesiones completas ({(D.per == '24-25').sum()} en 2024-25, {(D.per == '2026').sum()} en 2026)\n")
    sg = np.sign

    print("1) Primera media hora (9:30-10:00) vs última media hora (15:30-16:00): % mismo sentido")
    a, b = sg(D.p1000 - D.o), sg(D.c - D.p1530)
    print("   ", both(D, (a == b)))
    a2 = sg(D.p1530 - D.o)
    print("   Día hasta 15:30 vs última media hora:", both(D, (a2 == b)))

    print("\n2) Huecos (apertura vs cierre de ayer): % que se llenan en la sesión, por tamaño")
    D["gap_abs"] = D.gap.abs()
    for lo_, hi_ in ((0, 50), (50, 100), (100, 200), (200, 1e9)):
        m = (D.gap_abs >= lo_) & (D.gap_abs < hi_)
        fill = D.gap_fill_t.notna()
        before11 = D.gap_fill_t < 660
        print(f"   hueco {lo_:>3}-{'∞' if hi_ > 1e8 else int(hi_)} pts ({m.sum()} días): se llena {both(D[m], fill[m])} %  · antes de 11:00 {both(D[m], before11[m])} %")

    print("\n3) Máximo / mínimo de la noche (18:00-9:30): ¿cuál toma NY primero y qué pasa?")
    for v, n in ((1, "toma primero el MÁXIMO"), (-1, "toma primero el MÍNIMO"), (0, "no toma ninguno")):
        m = D.on_first == v
        print(f"   {n}: {both(D, m)} % de días · luego toma el otro lado: {both(D[m], D.on_both[m])} % · cierra a favor del primero: {both(D[m], (sg(D.c - D.o) == v)[m]) if v else '-'} %")

    print("\n4) Máximo / mínimo de AYER: el primero que se rompe y el cierre")
    for v, n in ((1, "rompe primero el máximo de ayer"), (-1, "rompe primero el mínimo de ayer")):
        m = D.pd_first == v
        print(f"   {n}: {both(D, m)} % de días · cierra en esa dirección: {both(D[m], (sg(D.c - D.o) == v)[m])} % · cierra más allá del nivel: {both(D[m], ((D.c > D.pdh) if v == 1 else (D.c < D.pdl))[m])} %")

    print("\n5) ¿A qué hora se hace el máximo y el mínimo de la sesión? (% de días)")
    bins = [570, 600, 630, 690, 780, 870, 930, 960]
    lab = ["9:30-10:00", "10:00-10:30", "10:30-11:30", "11:30-13:00", "13:00-14:30", "14:30-15:30", "15:30-16:00"]
    for p in ("24-25", "2026"):
        E = D[D.per == p]
        h = pd.cut(E.t_h, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
        l = pd.cut(E.t_l, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
        print(f"   {p}: extremo (máx o mín) → " + " · ".join(f"{k} {h[k] + l[k]:.0f}%" for k in lab))

    print("\n6) Movimiento de la mañana (9:30-11:30) y la tarde (13:30-16:00): % mismo sentido")
    p1130 = D.p1100 + 0  # aproximación con 11:00
    print("   9:30-11:00 vs 13:30-16:00:", both(D, sg(D.p1100 - D.o) == sg(D.c - D.p1330)))
    big = (D.p1100 - D.o).abs() >= (D.p1100 - D.o).abs().quantile(0.75)
    print("   mañanas grandes (25 % mayor):", both(D[big], (sg(D.p1100 - D.o) == sg(D.c - D.p1330))[big]))

    print("\n7) Hora de almuerzo (12:00-13:30): ¿revierte la mañana?")
    print("   9:30-12:00 vs 12:00-13:30 mismo sentido:", both(D, sg(D.p1200 - D.o) == sg(D.p1330 - D.p1200)))

    print("\n8) Días después de un día de rango chico (rango de ayer en el 25 % menor): rango de hoy vs normal")
    small = D.prng <= D.prng.quantile(0.25)
    for p in ("24-25", "2026"):
        E = D[D.per == p]; s = small[D.per == p]
        print(f"   {p}: rango mediano tras día chico {E.rng[s].median():.0f} vs resto {E.rng[~s].median():.0f}")

    print("\n9) Día de la semana: % de días que cierran arriba de la apertura y rango mediano")
    for k, n in enumerate(["lun", "mar", "mié", "jue", "vie"]):
        m = D.dow == k
        print(f"   {n}: sube {both(D[m], (D.c > D.o)[m])} % · rango {D.rng[m].median():.0f} pts")

    print("\n10) Si el día cae/sube fuerte a las 11:00 (25 % extremo), ¿la tarde rebota o sigue? (pts 11:00→16:00 a favor del movimiento)")
    mv = D.p1100 - D.o
    for lab_, m in (("caída fuerte", mv <= mv.quantile(0.25)), ("subida fuerte", mv >= mv.quantile(0.75))):
        cont = (D.c - D.p1100) * sg(mv)
        print(f"   {lab_}: sigue {both(D[m], (cont > 0)[m])} % · pts promedio {both(D[m], cont[m])}")
    D.to_csv("backtest/resultados/patrones_ny.csv", index=False)


if __name__ == "__main__":
    main()
