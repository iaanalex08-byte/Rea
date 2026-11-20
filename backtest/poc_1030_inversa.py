#!/usr/bin/env python3
"""NQ POC: ¿a favor, al revés o en otro horario? Velas de 3 min, perfil de 12 min, salida única, cierre 14:30 CDMX.

Modos:
  favor : la normal (dirección = medianoche -> inicio del perfil; ruptura y retroceso al POC a favor).
  dir   : dirección invertida (día alcista -> se buscan ventas: ruptura bajista y retroceso al POC).
  fade  : la misma ruptura que la normal, pero en el retroceso al POC se entra al revés.
Horarios (CDMX): 7:30 a 12:00. SL 30 / 45 / 66.5 / 90 pts. R:R 1, 1.5, 2, 3.
Robusta = gana en 2024-25 y en 2026.

    python3 backtest/poc_1030_inversa.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import combinado_nq as cn  # noqa: E402
import poc_backtest as pb  # noqa: E402

HORAS = ["07:30", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00"]
MODOS = {"favor": "no", "dir": "dir", "fade": "fade"}
SLS = [30, 45, 66.5, 90]
RRS = [1.0, 1.5, 2.0, 3.0]


def trades(h, sl, rr, modo):
    hh, mm = map(int, h.split(":"))
    ws = hh * 60 + mm + 12
    orig = pb.parse_args
    def patched(argv):  # noqa: E306
        a = orig(argv); a.contra = MODOS[modo]; return a
    pb.parse_args = patched
    try:
        return cn.trades({"tf": 3, "ph": hh, "pm": mm, "dur": 12, "ws": f"{ws // 60:02d}:{ws % 60:02d}", "sl": sl, "rr": rr})
    finally:
        pb.parse_args = orig


def main():
    rows = []
    for h in HORAS:
        for modo in MODOS:
            for sl in SLS:
                for rr in RRS:
                    t = trades(h, sl, rr, modo)
                    if t.empty:
                        continue
                    y = pd.to_datetime(t.date).dt.year
                    usd = t.pts * cn.PV - cn.COM
                    eq = usd.cumsum()
                    rows.append({"hora": h, "modo": modo, "SL": sl, "RR": rr, "ops": len(t),
                                 "acierto %": round(100 * (t.pts > 0).mean(), 1), "R/op": round(t.R.mean(), 3),
                                 "R/op 24-25": round(t.R[y <= 2025].mean(), 3), "R/op 2026": round(t.R[y == 2026].mean(), 3),
                                 "neto $ 1 MNQ": round(usd.sum()), "peor DD $": round((eq.cummax() - eq).max())})
        print(f"{h} listo", file=sys.stderr, flush=True)
    T = pd.DataFrame(rows)
    T["robusta"] = (T["R/op 24-25"] > 0) & (T["R/op 2026"] > 0)
    T.to_csv("backtest/resultados/poc_1030_inversa.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"{len(T)} versiones · robustas {T.robusta.sum()}")
    g = T.groupby(["hora", "modo"])
    print(pd.DataFrame({"robustas": g.robusta.sum(), "de": g.size(), "R/op prom": g["R/op"].mean().round(3),
                        "R 24-25": g["R/op 24-25"].mean().round(3), "R 2026": g["R/op 2026"].mean().round(3)}).unstack("modo").to_string())
    print("\n10:30 por modo, SL y RR:")
    print(T[T.hora == "10:30"].sort_values(["modo", "SL", "RR"]).drop(columns=["hora"]).to_string(index=False))
    print("\nMejores robustas:")
    print(T[T.robusta].sort_values("R/op", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
