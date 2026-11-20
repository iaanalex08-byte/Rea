#!/usr/bin/env python3
"""Modelo B: ¿qué pasa si, cuando el perfil de volumen de hoy ya está a favor (forma P al comprar o b al vender),
en lugar de cancelar se opera AL REVÉS? (P con compra -> venta; b con venta -> compra).

Perfil de hoy: desde las 9:30 NY hasta la entrada (10:12 NY), o solo los primeros 30 min (9:30–10:00 NY).
Forma: POC en el 38 % de arriba del rango = P; en el 38 % de abajo = b; en medio = D.
Base: ES real 1 min, 10:12 NY, EMA 20 de 3 min, filtro A por volumen (fuera del valor de ayer), 2 ES, 34 USD.

    python3 backtest/modelo_b/reversa_pb.py
Salida: backtest/resultados/modelo_b_reversa_pb.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import perfil_volumen as pv  # noqa: E402
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar, velas, eventos, verano  # noqa: E402
from sp500_0912 import bars  # noqa: E402

BRACKETS = {"30/40/160 sin BE": (30, 40, 160, False), "35/30/120 con BE": (35, 30, 120, True), "40/20/120 con BE": (40, 20, 120, True)}


def dias_lado(df, lado):
    """Días a las 10:12 NY con la dirección forzada (lado = 1, -1) o por EMA (None)."""
    out = {}
    for desfase, es_verano in ((60, False), (120, True)):
        mm = 10 * 60 + 12 - desfase
        hm = (mm // 60, mm % 60)
        for d in rf.dias(df, hm=hm, lado=lado):
            if verano(d["date"]) == es_verano:
                out[d["date"]] = dict(d, hm=hm)
    return out


def rasgos(E):
    raw = bars(str(HERE.parent / "datos"))
    raw.index = raw.index.tz_convert("America/New_York")
    m = raw.index.hour * 60 + raw.index.minute
    rth = raw[(m >= 570) & (m < 960)].copy()
    rth["d"] = rth.index.date
    ses = {d: g for d, g in rth.groupby("d") if len(g) >= 200}
    fechas = sorted(ses)
    prof = {d: pv.perfil(g.low.values, g.high.values, g.volume.values) for d, g in ses.items()}
    out = {}
    for fecha_s, d in E.items():
        fecha = pd.Timestamp(fecha_s).date()
        t0 = pd.Timestamp(f"{fecha_s} {d['hm'][0]:02d}:{d['hm'][1]:02d}", tz="America/Mexico_City").tz_convert("America/New_York")
        prev = [f for f in fechas if f < fecha]
        g = rth[rth.d == fecha]
        dev = g[g.index < t0]
        if len(prev) < 2 or len(dev) < 30:
            continue
        y = prof[prev[-1]]
        p30 = dev[dev.index < dev.index[0] + pd.Timedelta(minutes=30)]
        tp = (dev.high + dev.low + dev.close) / 3
        out[fecha_s] = dict(fuera=d["entry"] > y["vah"] or d["entry"] < y["val"],
                            pos_dev=pv.perfil(dev.low.values, dev.high.values, dev.volume.values)["pos"],
                            pos_30=pv.perfil(p30.low.values, p30.high.values, p30.volume.values)["pos"],
                            vwap=(tp * dev.volume).sum() / dev.volume.sum())
    return out


def forma(pos, s):
    """'a favor' (P al comprar / b al vender), 'en contra' o 'D'."""
    p = pos if s == 1 else 1 - pos
    return "a favor" if p > 0.62 else ("en contra" if p < 0.38 else "D")


def main():
    df = cargar()
    E = dias_lado(df, None)
    C = dias_lado(df, 1)
    V = dias_lado(df, -1)
    R = rasgos(E)
    ev = eventos(velas(df, 3))
    tB = np.array([e[0] for e in ev if e[1] == "BOS"]); sB = np.array([e[2] for e in ev if e[1] == "BOS"])

    def bos_contra(fecha, hm, s):
        t0 = pd.Timestamp(f"{fecha} {hm[0]:02d}:{hm[1]:02d}", tz="America/Mexico_City").tz_convert("UTC").tz_localize(None)
        mk = (tB > np.datetime64(t0 - pd.Timedelta(minutes=60))) & (tB <= np.datetime64(t0))
        return bool((sB[mk] == -s).any())

    filas = []
    for perfil_nom, campo in (("perfil 9:30 hasta la entrada", "pos_dev"), ("perfil de los primeros 30 min", "pos_30")):
        casos = {k: [] for k in ("Original (C pasa, sigue la EMA)", "Al revés cuando C falla (sin más filtros)",
                                 "Al revés + sin BOS en contra", "Al revés + VWAP a favor", "Al revés + sin BOS + VWAP",
                                 "Original + al revés (sin BOS + VWAP en ambos)", "Solo por forma: P vende, b compra (ignora la EMA)")}
        for fecha, d in sorted(E.items()):
            if fecha not in R or fecha not in C or fecha not in V or not R[fecha]["fuera"]:
                continue
            r = R[fecha]; s = d["dir"]; e = d["entry"]; hm = d["hm"]
            f = forma(r[campo], s)
            noB = lambda x: not bos_contra(fecha, hm, x)
            vw = lambda x: (e - r["vwap"]) * x > 0
            dia = lambda x: C[fecha] if x == 1 else V[fecha]
            if f != "a favor":
                if noB(s) and vw(s):
                    casos["Original (C pasa, sigue la EMA)"].append((fecha, dia(s)))
                    casos["Original + al revés (sin BOS + VWAP en ambos)"].append((fecha, dia(s)))
            else:
                x = -s
                casos["Al revés cuando C falla (sin más filtros)"].append((fecha, dia(x)))
                if noB(x):
                    casos["Al revés + sin BOS en contra"].append((fecha, dia(x)))
                if vw(x):
                    casos["Al revés + VWAP a favor"].append((fecha, dia(x)))
                if noB(x) and vw(x):
                    casos["Al revés + sin BOS + VWAP"].append((fecha, dia(x)))
                    casos["Original + al revés (sin BOS + VWAP en ambos)"].append((fecha, dia(x)))
            fs = forma(r[campo], 1)
            if fs == "a favor":
                casos["Solo por forma: P vende, b compra (ignora la EMA)"].append((fecha, V[fecha]))
            elif fs == "en contra":
                casos["Solo por forma: P vende, b compra (ignora la EMA)"].append((fecha, C[fecha]))
        for bn, (sl, t1, t2, be) in BRACKETS.items():
            for caso, lst in casos.items():
                if len(lst) < 30:
                    continue
                u = np.array([rf.bracket(dd, sl, t1, t2, be=be) for _, dd in lst])
                y = np.array([f[:4] for f, _ in lst])
                filas.append(dict(perfil=perfil_nom, bracket=bn, caso=caso, **pv.met(u, y)))
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/modelo_b_reversa_pb.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
