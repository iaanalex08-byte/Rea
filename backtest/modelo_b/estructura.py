#!/usr/bin/env python3
"""Modelo B (9:12 CDMX, EMA 20 de 3 min, filtros de perfil A + C, bracket 35/30/120) sobre velas REALES de ES de 1 min
(backtest/datos, 2024 – 4 nov 2026), y la prueba de si mejora con un BOS, CHOCH o FVG previo a la entrada.

El código del modelo (engine.py, perfil.py, rejilla_filtro.py, mejoras.py) es el de la rama ccr-f8177091-hrh8wn,
sin cambios; aquí solo se le dan velas de ES en lugar de SPXUSD.

Estructura (solo velas cerradas ANTES de la entrada; nada del futuro):
  Swing alto / bajo: fractal de K velas a cada lado (K = 2), confirmado K velas después.
  Ruptura: una vela CIERRA arriba del último swing alto no roto (o abajo del último swing bajo).
     CHOCH = la ruptura va contra la estructura anterior (la última ruptura fue en sentido contrario).
     BOS   = la ruptura sigue la estructura anterior.
  FVG: hueco de 3 velas (alcista: mínimo de la vela 3 > máximo de la vela 1; bajista al revés), de al menos
     --fvg-min puntos, que el precio no haya cerrado por completo antes de la entrada.
  "Previo": el evento ocurre en la ventana [entrada - V min, entrada). A favor = en la dirección de la operación.
Temporalidades de estructura: 3 y 5 min. Ventanas: 30 y 60 min, y desde la apertura de NY (9:30 NY).

    python3 backtest/modelo_b/estructura.py cdmx   # siempre 9:12 CDMX (la regla escrita)
    python3 backtest/modelo_b/estructura.py ny     # siempre 10:12 NY (lo que midió el backtest con SPXUSD)
Salidas: backtest/resultados/modelo_b_dias_<versión>.csv y backtest/resultados/modelo_b_estructura_<versión>.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import rejilla_filtro as rf  # noqa: E402
from mejoras import con_filtros  # noqa: E402
from sp500_0912 import bars  # noqa: E402

BR = (35, 30, 120)
K = 2
FVG_MIN = 1.0


def cargar():
    df = bars(str(HERE.parent / "datos"))
    df = df.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"})[["o", "h", "l", "c"]]
    df.index = df.index.tz_convert("UTC")
    return df


def velas(df1, tf):
    r = df1.resample(f"{tf}min", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    r["cierre"] = r.index + pd.Timedelta(minutes=tf)  # momento en que la vela ya se conoce
    return r


def eventos(b):
    """Lista de eventos de estructura en velas de tf: (momento conocido, tipo, dirección)."""
    H, L, C, T = b.h.values, b.l.values, b.c.values, b.cierre.values
    n = len(b)
    ev = []
    sh = sl = None          # último swing alto / bajo no roto (precio)
    trend = 0
    pend = []               # swings por confirmar
    for i in range(n):
        # confirmar el fractal de la vela i-K con las K velas posteriores ya cerradas
        j = i - K
        if j >= K:
            if H[j] == H[j - K:j + K + 1].max() and (H[j] > H[j - K:j]).all():
                sh = H[j]
            if L[j] == L[j - K:j + K + 1].min() and (L[j] < L[j - K:j]).all():
                sl = L[j]
        if sh is not None and C[i] > sh:
            ev.append((T[i], "CHOCH" if trend == -1 else "BOS", 1)); trend = 1; sh = None
        elif sl is not None and C[i] < sl:
            ev.append((T[i], "CHOCH" if trend == 1 else "BOS", -1)); trend = -1; sl = None
        if i >= 2:
            if L[i] - H[i - 2] >= FVG_MIN:
                ev.append((T[i], "FVG", 1, H[i - 2], L[i]))
            elif L[i - 2] - H[i] >= FVG_MIN:
                ev.append((T[i], "FVG", -1, H[i], L[i - 2]))
    return ev


def rasgos_estructura(df1, D, tf):
    b = velas(df1, tf)
    ev = eventos(b)
    tiempos = np.array([e[0] for e in ev])
    c1 = df1.c
    out = {}
    for d in D:
        h, mi = d.get("hm", (9, 12))
        t0 = pd.Timestamp(f"{d['date']} {h:02d}:{mi:02d}", tz="America/Mexico_City").tz_convert("UTC")
        ny0 = t0.tz_convert("America/New_York").normalize() + pd.Timedelta(hours=9, minutes=30)
        s = d["dir"]
        f = {}
        for vent, desde in (("30", t0 - pd.Timedelta(minutes=30)), ("60", t0 - pd.Timedelta(minutes=60)), ("NY", ny0.tz_convert("UTC"))):
            lo = np.datetime64(desde.tz_localize(None) if desde.tzinfo is None else desde.tz_convert("UTC").tz_localize(None))
            hi = np.datetime64(t0.tz_convert("UTC").tz_localize(None))
            m = (tiempos > lo) & (tiempos <= hi)
            sel = [ev[k] for k in np.flatnonzero(m)]
            for tipo in ("BOS", "CHOCH"):
                f[f"{tipo}_{vent}_favor"] = any(e[1] == tipo and e[2] == s for e in sel)
                f[f"{tipo}_{vent}_contra"] = any(e[1] == tipo and e[2] == -s for e in sel)
            # FVG a favor sin cerrar al momento de entrar
            vivos_f, vivos_c = False, False
            for e in sel:
                if e[1] != "FVG":
                    continue
                tt = pd.Timestamp(e[0]).tz_localize("UTC")
                tramo = c1[(c1.index >= tt) & (c1.index < t0)]
                if e[2] == 1:
                    vivo = tramo.empty or tramo.min() > e[3]
                else:
                    vivo = tramo.empty or tramo.max() < e[4]
                if vivo and e[2] == s:
                    vivos_f = True
                if vivo and e[2] == -s:
                    vivos_c = True
            f[f"FVG_{vent}_favor"] = vivos_f
            f[f"FVG_{vent}_contra"] = vivos_c
        out[d["date"]] = f
    return out


def metricas(x):
    u = x.usd.values
    g, l = u[u > 0].sum(), -u[u <= 0].sum()
    eq = np.cumsum(u)
    dd = float((eq - np.maximum.accumulate(np.maximum(eq, 0))).min()) if len(u) else 0.0
    neg = (u <= 0).astype(int)
    racha = int(pd.Series(neg).groupby((pd.Series(neg) != pd.Series(neg).shift()).cumsum()).sum().max()) if len(u) else 0
    pf = lambda v: (v[v > 0].sum() / -v[v <= 0].sum()) if (v <= 0).any() else np.inf
    yy = x.date.str[:4].values
    r = dict(ops=len(u), ganadoras=round((u > 0).mean() * 100, 1) if len(u) else None, pf=round(pf(u), 2) if len(u) else None,
             neto=round(u.sum()), por_op=round(u.mean(), 1) if len(u) else None, caida=round(dd), peor_racha=racha)
    for a in ("2024", "2025", "2026"):
        v = u[yy == a]
        r[f"pf_{a}"] = round(pf(v), 2) if len(v) else None
        r[f"n_{a}"] = int(len(v))
    return r


def verano(fecha):
    return pd.Timestamp(fecha + " 12:00", tz="America/New_York").utcoffset() == pd.Timedelta(hours=-4)


def dias_version(df, version):
    """'cdmx' = siempre 9:12 CDMX (la regla escrita). 'ny' = siempre 10:12 NY (9:12 CDMX en invierno, 8:12 en verano),
    que es lo que de verdad midió el backtest original con SPXUSD."""
    F9 = [dict(d, hm=(9, 12)) for d in con_filtros(df, rf.dias(df, hm=(9, 12)), hm=(9, 12))]
    if version == "cdmx":
        return F9
    F8 = {d["date"]: dict(d, hm=(8, 12)) for d in con_filtros(df, rf.dias(df, hm=(8, 12)), hm=(8, 12))}
    out = []
    for d in F9:
        if verano(d["date"]):
            if d["date"] in F8:
                out.append(F8[d["date"]])
        else:
            out.append(d)
    return out


def main():
    df = cargar()
    version = sys.argv[1] if len(sys.argv) > 1 else "cdmx"
    F = dias_version(df, version)
    rows = []
    for d in F:
        rows.append(dict(date=d["date"], dir=d["dir"], entry=d["entry"], usd=float(rf.bracket(d, *BR)),
                         salida=rf.salida(d, *BR), usd_45=float(rf.bracket(d, 45, 30, 60)), loc=d["loc"],
                         forma=d["forma"] if isinstance(d["forma"], str) else "sin datos", pasa=bool(d["pasa"])))
    T = pd.DataFrame(rows)
    for tf in (3, 5):
        R = rasgos_estructura(df, F, tf)
        G = pd.DataFrame.from_dict(R, orient="index").add_prefix(f"{tf}m_")
        T = T.merge(G, left_on="date", right_index=True, how="left")
    T.to_csv(f"backtest/resultados/modelo_b_dias_{version}.csv", index=False)

    res = []
    for base_nom, B in (("Solo EMA", T), ("EMA + A + C (el modelo)", T[T.pasa])):
        res.append(dict(base=base_nom, filtro="— sin filtro de estructura —", **metricas(B)))
        cols = [c for c in T.columns if c.startswith(("3m_", "5m_"))]
        for c in cols:
            m = B[c].astype(bool)
            if m.sum() >= 25:
                res.append(dict(base=base_nom, filtro=c, **metricas(B[m])))
            if (~m).sum() >= 25 and c.endswith("_favor"):
                res.append(dict(base=base_nom, filtro="SIN " + c, **metricas(B[~m])))
        for tf in (3, 5):
            for v in ("30", "60", "NY"):
                m = B[f"{tf}m_BOS_{v}_favor"] | B[f"{tf}m_CHOCH_{v}_favor"]
                res.append(dict(base=base_nom, filtro=f"{tf}m_BOS o CHOCH_{v}_favor", **metricas(B[m])))
                m2 = m & B[f"{tf}m_FVG_{v}_favor"]
                if m2.sum() >= 25:
                    res.append(dict(base=base_nom, filtro=f"{tf}m_(BOS o CHOCH) + FVG_{v}_favor", **metricas(B[m2])))
                m3 = ~(B[f"{tf}m_BOS_{v}_favor"] | B[f"{tf}m_CHOCH_{v}_favor"] | B[f"{tf}m_FVG_{v}_favor"])
                if m3.sum() >= 25:
                    res.append(dict(base=base_nom, filtro=f"{tf}m_ninguno_{v}", **metricas(B[m3])))
    S = pd.DataFrame(res)
    S.to_csv(f"backtest/resultados/modelo_b_estructura_{version}.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print(S.to_string(index=False))


if __name__ == "__main__":
    main()
