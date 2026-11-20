#!/usr/bin/env python3
"""Modelo B (EMA 20 de 3 min + perfil A + C, bracket 35/30/120 con break-even) en cuatro sesiones del ES.

Sesiones (hora local de cada plaza, con su horario de verano):
  Sídney  10:00–16:00 Australia/Sydney      Tokio  9:00–15:00 Asia/Tokyo
  Londres  8:00–16:30 Europe/London         Nueva York  9:30–16:00 America/New_York
Misma regla en cada una, adaptada a su horario:
  entrada a mercado N minutos después de la apertura de la sesión (42 = como las 10:12 en NY; también 102);
  dirección: precio contra la EMA 20 de velas de 3 min (serie continua de ES);
  A: el precio está fuera del área de valor (70 %, perfil por tiempo, niveles de 1 pt) de la misma sesión del día anterior;
  C: el perfil de hoy (apertura de la sesión hasta la entrada) no tiene forma P al comprar ni b al vender;
  bracket en ticks de ES: SL 35, TP1 30 (mitad, luego BE), TP2 120; lo abierto se cierra al final de la sesión.
  Variante "escalado": SL/TP multiplicados por (rango mediano de la sesión ÷ rango mediano de NY), para que el
  bracket tenga el mismo tamaño relativo en sesiones más tranquilas.
2 ES, 34 USD de costo por operación. Velas reales de ES de 1 min, ene 2024 – 4 nov 2026.

    python3 backtest/modelo_b/sesiones.py <carpeta de salida para el dashboard>
Salidas: backtest/resultados/modelo_b_sesiones.csv y, en la carpeta, sesiones_resumen.json y sesiones_ops.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import rejilla_filtro as rf  # noqa: E402
from engine import ema3, TICK  # noqa: E402
from perfil import niveles  # noqa: E402
from estructura import cargar  # noqa: E402

SESIONES = {"Sídney": ("Australia/Sydney", "10:00", "16:00"), "Tokio": ("Asia/Tokyo", "09:00", "15:00"),
            "Londres": ("Europe/London", "08:00", "16:30"), "Nueva York": ("America/New_York", "09:30", "16:00")}
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "backtest/resultados/dashboard_sesiones"); OUT.mkdir(parents=True, exist_ok=True)


def sesiones_dia(df, tz, ini, fin):
    """{fecha local: velas de la sesión}"""
    loc = df.index.tz_convert(tz)
    m = loc.hour * 60 + loc.minute
    a = int(ini[:2]) * 60 + int(ini[3:]); b = int(fin[:2]) * 60 + int(fin[3:])
    x = df[(m >= a) & (m < b)].copy()
    x["d"] = loc[(m >= a) & (m < b)].date
    esperado = b - a
    return {d: g for d, g in x.groupby("d") if len(g) >= 0.8 * esperado and pd.Timestamp(d).dayofweek < 5}


def dias_sesion(df, ema, ses, offset):
    fechas = sorted(ses)
    out = []
    for i in range(1, len(fechas)):
        d, prev = fechas[i], fechas[i - 1]
        g, y = ses[d], ses[prev]
        if (pd.Timestamp(d) - pd.Timestamp(prev)).days > 4:
            continue
        if len(g) <= offset + 5:
            continue
        s0 = g.index[offset]
        dev = g.iloc[:offset]
        ent = g.o.values[offset]
        e = ema.asof(s0)
        if np.isnan(e):
            continue
        s = 1 if ent > e else -1
        yv = niveles(y.l.values, y.h.values)
        loc = "dentro" if yv["val"] <= ent <= yv["vah"] else "fuera"
        hv = niveles(dev.l.values, dev.h.values)
        pos = hv["pos"] if s == 1 else 1 - hv["pos"]
        rest = g.iloc[offset:]
        H, L, O, C = rest.h.values, rest.l.values, rest.o.values, rest.c.values
        up = ((H - ent) if s == 1 else (ent - L)) / TICK
        dn = ((L - ent) if s == 1 else (ent - H)) / TICK
        op = (O - ent) * s / TICK
        out.append(dict(date=str(d), dir=s, up=up, dn=dn, op=op, cl=(C[-1] - ent) * s / TICK,
                        pasa=(loc == "fuera") and pos <= 0.62, rango=float(g.h.max() - g.l.min())))
    return out


def met(u, y):
    pf = lambda v: float(v[v > 0].sum() / -v[v <= 0].sum()) if (v <= 0).any() and len(v) else None
    eq = np.cumsum(u)
    neg = pd.Series((u <= 0).astype(int))
    r = dict(ops=int(len(u)), ganadoras=round(float((u > 0).mean() * 100), 1) if len(u) else None, pf=round(pf(u), 2) if len(u) else None,
             neto=int(round(u.sum())), por_op=int(round(u.mean())) if len(u) else None,
             caida=int(round((eq - np.maximum.accumulate(np.maximum(eq, 0))).min())) if len(u) else 0,
             peor_racha=int(neg.groupby((neg != neg.shift()).cumsum()).sum().max()) if len(u) else 0)
    for a in ("2024", "2025", "2026"):
        v = u[y == a]
        r[f"pf_{a}"] = round(pf(v), 2) if len(v) and pf(v) is not None else None
        r[f"neto_{a}"] = int(round(v.sum()))
    return r


def main():
    df = cargar()
    ema = ema3(df, 20, 3)
    base = {}
    filas, ops = [], []
    for nom, (tz, ini, fin) in SESIONES.items():
        ses = sesiones_dia(df, tz, ini, fin)
        base[nom] = (ses, float(np.median([g.h.max() - g.l.min() for g in ses.values()])))
    rango_ny = base["Nueva York"][1]
    for nom, (ses, rango) in base.items():
        esc = rango / rango_ny
        for offset in (42, 102):
            D = dias_sesion(df, ema, ses, offset)
            y = np.array([d["date"][:4] for d in D])
            for br_nom, k in (("35/30/120 (igual que NY)", 1.0), ("escalado a la volatilidad de la sesión", esc)):
                br = (max(4, round(35 * k)), max(2, round(30 * k)), max(6, round(120 * k)))
                U = np.array([rf.bracket(d, *br) for d in D])
                P = np.array([d["pasa"] for d in D])
                for filtro, mk in (("Solo EMA", np.ones(len(D), bool)), ("EMA + A + C (el modelo)", P)):
                    r = met(U[mk], y[mk])
                    clave = f"{nom}|{offset}|{br_nom}|{filtro}"
                    filas.append(dict(clave=clave, sesion=nom, minutos=offset, bracket=br_nom, sl_tp=f"{br[0]}/{br[1]}/{br[2]}",
                                      filtro=filtro, rango_mediano_pts=round(rango, 1), **r))
                    if offset == 42 and filtro == "EMA + A + C (el modelo)" and k == 1.0:
                        s = 0.0
                        for d, u in zip([d for d, m_ in zip(D, mk) if m_], U[mk]):
                            s += u
                            ops.append(dict(sesion=nom, fecha=d["date"], usd=round(float(u), 2), saldo=round(s, 2)))
    T = pd.DataFrame(filas)
    T.to_csv("backtest/resultados/modelo_b_sesiones.csv", index=False)
    code = Path(__file__).read_text()
    meta = [{"label": "sesiones.py", "value": code, "type": "code", "lang": "python"},
            {"label": "Entrada", "value": "Velas de 1 min de ES (NinjaTrader), ene 2024 – 4 nov 2026, contratos encadenados"}]
    (OUT / "sesiones_resumen.json").write_text(json.dumps({"rows": [{k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()} for r in filas], "meta": meta}, ensure_ascii=False))
    (OUT / "sesiones_ops.json").write_text(json.dumps({"rows": ops, "meta": meta}, ensure_ascii=False))
    pd.set_option("display.width", 260); pd.set_option("display.max_rows", 100)
    print(T.drop(columns=["clave"]).to_string(index=False))


if __name__ == "__main__":
    main()
