#!/usr/bin/env python3
"""Arma los JSON del dashboard "Modelo B en ES real" a partir de los resultados de estructura.py y variaciones.py.
Cada archivo es {rows, meta}; meta lleva este código para que se pueda revisar y volver a correr.
    python3 backtest/modelo_b/estructura.py cdmx && python3 backtest/modelo_b/estructura.py ny
    python3 backtest/modelo_b/variaciones.py
    python3 backtest/modelo_b/dashboard_datos.py <carpeta de salida>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402
from estructura import velas, eventos  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "backtest/resultados/dashboard_modelo_b")
OUT.mkdir(parents=True, exist_ok=True)
RES = Path("backtest/resultados")
CODE = Path(__file__).read_text()


def pf(u):
    u = np.asarray(u, float)
    n = -u[u <= 0].sum()
    return float(u[u > 0].sum() / n) if n > 0 else None


def resumen(clave, nombre, fechas, u):
    u = np.asarray(u, float); f = np.asarray(fechas)
    eq = np.cumsum(u)
    neg = pd.Series((u <= 0).astype(int))
    r = dict(clave=clave, version=nombre, ops=int(len(u)), ganadoras=round(float((u > 0).mean() * 100), 1), pf=round(pf(u), 2),
             neto=int(round(u.sum())), por_op=int(round(u.mean())), caida=int(round((eq - np.maximum.accumulate(np.maximum(eq, 0))).min())),
             peor_racha=int(neg.groupby((neg != neg.shift()).cumsum()).sum().max()))
    mes = pd.Series(u).groupby(pd.Series(f).str[:7]).sum()
    r["meses_pos"] = int((mes > 0).sum()); r["meses"] = int(len(mes))
    for a in ("2024", "2025", "2026"):
        m = np.char.startswith(f.astype(str), a)
        r[f"pf_{a}"] = round(pf(u[m]), 2) if m.any() else None
        r[f"neto_{a}"] = int(round(u[m].sum()))
    return r


def guardar(nombre, rows, entrada):
    meta = [{"label": "dashboard_datos.py", "value": CODE, "type": "code", "lang": "python"},
            {"label": "Entrada", "value": entrada},
            {"label": "Reglas", "value": "ES real 1 min (ene 2024 – 4 nov 2026), 2 ES, 34 USD de costo por operación, stop primero si stop y objetivo caen en la misma vela, cierre 15:59 NY"}]
    (OUT / nombre).write_text(json.dumps({"rows": rows, "meta": meta}, ensure_ascii=False))


df = cargar()
cd = pd.read_csv(RES / "modelo_b_dias_cdmx.csv"); ny = pd.read_csv(RES / "modelo_b_dias_ny.csv")
F = dias_ny(df, 10, 12, 20, 3)
bc = bos_contra(F, eventos(velas(df, 3)))
M = [d for d in F if d["loc"] != "dentro del valor" and d["forma"] != "a favor (P/b)" and not bc[d["date"]]]
mej_no = [(d["date"], float(rf.bracket(d, 30, 40, 160, be=False))) for d in M]
mej_si = [(d["date"], float(rf.bracket(d, 30, 40, 160, be=True))) for d in M]

vers = [
    resumen("original_cdmx", "Original · 9:12 CDMX · 35/30/120", cd[cd.pasa].date, cd[cd.pasa].usd),
    resumen("original_ny", "Original · 10:12 NY · 35/30/120", ny[ny.pasa].date, ny[ny.pasa].usd),
    resumen("sin_bos_ny", "10:12 NY + sin BOS en contra · 35/30/120", ny[ny.pasa & ~ny["3m_BOS_60_contra"].astype(bool)].date,
            ny[ny.pasa & ~ny["3m_BOS_60_contra"].astype(bool)].usd),
    resumen("mejorado_be", "Mejorado · 30/40/160 con BE", [a for a, _ in mej_si], [b for _, b in mej_si]),
    resumen("mejorado", "Mejorado · 30/40/160 sin BE", [a for a, _ in mej_no], [b for _, b in mej_no]),
]
guardar("versiones.json", vers, "modelo_b_dias_cdmx.csv, modelo_b_dias_ny.csv y el Modelo B a las 10:12 NY recalculado aquí")

ops = []
for clave, fechas, u in (("original_cdmx", cd[cd.pasa].date.tolist(), cd[cd.pasa].usd.tolist()),
                         ("mejorado", [a for a, _ in mej_no], [b for _, b in mej_no])):
    s = 0.0
    for i, (f, x) in enumerate(zip(fechas, u)):
        s += x
        ops.append(dict(clave=clave, n=i + 1, fecha=f, usd=round(x, 2), saldo=round(s, 2)))
guardar("operaciones.json", ops, "Operación por operación del original (9:12 CDMX) y del mejorado (10:12 NY, 30/40/160 sin BE)")

E = []
for v, nom in (("cdmx", "9:12 CDMX"), ("ny", "10:12 NY")):
    S = pd.read_csv(RES / f"modelo_b_estructura_{v}.csv")
    S = S[S.base == "EMA + A + C (el modelo)"]
    for f, et in (("— sin filtro de estructura —", "Sin filtro (base)"), ("SIN 3m_BOS_60_contra", "Saltar si hubo BOS en contra (3 min, última hora)"),
                  ("5m_BOS_60_favor", "BOS a favor (5 min, última hora)"), ("3m_FVG_30_favor", "FVG a favor (3 min, 30 min)"),
                  ("5m_FVG_30_favor", "FVG a favor (5 min, 30 min)"), ("3m_CHOCH_60_favor", "CHOCH a favor (3 min, última hora)"),
                  ("5m_CHOCH_30_favor", "CHOCH a favor (5 min, 30 min)"), ("3m_(BOS o CHOCH) + FVG_30_favor", "BOS o CHOCH + FVG (3 min, 30 min)")):
        if f == "SIN 3m_BOS_60_contra":
            T = cd if v == "cdmx" else ny
            x = T[T.pasa & ~T["3m_BOS_60_contra"].astype(bool)]
            r = resumen(f, et, x.date, x.usd)
        else:
            row = S[S.filtro == f].iloc[0]
            r = dict(ops=int(row.ops), pf=round(row.pf, 2), neto=int(row.neto), pf_2024=round(row.pf_2024, 2), pf_2025=round(row.pf_2025, 2), pf_2026=round(row.pf_2026, 2))
        E.append(dict(clave=f"{v}|{f}", hora=nom, confirmacion=et, ops=r["ops"], pf=r["pf"], neto=r["neto"],
                      pf_2024=r["pf_2024"], pf_2025=r["pf_2025"], pf_2026=r["pf_2026"]))
guardar("estructura.json", E, "modelo_b_estructura_cdmx.csv y modelo_b_estructura_ny.csv (filtros sobre EMA + A + C)")

G = pd.read_csv(RES / "modelo_b_variaciones.csv")
z = G[(G.hora_ny == "10:12") & (G.ema == "EMA 20 de 3 min") & (G.filtro == "A + C sin BOS en contra") & (G.tp2 == 160)]
Z = [dict(clave=f"{r.be}|{r.sl}|{r.tp1}", be=r.be, sl=int(r.sl), tp1=int(r.tp1), pf=round(r.pf, 2),
          pf_peor=round(min(r.pf_2024, r.pf_2025, r.pf_2026), 2), neto=int(r.neto)) for r in z.itertuples()]
guardar("zona.json", Z, "modelo_b_variaciones.csv: 10:12 NY, EMA 20 de 3 min, A + C sin BOS en contra, TP2 160")

h = G[(G.ema == "EMA 20 de 3 min") & (G.filtro == "A + C sin BOS en contra") & (G.sl == 35) & (G.tp1 == 30) & (G.tp2 == 120) & (G.be == "sí")]
orden = ["9:45", "10:00", "10:12", "10:30", "10:45", "11:00", "11:12", "11:30"]
H = [dict(hora=r.hora_ny, orden=orden.index(r.hora_ny), ops=int(r.ops), pf=round(r.pf, 2), neto=int(r.neto),
          pf_2024=round(r.pf_2024, 2), pf_2025=round(r.pf_2025, 2), pf_2026=round(r.pf_2026, 2)) for r in h.itertuples()]
H.sort(key=lambda r: r["orden"])
guardar("horas.json", H, "modelo_b_variaciones.csv: EMA 20 de 3 min, A + C sin BOS en contra, 35/30/120 con BE")

t = G[G.ops >= 150].sort_values("pf_elegir", ascending=False).head(100)
P = [dict(rango=i + 1, pf_2024_2025=round(r.pf_elegir, 2), pf_2026=round(r.pf_2026, 2), neto_2026=int(r.neto_2026)) for i, r in enumerate(t.itertuples())]
guardar("sobreajuste.json", P, "modelo_b_variaciones.csv: las 100 variaciones con mejor PF mínimo de 2024 y 2025 (150 operaciones o más) y su PF en 2026")
for r in vers: print(r)
