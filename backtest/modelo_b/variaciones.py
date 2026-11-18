#!/usr/bin/env python3
"""Variaciones del Modelo B en ES real (ene 2024 – 4 nov 2026), con la hora fija en Nueva York para que el horario
de verano no cambie la regla (en invierno CDMX = NY - 1 h, en verano CDMX = NY - 2 h).

Se varía: hora de entrada (NY), EMA (largo y temporalidad), filtros (ninguno, A, C, A + C, A + C sin BOS en contra),
bracket (SL, TP1, TP2 en ticks) y break-even tras TP1. 2 ES, 34 USD de costo por operación, velas de 1 min,
stop primero si stop y objetivo caen en la misma vela (motor de la rama ccr-f8177091-hrh8wn, sin cambios).

Para no engañarse con el sobreajuste:
  - se elige con 2024 + 2025 (PF mínimo de los dos años) y 2026 se usa como prueba que no se miró para elegir;
  - "robusta" = PF > 1.1 en cada uno de los tres años y al menos 60 operaciones por año.

    python3 backtest/modelo_b/variaciones.py
Salida: backtest/resultados/modelo_b_variaciones.csv
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import rejilla_filtro as rf  # noqa: E402
from mejoras import con_filtros  # noqa: E402
from estructura import cargar, velas, eventos, verano  # noqa: E402

HORAS_NY = [(9, 45), (10, 0), (10, 12), (10, 30), (10, 45), (11, 0), (11, 12), (11, 30)]
EMAS = [(20, 3), (9, 3), (50, 3), (20, 5), (20, 1), (20, 15)]
SLS = [25, 30, 35, 40, 45, 50, 60]
TP1S = [20, 25, 30, 40]
TP2S = [60, 80, 120, 160]
FILTROS = ["ninguno", "A", "C", "A + C", "A + C sin BOS en contra"]


def dias_ny(df, h, m, ema_len, ema_tf):
    """Un día por fecha con la entrada a la hora NY dada."""
    out = {}
    for desfase, es_verano in ((60, False), (120, True)):
        mm = h * 60 + m - desfase
        hm = (mm // 60, mm % 60)
        D = rf.dias(df, ema_len=ema_len, ema_tf=ema_tf, hm=hm)
        for d in con_filtros(df, D, hm=hm):
            if verano(d["date"]) == es_verano:
                out[d["date"]] = dict(d, hm=hm)
    return [out[k] for k in sorted(out)]


def bos_contra(F, ev3):
    """True si en los 60 min previos a la entrada hubo un BOS de 3 min en contra de la operación."""
    t = np.array([e[0] for e in ev3 if e[1] == "BOS"])
    s = np.array([e[2] for e in ev3 if e[1] == "BOS"])
    res = {}
    for d in F:
        t0 = pd.Timestamp(f"{d['date']} {d['hm'][0]:02d}:{d['hm'][1]:02d}", tz="America/Mexico_City").tz_convert("UTC").tz_localize(None)
        hi, lo = np.datetime64(t0), np.datetime64(t0 - pd.Timedelta(minutes=60))
        m = (t > lo) & (t <= hi)
        res[d["date"]] = bool((s[m] == -d["dir"]).any())
    return res


def pf(u):
    neg = -u[u <= 0].sum()
    return u[u > 0].sum() / neg if neg > 0 else np.inf


def main():
    df = cargar()
    ev3 = eventos(velas(df, 3))
    filas = []
    for (h, m), (el, et) in itertools.product(HORAS_NY, EMAS):
        F = dias_ny(df, h, m, el, et)
        bc = bos_contra(F, ev3)
        yrs = np.array([d["date"][:4] for d in F])
        A = np.array([d["loc"] != "dentro del valor" for d in F])
        C = np.array([d["forma"] != "a favor (P/b)" for d in F])
        B = np.array([not bc[d["date"]] for d in F])
        masks = {"ninguno": np.ones(len(F), bool), "A": A, "C": C, "A + C": A & C, "A + C sin BOS en contra": A & C & B}
        for sl, tp1, tp2, be in itertools.product(SLS, TP1S, TP2S, (True, False)):
            if tp2 <= tp1:
                continue
            u_all = np.array([rf.bracket(d, sl, tp1, tp2, be=be) for d in F])
            for fn in FILTROS:
                mk = masks[fn]
                u, y = u_all[mk], yrs[mk]
                if len(u) < 120:
                    continue
                eq = np.cumsum(u)
                row = dict(hora_ny=f"{h}:{m:02d}", ema=f"EMA {el} de {et} min", filtro=fn, sl=sl, tp1=tp1, tp2=tp2, be="sí" if be else "no",
                           ops=len(u), ganadoras=(u > 0).mean() * 100, pf=pf(u), neto=u.sum(), por_op=u.mean(),
                           caida=(eq - np.maximum.accumulate(np.maximum(eq, 0))).min())
                for a in ("2024", "2025", "2026"):
                    v = u[y == a]
                    row[f"pf_{a}"] = pf(v) if len(v) else np.nan
                    row[f"ops_{a}"] = len(v)
                    row[f"neto_{a}"] = v.sum()
                filas.append(row)
        print(f"{h}:{m:02d} EMA {el}/{et} listo", file=sys.stderr, flush=True)
    G = pd.DataFrame(filas)
    G["pf_elegir"] = G[["pf_2024", "pf_2025"]].min(axis=1)
    G["robusta"] = (G[["pf_2024", "pf_2025", "pf_2026"]].min(axis=1) > 1.1) & (G[["ops_2024", "ops_2025", "ops_2026"]].min(axis=1) >= 60)
    G.to_csv("backtest/resultados/modelo_b_variaciones.csv", index=False)
    print(len(G), "variaciones")


if __name__ == "__main__":
    main()
