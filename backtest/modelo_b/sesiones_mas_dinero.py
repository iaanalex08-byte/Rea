#!/usr/bin/env python3
"""Modelo B "Más dinero" en las sesiones de Sídney, Tokio, Londres y Nueva York (ES real 1 min, ene 2024 – 4 nov 2026).

Reglas del indicador ModeloB.cs adaptadas a cada sesión (hora local con su horario de verano):
  entrada a mercado N min después de la apertura (42 = como las 10:12 en NY; también 102);
  dirección: precio contra la EMA 20 de 3 min (serie continua);
  A: fuera del área de valor (70 %) del perfil de VOLUMEN de la misma sesión del día anterior;
  C: el perfil de volumen de hoy (apertura hasta la entrada) sin forma P al comprar ni b al vender;
  sin BOS de 3 min en contra en los 60 min previos; VWAP de la sesión a favor;
  bracket 30/40/160 ticks sin break-even (y una versión escalada a la volatilidad de la sesión); cierre al final de la sesión.
2 ES, 34 USD de costo por operación.
    python3 backtest/modelo_b/sesiones_mas_dinero.py <carpeta de salida>
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
from engine import ema3, TICK  # noqa: E402
from estructura import velas, eventos  # noqa: E402
from sesiones import SESIONES, met  # noqa: E402
from sp500_0912 import bars  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "backtest/resultados/dashboard_sesiones_md"); OUT.mkdir(parents=True, exist_ok=True)


def main():
    raw = bars(str(HERE.parent / "datos")).rename(columns={"open": "o", "high": "h", "low": "l", "close": "c", "volume": "v"})
    raw.index = raw.index.tz_convert("UTC")
    ema = ema3(raw[["o", "h", "l", "c"]], 20, 3)
    ev = eventos(velas(raw[["o", "h", "l", "c"]], 3))
    tB = np.array([e[0] for e in ev if e[1] == "BOS"]); sB = np.array([e[2] for e in ev if e[1] == "BOS"])
    base = {}
    for nom, (tz, ini, fin) in SESIONES.items():
        loc = raw.index.tz_convert(tz); mm = loc.hour * 60 + loc.minute
        a = int(ini[:2]) * 60 + int(ini[3:]); b = int(fin[:2]) * 60 + int(fin[3:])
        x = raw[(mm >= a) & (mm < b)].copy(); x["d"] = loc[(mm >= a) & (mm < b)].date
        ses = {d: g for d, g in x.groupby("d") if len(g) >= 0.8 * (b - a) and pd.Timestamp(d).dayofweek < 5}
        base[nom] = (ses, float(np.median([g.h.max() - g.l.min() for g in ses.values()])))
    rango_ny = base["Nueva York"][1]
    filas, ops = [], []
    for nom, (ses, rango) in base.items():
        fechas = sorted(ses)
        prof = {d: pv.perfil(g.l.values, g.h.values, g.v.values) for d, g in ses.items()}
        for offset in (42, 102):
            D = []
            for i in range(1, len(fechas)):
                d, prev = fechas[i], fechas[i - 1]
                g = ses[d]
                if (pd.Timestamp(d) - pd.Timestamp(prev)).days > 4 or len(g) <= offset + 5:
                    continue
                t0 = g.index[offset]; dev = g.iloc[:offset]; ent = g.o.values[offset]
                e = ema.asof(t0)
                if np.isnan(e):
                    continue
                s = 1 if ent > e else -1
                y = prof[prev]; hoy = pv.perfil(dev.l.values, dev.h.values, dev.v.values)
                A = ent > y["vah"] or ent < y["val"]
                C = (hoy["pos"] if s == 1 else 1 - hoy["pos"]) <= 0.62
                t0n = np.datetime64(t0.tz_localize(None))
                mk = (tB > t0n - np.timedelta64(60, "m")) & (tB <= t0n)
                B = not (sB[mk] == -s).any()
                tp = (dev.h + dev.l + dev.c) / 3
                vw = (tp * dev.v).sum() / max(dev.v.sum(), 1)
                W = (ent - vw) * s > 0
                rest = g.iloc[offset:]
                H, L, O, Cc = rest.h.values, rest.l.values, rest.o.values, rest.c.values
                D.append(dict(date=str(d), dir=s, up=((H - ent) if s == 1 else (ent - L)) / TICK, dn=((L - ent) if s == 1 else (ent - H)) / TICK,
                              op=(O - ent) * s / TICK, cl=(Cc[-1] - ent) * s / TICK, pasa=A and C and B and W))
            yrs = np.array([d["date"][:4] for d in D])
            for br_nom, k in (("30/40/160 (igual que NY)", 1.0), ("escalado a la volatilidad de la sesión", rango / rango_ny)):
                br = (max(4, round(30 * k)), max(4, round(40 * k)), max(8, round(160 * k)))
                U = np.array([rf.bracket(d, *br, be=False) for d in D])
                P = np.array([d["pasa"] for d in D])
                for filtro, m in (("Solo EMA", np.ones(len(D), bool)), ("Todos los filtros (el modelo)", P)):
                    r = met(U[m], yrs[m])
                    filas.append(dict(clave=f"{nom}|{offset}|{br_nom}|{filtro}", sesion=nom, minutos=offset, bracket=br_nom,
                                      sl_tp=f"{br[0]}/{br[1]}/{br[2]}", filtro=filtro, rango_mediano_pts=round(rango, 1), **r))
                    if offset == 42 and k == 1.0 and filtro.startswith("Todos"):
                        sacum = 0.0
                        for d, u in zip([d for d, x in zip(D, m) if x], U[m]):
                            sacum += u; ops.append(dict(sesion=nom, fecha=d["date"], usd=round(float(u), 2), saldo=round(sacum, 2)))
    T = pd.DataFrame(filas); T.to_csv("backtest/resultados/mas_dinero_sesiones.csv", index=False)
    meta = [{"label": "sesiones_mas_dinero.py", "value": Path(__file__).read_text(), "type": "code", "lang": "python"},
            {"label": "Entrada", "value": "Velas de 1 min de ES (NinjaTrader), ene 2024 – 4 nov 2026"}]
    (OUT / "sesiones_resumen.json").write_text(json.dumps({"rows": filas, "meta": meta}, ensure_ascii=False))
    (OUT / "sesiones_ops.json").write_text(json.dumps({"rows": ops, "meta": meta}, ensure_ascii=False))
    pd.set_option("display.width", 260); print(T.drop(columns=["clave"]).to_string(index=False))


if __name__ == "__main__":
    main()
