#!/usr/bin/env python3
"""Datos del dashboard "Modelo B · Más dinero" (el modelo del indicador ModeloB.cs):
10:12 NY, EMA 20 de 3 min, A y C por perfil de volumen, sin BOS en contra (3 min, 60 min), VWAP a favor,
SL 30 · TP1 40 · TP2 160 ticks sin break-even, cierre 15:59 NY. ES real 1 min (ene 2024 – 4 nov 2026).
    python3 backtest/modelo_b/dashboard_mas_dinero.py <carpeta de salida>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "backtest/resultados/dashboard_mas_dinero"); OUT.mkdir(parents=True, exist_ok=True)
CODE = Path(__file__).read_text()
BR = (30, 40, 160, False)
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes"]


def guardar(nombre, rows, entrada):
    meta = [{"label": "dashboard_mas_dinero.py", "value": CODE, "type": "code", "lang": "python"}, {"label": "Entrada", "value": entrada},
            {"label": "Reglas", "value": "10:12 NY · EMA 20 de 3 min · A y C por perfil de volumen · sin BOS en contra · VWAP a favor · SL 30, TP1 40, TP2 160 ticks sin BE · 2 ES y 34 USD de costo; 8 MES y 2.49 USD por MES"}]
    (OUT / nombre).write_text(json.dumps({"rows": rows, "meta": meta}, ensure_ascii=False))


df = cargar()
F = dias_ny(df, 10, 12, 20, 3)
bc = bos_contra(F, eventos(velas(df, 3)))
V = pv.rasgos_volumen(F)
F = [d for d in F if d["date"] in V]
f = pd.DataFrame([V[d["date"]] for d in F])
A = f.A_vol.values; C = f.C_vol.values; B = np.array([not bc[d["date"]] for d in F]); W = f["VWAP a favor"].values
U = np.array([rf.bracket(d, *BR[:3], be=BR[3]) for d in F])
pf = lambda u: round(float(u[u > 0].sum() / -u[u <= 0].sum()), 2)
emb = []
for paso, m in (("Días hábiles con datos", np.ones(len(F), bool)), ("A: fuera del valor de ayer", A), ("C: perfil de hoy no ya a favor", A & C),
                ("Sin BOS en contra", A & C & B), ("VWAP a favor (se opera)", A & C & B & W)):
    emb.append(dict(paso=paso, dias=int(m.sum()), pf=pf(U[m]), ganadoras=round(float((U[m] > 0).mean() * 100), 1), neto=int(round(U[m].sum()))))
guardar("embudo.json", emb, "Cada paso: días que siguen después del filtro y cómo les fue con el bracket 30/40/160 en 2 ES")

m = A & C & B & W
rows, s2, s8 = [], 0.0, 0.0
for d, u in zip([d for d, k in zip(F, m) if k], U[m]):
    ticks = (u + 34) / 12.5
    u8 = ticks * 4 * 1.25 - 8 * 2.49
    s2 += u; s8 += u8
    fecha = pd.Timestamp(d["date"])
    rows.append(dict(fecha=d["date"], anio=d["date"][:4], mes=d["date"][:7], dia=DIAS[fecha.dayofweek], direccion="Compra" if d["dir"] == 1 else "Venta",
                     salida=rf.salida(d, *BR[:3]).replace("Stop (−2)", "Stop"), ticks=round(float(ticks), 2), usd_2es=round(float(u), 2),
                     usd_8mes=round(float(u8), 2), saldo_2es=round(s2, 2), saldo_8mes=round(s8, 2), gana=bool(u > 0)))
guardar("operaciones.json", rows, "Una fila por operación del modelo, en orden")
fo = pd.read_csv("backtest/resultados/modelo_b_fondeo.csv")
fo = fo[fo.version == "Más dinero 30/40/160 sin BE"]
guardar("fondeo.json", [dict(mes=int(r.mes), riesgo_sl=int(r.riesgo_sl), pasa_pct=float(r.pasa_pct), ops_para_pasar=int(r.ops_para_pasar),
                             retira_1000_pct=float(r.retira_1000_pct), intentos=int(r.intentos)) for r in fo.itertuples()],
        "modelo_b_fondeo.csv (fondeo.py): evaluación Lucid 50K Flex simulada desde cada operación; meta 3,000, caída 2,000 al cierre, consistencia 40 %")
u = np.array([r["usd_2es"] for r in rows]); print(len(rows), pf(u), round((u > 0).mean() * 100, 1), round(u.sum())); print(emb)
