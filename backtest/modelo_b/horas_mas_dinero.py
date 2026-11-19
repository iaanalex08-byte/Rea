#!/usr/bin/env python3
"""Modelo B "Más dinero" a otras horas de entrada en Nueva York (mismos filtros y bracket 30/40/160 sin BE).
Busca horas que también funcionen para sumar operaciones. Cuenta como buena si el PF pasa de 1.1 en 2024, 2025 y 2026.
    python3 backtest/modelo_b/horas_mas_dinero.py
Salida: backtest/resultados/mas_dinero_horas.csv
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402

df = cargar(); ev = eventos(velas(df, 3)); filas = []
for h, m in ((10, 0), (10, 12), (10, 30), (10, 45), (11, 0), (11, 15), (11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0), (14, 30)):
    F = dias_ny(df, h, m, 20, 3); bc = bos_contra(F, ev); V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]; f = pd.DataFrame([V[d["date"]] for d in F])
    if f.empty:   # antes de 20 min de sesión no hay perfil de hoy suficiente
        continue
    mk = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    D = [d for d, x in zip(F, mk) if x]
    u = np.array([rf.bracket(d, 30, 40, 160, be=False) for d in D]); y = np.array([d["date"][:4] for d in D])
    r = pv.met(u, y); r["robusta"] = all((r[f"pf_{a}"] or 0) > 1.1 for a in ("2024", "2025", "2026"))
    filas.append(dict(hora_ny=f"{h}:{m:02d}", hora_cdmx_invierno=f"{h-1}:{m:02d}", **r))
    print(filas[-1], flush=True)
T = pd.DataFrame(filas); T.to_csv("backtest/resultados/mas_dinero_horas.csv", index=False)
pd.set_option("display.width", 220); print(T.to_string(index=False))
