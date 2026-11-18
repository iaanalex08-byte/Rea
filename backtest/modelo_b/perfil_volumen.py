#!/usr/bin/env python3
"""Modelo B a las 10:12 NY con filtros de perfil de VOLUMEN real de ES (no TPO) y conceptos básicos de subasta.

Todo se mide con información anterior a la entrada. Perfil de volumen: cada vela de 1 min reparte su volumen
en partes iguales entre los niveles de 1 punto que tocó (sesión regular 9:30–16:00 NY). Área de valor 70 %.

Filtros probados (a favor = en la dirección de la operación):
  A_vol / C_vol      los filtros A y C del modelo, pero con perfil de volumen en lugar de TPO
  POC ayer           entrada del lado a favor del POC de ayer
  POC hoy            entrada del lado a favor del POC en desarrollo (9:30 NY hasta la entrada)
  VWAP               entrada del lado a favor del VWAP de la sesión
  Apertura           la apertura de las 9:30 NY quedó fuera del valor de ayer a favor
  Rango 30 min       la entrada ya está fuera del rango de 9:30–10:00 NY a favor
  Espacio            hay al menos 40 ticks (10 pts) hasta el siguiente nivel de ayer (POC, VAH, VAL o nodo alto)
  Volumen relativo   el volumen desde las 9:30 NY supera el promedio de los 20 días anteriores
  Noche a favor      la sesión nocturna (18:00–9:30 NY) cerró a favor
  EMA cerca          el precio está a menos de 6 pts de la EMA (no estirado)
Brackets: 30/40/160 sin BE (el mejorado), 35/30/120 con BE (el original) y 40/20/120 con BE (de winrate alto).

    python3 backtest/modelo_b/perfil_volumen.py
Salida: backtest/resultados/modelo_b_volumen.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import rejilla_filtro as rf  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402
from sp500_0912 import bars  # noqa: E402

BRACKETS = {"30/40/160 sin BE": (30, 40, 160, False), "35/30/120 con BE": (35, 30, 120, True), "40/20/120 con BE": (40, 20, 120, True)}


def perfil(lo, hi, vol, binw=1.0):
    b0 = np.floor(lo.min() / binw)
    nb = int(np.floor(hi.max() / binw) - b0) + 1
    cnt = np.zeros(nb)
    a = (np.floor(lo / binw) - b0).astype(int)
    z = (np.floor(hi / binw) - b0).astype(int)
    for i, j, v in zip(a, z, vol):
        cnt[i:j + 1] += v / (j - i + 1)
    px = (b0 + np.arange(nb)) * binw
    p = int(cnt.argmax()); up = dn = p; acc, tot = cnt[p], cnt.sum()
    while acc < 0.7 * tot:
        A = cnt[up + 1] if up + 1 < nb else -1
        B = cnt[dn - 1] if dn > 0 else -1
        if A >= B:
            up += 1; acc += A
        else:
            dn -= 1; acc += B
    s = np.convolve(cnt, np.ones(3) / 3, mode="same")
    hvn = [px[i] + binw / 2 for i in range(1, nb - 1) if s[i] >= s[i - 1] and s[i] >= s[i + 1] and s[i] >= 0.6 * s.max()]
    lo_r, hi_r = px[0], px[-1] + binw
    poc = px[p] + binw / 2
    return dict(poc=poc, vah=px[up] + binw, val=px[dn], pos=(poc - lo_r) / max(hi_r - lo_r, binw), hvn=hvn)


def rasgos_volumen(F):
    raw = bars(str(HERE.parent / "datos"))
    raw.index = raw.index.tz_convert("America/New_York")
    m = raw.index.hour * 60 + raw.index.minute
    rth = raw[(m >= 570) & (m < 960)].copy()
    rth["d"] = rth.index.date
    ses = {d: g for d, g in rth.groupby("d") if len(g) >= 200}
    fechas = sorted(ses)
    prof = {d: perfil(g.low.values, g.high.values, g.volume.values) for d, g in ses.items()}
    vol_hasta = {}
    out = {}
    for d in F:
        fecha = pd.Timestamp(d["date"]).date()
        t0 = pd.Timestamp(f"{d['date']} {d['hm'][0]:02d}:{d['hm'][1]:02d}", tz="America/Mexico_City").tz_convert("America/New_York")
        prev = [f for f in fechas if f < fecha]
        g = rth[rth.d == fecha]
        dev = g[g.index < t0]
        if len(prev) < 21 or len(dev) < 20:
            continue
        y = prof[prev[-1]]
        s, e = d["dir"], d["entry"]
        hoy = perfil(dev.low.values, dev.high.values, dev.volume.values)
        tp = (dev.high + dev.low + dev.close) / 3
        vwap = (tp * dev.volume).sum() / dev.volume.sum()
        o930 = g.open.values[0]
        or30 = g[g.index < g.index[0] + pd.Timedelta(minutes=30)]
        mins = len(dev)
        vol_hasta[fecha] = dev.volume.sum()
        prev_v = [ses[f].volume.values[:mins].sum() for f in prev[-20:]]
        noche = raw[(raw.index >= (pd.Timestamp(fecha, tz="America/New_York") - pd.Timedelta(hours=6))) & (raw.index < g.index[0])]
        lv = [y["poc"], y["vah"], y["val"]] + list(y["hvn"])
        ahead = [(v - e) * s for v in lv if (v - e) * s > 0.5]
        loc_v = "fuera" if (e > y["vah"] or e < y["val"]) else "dentro"
        pos = hoy["pos"] if s == 1 else 1 - hoy["pos"]
        out[d["date"]] = {
            "A_vol": loc_v == "fuera",
            "C_vol": pos <= 0.62,
            "POC ayer a favor": (e - y["poc"]) * s > 0,
            "POC hoy a favor": (e - hoy["poc"]) * s > 0,
            "VWAP a favor": (e - vwap) * s > 0,
            "Apertura fuera del valor a favor": (o930 > y["vah"]) if s == 1 else (o930 < y["val"]),
            "Fuera del rango de 30 min a favor": (e > or30.high.max()) if s == 1 else (e < or30.low.min()),
            "Espacio de 10 pts al siguiente nivel": (min(ahead) if ahead else 99) >= 10,
            "Volumen relativo alto": vol_hasta[fecha] > np.mean(prev_v),
            "Noche a favor": len(noche) > 0 and (noche.close.values[-1] - noche.open.values[0]) * s > 0,
            "EMA cerca (< 6 pts)": abs(e - d["ema"]) < 6,
        }
    return out


def pf(u):
    n = -u[u <= 0].sum()
    return u[u > 0].sum() / n if n > 0 else np.inf


def met(u, y):
    eq = np.cumsum(u)
    r = dict(ops=len(u), ganadoras=round((u > 0).mean() * 100, 1), pf=round(pf(u), 2), neto=round(u.sum()), por_op=round(u.mean()),
             caida=round((eq - np.maximum.accumulate(np.maximum(eq, 0))).min()))
    for a in ("2024", "2025", "2026"):
        v = u[y == a]
        r[f"pf_{a}"] = round(pf(v), 2) if len(v) else None
        r[f"gan_{a}"] = round((v > 0).mean() * 100, 1) if len(v) else None
    return r


def main():
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    y = np.array([d["date"][:4] for d in F])
    feat = pd.DataFrame([V[d["date"]] for d in F])
    A = np.array([d["loc"] != "dentro del valor" for d in F]); C = np.array([d["forma"] != "a favor (P/b)" for d in F])
    noB = np.array([not bc[d["date"]] for d in F])
    bases = {"EMA sola": np.ones(len(F), bool), "Mejorado (A+C por tiempo, sin BOS en contra)": A & C & noB,
             "A+C por volumen, sin BOS en contra": feat["A_vol"].values & feat["C_vol"].values & noB}
    filas = []
    for bn, (sl, t1, t2, be) in BRACKETS.items():
        U = np.array([rf.bracket(d, sl, t1, t2, be=be) for d in F])
        for base, bm in bases.items():
            filas.append(dict(bracket=bn, base=base, filtro="(ninguno)", **met(U[bm], y[bm])))
            for c in feat.columns:
                if c in ("A_vol", "C_vol"):
                    continue
                for neg, mk in (("", feat[c].values.astype(bool)), ("NO ", ~feat[c].values.astype(bool))):
                    m = bm & mk
                    if m.sum() >= 60:
                        filas.append(dict(bracket=bn, base=base, filtro=neg + c, **met(U[m], y[m])))
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/modelo_b_volumen.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
