#!/usr/bin/env python3
"""Análisis de patrones y variantes de la estrategia POC Apertura CDMX.

    python3 backtest/analisis.py backtest/datos --start 2024-01-01 --end 2026-11-04
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402


def excursions(df, tr):
    """MFE/MAE en puntos desde la entrada hasta la salida (sin contar la vela de entrada)."""
    H, L = df["high"].to_numpy(), df["low"].to_numpy()
    pos = {t: k for k, t in enumerate(df.index)}
    mfe, mae, mfe_after_tp1 = [], [], []
    for t in tr.itertuples():
        a = t.entry_idx + 1
        b = pos.get(t.exit_time, a)
        d = 1 if t.dir == "COMPRA" else -1
        hh, ll = H[a:b + 1], L[a:b + 1]
        if len(hh) == 0:
            mfe.append(np.nan); mae.append(np.nan); mfe_after_tp1.append(np.nan); continue
        fav = (hh - t.entry) if d == 1 else (t.entry - ll)
        adv = (t.entry - ll) if d == 1 else (hh - t.entry)
        mfe.append(fav.max()); mae.append(adv.max())
        mfe_after_tp1.append(fav.max() if t.partial else np.nan)
    tr = tr.copy()
    tr["mfe"], tr["mae"], tr["mfe_tp1"] = mfe, mae, mfe_after_tp1
    return tr


def table(tr, by, name):
    g = tr.groupby(by, observed=True)
    out = pd.DataFrame({
        "ops": g.size(),
        "ganadas": g.apply(lambda x: (x.result == "GANADA").sum()),
        "parc_be": g.apply(lambda x: (x.result == "PARCIAL + BE").sum()),
        "perdidas": g.apply(lambda x: (x.result == "PERDIDA").sum()),
        "%perd": g.apply(lambda x: 100 * (x.result == "PERDIDA").mean()),
        "pts/op": g["pts"].mean(),
        "neto_pts": g["pts"].sum(),
    })
    print(f"\n--- {name} ---")
    print(out.round(2).to_string())


def main():
    argv = sys.argv[1:]
    a = pb.parse_args(argv)
    df = pb.load_bars(a.csv, a.input_tz, a.tz, a.tf, a.nt_tz)
    df = df[(df.index >= pd.Timestamp(a.start, tz=a.tz)) & (df.index < pd.Timestamp(a.end, tz=a.tz) + pd.Timedelta(days=1))]
    df, _ = pb.filter_days(df, a)
    tr, _ = pb.run(df, a)
    tr = excursions(df, tr)
    tr["hora"] = tr.entry_time.dt.strftime("%H").astype(int).map(lambda h: f"{h:02d}:00")
    tr["espera_min"] = (tr.entry_time - tr.brk_time).dt.total_seconds() / 60
    tr["dia"] = tr.entry_time.dt.day_name()
    tr["anio"] = tr.entry_time.dt.year
    tr["tend_abs"] = tr.trend_pts.abs()
    print(f"{len(tr)} operaciones")
    table(tr, "dir", "Dirección")
    table(tr, ["anio", "dir"], "Año y dirección")
    table(tr, "hora", "Hora de entrada")
    table(tr, pd.cut(tr.espera_min, [0, 15, 30, 60, 120, 600]), "Minutos entre ruptura y retroceso")
    table(tr, pd.qcut(tr.tend_abs, 4), "Fuerza de la tendencia previa (pts)")
    table(tr, pd.qcut(tr.prof_range, 4), "Rango del perfil 9:00-9:12 (pts)")
    table(tr, "dia", "Día de la semana")
    l = tr[tr.result == "PERDIDA"]
    print("\n--- Perdidas: avance a favor antes del SL (MFE, pts) ---")
    print(l.mfe.describe(percentiles=[.25, .5, .75, .9]).round(2).to_string())
    print("Perdidas que avanzaron >= 4.5 pts a favor:", (l.mfe >= 4.5).sum(), "de", len(l))
    print("Perdidas que avanzaron >= 6 pts a favor:", (l.mfe >= 6).sum(), "de", len(l))
    be = tr[tr.result == "PARCIAL + BE"]
    print("\n--- Parcial + BE: máximo a favor antes de volver a la entrada (pts) ---")
    print(be.mfe_tp1.describe(percentiles=[.25, .5, .75, .9]).round(2).to_string())
    for lvl in [13.5, 15, 18]:
        print(f"Parcial+BE que llegaron a {lvl} pts:", (be.mfe_tp1 >= lvl).sum(), "de", len(be))
    w = tr[tr.result.isin(["GANADA", "PARCIAL + BE"])]
    print("\n--- Ganadas y Parcial+BE: retroceso en contra antes del TP1 (MAE, pts) ---")
    print(w.mae.describe(percentiles=[.5, .75, .9]).round(2).to_string())
    tr.to_csv(Path(a.out) / "operaciones_detalle.csv", index=False) if Path(a.out).exists() else None


if __name__ == "__main__":
    main()
