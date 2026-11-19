#!/usr/bin/env python3
"""¿Afectan las noticias a los modelos? Días de CPI, PPI y NFP (8:30 NY, antes de las entradas) y de FOMC (14:00 NY,
con la operación abierta) contra los días sin esas noticias. Calendario en backtest/noticias.py.
    python3 backtest/modelo_b/noticias_efecto.py <operaciones.json de Más dinero>
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import noticias as N  # noqa: E402
import confirmaciones as cf  # noqa: E402
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

def tipo(f):
    t = [n for n, L in (("CPI", N.CPI), ("PPI", N.PPI), ("NFP", N.NFP), ("FOMC", N.FOMC)) if f in L]
    return t

def tabla(nombre, fechas, u):
    u = np.asarray(u, float); f = list(fechas)
    pf = lambda v: round(v[v > 0].sum() / -v[v <= 0].sum(), 2) if (v <= 0).any() and len(v) else None
    grupos = {"Todos": np.ones(len(u), bool)}
    for n in ("CPI", "PPI", "NFP", "FOMC"):
        grupos[f"Día de {n}"] = np.array([n in tipo(x) for x in f])
    grupos["Noticia a las 8:30 (CPI, PPI o NFP)"] = np.array([any(n in tipo(x) for n in ("CPI", "PPI", "NFP")) for x in f])
    grupos["Sin ninguna de estas noticias"] = np.array([not tipo(x) for x in f])
    out = []
    for gname, m in grupos.items():
        v = u[m]
        out.append(dict(modelo=nombre, grupo=gname, ops=int(m.sum()), ganadoras=round((v > 0).mean() * 100, 1) if len(v) else None,
                        pf=pf(v), por_op=round(v.mean()) if len(v) else None, neto=round(v.sum())))
    return out

ops = json.load(open(sys.argv[1]))["rows"]
rows = tabla("Más dinero (2 ES)", [o["fecha"] for o in ops], [o["usd_2es"] for o in ops])
raw = bars(str(HERE.parent / "datos")); Fx = cf.features(raw)
Fx = Fx[(Fx.entrada == 540) & Fx["Últimos 12 min a favor"] & Fx["Noche 20-50 pts"]]
days = {x[0]: x for x in g.prep(raw)}; fs, us = [], []
for r in Fx.itertuples():
    t = g.run([days[r.fecha]], 60, "parcial 1:1 + BE + 2R", 540, 20)
    if len(t):
        fs.append(str(r.fecha)); us.append(float(t.R.iloc[0]) * 150)
rows += tabla("SP500 9:00 con confirmación (2 MES)", fs, us)
T = pd.DataFrame(rows); T.to_csv("backtest/resultados/noticias_efecto.csv", index=False)
pd.set_option("display.width", 200); print(T.to_string(index=False))
