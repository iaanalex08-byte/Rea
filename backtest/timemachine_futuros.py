#!/usr/bin/env python3
"""Time Machine para futuros (ES/MES y NQ/MNQ), compras y ventas.

Antes de entrar, simula el resto del día 10,000 veces y da la probabilidad de cada desenlace:
SL antes de TP1, TP1 y luego BE, TP1 y TP2, o cierre sin resolver (15:00 CDMX).

Regla (la estrategia de tendencia del SP500):
  dirección = cierre de las 8:59 vs apertura de las 00:00 CDMX (sube = compra, baja = venta),
  solo si el movimiento es >= --tendencia puntos; entrada a mercado en la apertura de --hora (+1 tick de deslizamiento).
  SL --sl ticks. En TP1 (--tp1 ticks) se cierra --parcial de la posición y el SL pasa a BE. El resto sale en TP2 (--tp2 ticks).
  Vela de 1 min que toca SL y TP a la vez: cuenta primero el SL (conservador), igual que los backtests.

Cómo simula (sin ver el futuro):
  1. Banco de días: sólo días ANTERIORES a la fecha, con la misma condición (misma dirección de la tendencia
     00:00-9:00 y movimiento >= --tendencia). Así la simulación usa cómo se comportó el mercado en días parecidos.
  2. Cada réplica arma el resto del día (desde la hora de entrada hasta las 15:00) con bloques de --bloque minutos (default 60)
     tomados al azar de esos días (retornos de cada vela de 1 min, escalados al precio de hoy). Los bloques
     conservan la inercia de corto plazo que una vela suelta pierde.
  3. Con --ajustar-vol, los retornos se escalan por el rango de la noche de hoy contra el del día de origen.
  4. Historia real: la misma regla sobre cada día del banco (lo que de verdad pasó).

Datos: CSV de 1 min de NinjaTrader en backtest/datos (ES) y backtest/datos_NQ (NQ).
Con --vivo, el día de hoy (tendencia y precio de entrada) se lee de Yahoo Finance (ES=F / NQ=F, 1 min, gratis,
puede tener retraso). Si aún no son las 9:00, el resultado es provisional con la tendencia hasta ese minuto.

    python3 backtest/timemachine_futuros.py --vivo                          # ES, hoy, 9:00, SL 60 / TP1 60 / TP2 120
    python3 backtest/timemachine_futuros.py --fecha 2026-11-04               # un día de los CSV (y lo que pasó de verdad)
    python3 backtest/timemachine_futuros.py --vivo --hora 9:12 --sl 45 --tp1 30 --tp2 60
    python3 backtest/timemachine_futuros.py --inst NQ --vivo --tendencia 70 --sl 200 --tp1 200 --tp2 400
    python3 backtest/timemachine_futuros.py --calibrar 2026                  # ¿acierta? compara pronóstico vs realidad
"""
import argparse
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from sp500_0912 import bars  # noqa: E402

INST = {  # carpeta, símbolo Yahoo, tick, $ por punto del micro, comisión ida y vuelta por micro
    "ES": ("backtest/datos", "ES=F", 0.25, 5.0, 1.24, "MES"),
    "NQ": ("backtest/datos_NQ", "NQ=F", 0.25, 2.0, 1.24, "MNQ"),
}
CDMX = timezone(timedelta(hours=-6))
CIERRE = 900  # 15:00 CDMX


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def fmt_min(m):
    return f"{m // 60}:{m % 60:02d}"


# ------------------------------------------------------------------ datos
def dias_csv(folder):
    """{fecha: DataFrame de 1 min indexado por minuto del día (0..1439), de 00:00 a 15:00 CDMX}"""
    df = bars(folder)
    out = {}
    for d, g in df.groupby(df.index.date):
        if g.index[0].dayofweek >= 5:
            continue
        tm = g.index.hour * 60 + g.index.minute
        g = g.set_axis(tm)
        g = g[g.index <= CIERRE]
        if len(g) < 300 or g.index[0] > 5:
            continue
        out[d] = g[["open", "high", "low", "close"]]
    return out


def dia_yahoo(sym, fecha=None):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=5d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    t = pd.to_datetime(j["timestamp"], unit="s", utc=True).tz_convert(CDMX)
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close")}, index=t).dropna()
    df = df[df.index.dayofweek < 5]
    if fecha is None:
        fecha = df.index[-1].date()
    g = df[df.index.date == fecha]
    if g.empty:
        raise SystemExit(f"Yahoo no tiene velas de {sym} para {fecha}.")
    g = g.set_axis(g.index.hour * 60 + g.index.minute)
    g = g[~g.index.duplicated(keep="last")]
    return fecha, g


def completar(g, ini, fin):
    """Velas de ini..fin-1; los minutos sin operación se rellenan con el cierre anterior."""
    idx = np.arange(ini, fin)
    g = g.reindex(idx)
    c = g.close.ffill()
    for k in ("open", "high", "low"):
        g[k] = g[k].fillna(c)
    g["close"] = c
    return g


# ------------------------------------------------------------------ regla
def condicion(g, hora, tend_min):
    """(dirección, movimiento) de 00:00 a la vela anterior a la hora de tendencia (8:59), o None."""
    pre = g[g.index < min(hora, 540)]
    if pre.empty or g.index[0] > 5:
        return None
    mv = pre.close.iloc[-1] - g.open.iloc[0]
    if abs(mv) < max(tend_min, 0.01):
        return None
    return (1 if mv > 0 else -1), mv


def evaluar(Hs, Ls, Cs, sl, tp1, tp2, parcial, be):
    """Hs/Ls/Cs: (réplicas, minutos) en puntos a favor de la operación respecto a la entrada.
    Devuelve código de resultado (0 SL, 1 TP1+BE, 2 TP1+TP2, 3 cierre sin TP1, 4 TP1 + cierre) y R bruto."""
    n, T = Hs.shape
    INF = T + 1
    ar = np.arange(T)

    def primero(mask):
        return np.where(mask.any(1), mask.argmax(1), INF)

    i_sl = primero(Ls <= -sl)
    i_t1 = primero(Hs >= tp1)
    sl_primero = i_sl <= i_t1  # misma vela: primero el SL
    res = np.full(n, 3)
    R = Cs[:, -1] / sl
    res[sl_primero & (i_sl < INF)] = 0
    R[res == 0] = -1.0
    con_t1 = (~sl_primero) & (i_t1 < INF)
    if con_t1.any():
        k = i_t1[con_t1][:, None]
        H2, L2 = Hs[con_t1], Ls[con_t1]
        stop2 = 0.0 if be else -sl
        i_t2 = primero((H2 >= tp2) & (ar >= k))
        i_st = primero((L2 <= stop2) & (ar > k if be else ar >= k))
        r1 = parcial * tp1 / sl
        rr = np.where(i_st <= i_t2, r1 + (1 - parcial) * stop2 / sl,
                      r1 + (1 - parcial) * tp2 / sl)
        cerr = (i_st == INF) & (i_t2 == INF)
        rr = np.where(cerr, r1 + (1 - parcial) * Cs[con_t1, -1] / sl, rr)
        code = np.where(cerr, 4, np.where(i_st <= i_t2, 1, 2))
        res[con_t1] = code
        R[con_t1] = rr
    return res, R


# ------------------------------------------------------------------ simulación
def banco(dias, fecha, s, hora, tend_min, desde=None):
    """Días anteriores a la fecha con la misma condición; devuelve (fechas, dc, dh, dl, rango_noche)."""
    fs, DC, DH, DL, RN = [], [], [], [], []
    for d, g in dias.items():
        if d >= fecha or (desde and d < desde):
            continue
        c = condicion(g, hora, tend_min)
        if c is None or c[0] != s:
            continue
        seg = completar(g, hora, CIERRE)
        if seg.open.isna().iloc[0]:
            continue
        o, h, l, cl = (seg[k].to_numpy() for k in ("open", "high", "low", "close"))
        prev = np.concatenate([[o[0]], cl[:-1]])
        DC.append(np.log(cl / prev)); DH.append(np.log(h / prev)); DL.append(np.log(l / prev))
        pre = g[g.index < 540]
        RN.append(pre.high.max() - pre.low.min())
        fs.append(d)
    return fs, np.array(DC), np.array(DH), np.array(DL), np.array(RN)


def simular(B, ent, s, rango_hoy, n, bloque, seed, ajustar_vol):
    fs, DC, DH, DL, RN = B
    rng = np.random.default_rng(seed)
    T = DC.shape[1]
    nb = -(-T // bloque)
    pick = rng.integers(0, len(fs), size=(n, nb))
    rows = np.repeat(pick, bloque, axis=1)[:, :T]
    cols = np.broadcast_to(np.arange(T), (n, T))
    dc, dh, dl = DC[rows, cols], DH[rows, cols], DL[rows, cols]
    if ajustar_vol:
        f = np.clip(rango_hoy / RN[rows], 0.5, 2.0)
        dc, dh, dl = dc * f, dh * f, dl * f
    lc = np.cumsum(dc, axis=1)
    lprev = lc - dc
    if s == 1:
        Hs = ent * (np.exp(lprev + dh) - 1); Ls = ent * (np.exp(lprev + dl) - 1)
    else:
        Hs = -ent * (np.exp(lprev + dl) - 1); Ls = -ent * (np.exp(lprev + dh) - 1)
    Cs = s * ent * (np.exp(lc) - 1)
    return Hs, Ls, Cs


def historia(dias, fs, s, hora, a):
    """La regla real sobre cada día del banco."""
    out = []
    for d in fs:
        seg = completar(dias[d], hora, CIERRE)
        e = seg.open.iloc[0] + s * a.tick
        H, L, C = (seg[k].to_numpy() - e for k in ("high", "low", "close"))
        Hs, Ls = (H, L) if s == 1 else (-L, -H)
        res, R = evaluar(Hs[None], Ls[None], (s * C)[None], a.sl_p, a.tp1_p, a.tp2_p, a.parcial, not a.sin_be)
        out.append((d, int(res[0]), float(R[0])))
    return pd.DataFrame(out, columns=["fecha", "res", "R"])


NOMBRES = {0: "SL antes de TP1", 1: "TP1 y luego BE", 2: "TP1 y TP2", 3: "Cierre 15:00 sin tocar TP1 ni SL", 4: "TP1 y cierre 15:00"}


def resumen(res, R, com_r):
    R = R - com_r
    p = {NOMBRES[k]: float((res == k).mean() * 100) for k in NOMBRES}
    return p, R


def veredicto(rm):
    if rm >= 0.15:
        return "Fuerte a favor: la expectativa es claramente positiva."
    if rm >= 0.05:
        return "Inclinada a favor: expectativa positiva, pero modesta."
    if rm > -0.05:
        return "Casi un volado: la expectativa está cerca de cero."
    if rm > -0.15:
        return "Inclinada en contra: expectativa negativa."
    return "Fuerte en contra: mejor no tomarla con estos niveles."


# ------------------------------------------------------------------ main
def parse(argv=None):
    p = argparse.ArgumentParser(description="Time Machine para futuros ES / NQ (compras y ventas)")
    p.add_argument("--inst", choices=INST, default="ES")
    p.add_argument("--vivo", action="store_true", help="hoy (o el último día con datos) desde Yahoo Finance")
    p.add_argument("--fecha", help="YYYY-MM-DD: un día de los CSV (también muestra lo que pasó de verdad)")
    p.add_argument("--hora", default="9:00", help="hora de entrada CDMX (default 9:00)")
    p.add_argument("--tendencia", type=float, default=None, help="movimiento mínimo 00:00-8:59 en puntos (ES 20, NQ 70)")
    p.add_argument("--sl", type=int, default=60, help="SL en ticks")
    p.add_argument("--tp1", type=int, default=60, help="TP1 en ticks")
    p.add_argument("--tp2", type=int, default=120, help="TP2 en ticks")
    p.add_argument("--parcial", type=float, default=0.5, help="fracción que se cierra en TP1 (default 0.5)")
    p.add_argument("--sin-be", action="store_true", help="no mover el SL a BE después de TP1")
    p.add_argument("--contratos", type=int, default=2, help="micros (MES / MNQ)")
    p.add_argument("--replicas", type=int, default=10000)
    p.add_argument("--bloque", type=int, default=60, help="minutos por bloque")
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--ajustar-vol", action="store_true", help="escalar por el rango de la noche de hoy")
    p.add_argument("--entrada", type=float, help="precio de entrada manual (si no, la apertura de la vela de la hora)")
    p.add_argument("--direccion", choices=["compra", "venta"], help="forzar dirección (si no, la de la tendencia)")
    p.add_argument("--calibrar", type=int, metavar="AÑO", help="pronostica cada día del año y lo compara con lo que pasó")
    p.add_argument("--json", help="guardar el resultado en este archivo")
    a = p.parse_args(argv)
    folder, a.ysym, a.tick, a.pv, a.com, a.micro = INST[a.inst]
    a.folder = folder
    if a.tendencia is None:
        a.tendencia = 20.0 if a.inst == "ES" else 70.0
    a.hora_m = hm(a.hora)
    a.sl_p, a.tp1_p, a.tp2_p = a.sl * a.tick, a.tp1 * a.tick, a.tp2 * a.tick
    a.usd_r = a.sl_p * a.pv * a.contratos
    a.com_r = a.com * a.contratos / a.usd_r
    return a


def un_dia(a, dias, fecha, g, real=None, silencioso=False):
    hora = a.hora_m
    pre = g[g.index < 540]
    if pre.empty or g.index[0] > 5:
        raise SystemExit(f"{fecha}: no hay velas desde las 00:00 CDMX.")
    mv = pre.close.iloc[-1] - g.open.iloc[0]
    s = 1 if mv > 0 else -1
    if a.direccion:
        s = 1 if a.direccion == "compra" else -1
    provisional = pre.index[-1] < 539
    if hora in g.index:
        ent = g.open.loc[hora] + s * a.tick
    else:
        ent = g.close.iloc[-1] + s * a.tick
        provisional = True
    if a.entrada:
        ent = a.entrada
    rango = pre.high.max() - pre.low.min()
    out = {"instrumento": a.inst, "fecha": str(fecha), "hora": a.hora, "movimiento_noche": round(float(mv), 2),
           "direccion": "compra" if s == 1 else "venta", "entrada": round(float(ent), 2),
           "sl": round(ent - s * a.sl_p, 2), "tp1": round(ent + s * a.tp1_p, 2), "tp2": round(ent + s * a.tp2_p, 2),
           "provisional": provisional, "seed": a.seed}
    filtro_ok = abs(mv) >= a.tendencia
    out["filtro_tendencia"] = bool(filtro_ok)
    B = banco(dias, fecha, s, hora, a.tendencia if filtro_ok else 0.0)
    if len(B[0]) < 30:
        raise SystemExit(f"Muy pocos días parecidos en el banco ({len(B[0])}).")
    Hs, Ls, Cs = simular(B, ent, s, rango, a.replicas, a.bloque, a.seed, a.ajustar_vol)
    res, R = evaluar(Hs, Ls, Cs, a.sl_p, a.tp1_p, a.tp2_p, a.parcial, not a.sin_be)
    p, R = resumen(res, R, a.com_r)
    hist = historia(dias, B[0], s, hora, a)
    hist["R"] -= a.com_r
    out.update({"dias_banco": len(B[0]), "probabilidades": p, "R_medio": float(R.mean()),
                "usd_medio": float(R.mean() * a.usd_r), "R_p5_p50_p95": [float(np.percentile(R, q)) for q in (5, 50, 95)],
                "historia": {"ops": len(hist), "R_medio": float(hist.R.mean()),
                             "pct": {NOMBRES[k]: float((hist.res == k).mean() * 100) for k in NOMBRES},
                             "ult60_R_medio": float(hist.R.tail(60).mean())},
                "veredicto": veredicto(R.mean())})
    if real is not None:
        out["real"] = real
    if silencioso:
        return out
    imprimir(a, out)
    return out


def imprimir(a, o):
    sg = "compra" if o["direccion"] == "compra" else "venta"
    print(f"\nTIME MACHINE {o['instrumento']}  ·  {o['fecha']}  ·  entrada {o['hora']} CDMX  ·  seed {o['seed']}")
    print(f"Noche 00:00-8:59: {o['movimiento_noche']:+.2f} pts -> {sg.upper()}"
          + ("" if o["filtro_tendencia"] else f"   (OJO: menos de {a.tendencia:g} pts, la regla NO opera hoy; simulo igual)"))
    if o["provisional"]:
        print("PROVISIONAL: todavía no hay vela de la hora de entrada; uso el último precio y la tendencia hasta ahora.")
    print(f"Entrada {o['entrada']:.2f}   SL {o['sl']:.2f} ({a.sl} ticks)   TP1 {o['tp1']:.2f} ({a.tp1} ticks, "
          f"cierra {a.parcial:.0%}{'' if a.sin_be else ' + BE'})   TP2 {o['tp2']:.2f} ({a.tp2} ticks)")
    print(f"\n{a.replicas:,} réplicas del resto del día con {o['dias_banco']} días parecidos (misma dirección y "
          f"noche >= {a.tendencia:g} pts), bloques de {a.bloque} min{', volatilidad ajustada' if a.ajustar_vol else ''}:")
    for k, v in o["probabilidades"].items():
        print(f"  {k:34s} {v:5.1f} %")
    lo, med, hi = o["R_p5_p50_p95"]
    print(f"  R medio {o['R_medio']:+.3f}  (${o['usd_medio']:+.0f} con {a.contratos} {a.micro}, riesgo ${a.usd_r:.0f})   "
          f"R del 5 % peor / mediana / 5 % mejor: {lo:+.2f} / {med:+.2f} / {hi:+.2f}")
    h = o["historia"]
    print(f"\nHistoria real de la misma regla en esos {h['ops']} días: R medio {h['R_medio']:+.3f}  "
          f"(últimos 60: {h['ult60_R_medio']:+.3f})")
    print("  " + "   ".join(f"{k}: {v:.0f} %" for k, v in h["pct"].items() if v > 0))
    print(f"\nVeredicto: {o['veredicto']}")
    if "real" in o:
        print(f"Lo que pasó de verdad ese día: {o['real']['resultado']} ({o['real']['R']:+.2f} R)")
    print("Es una simulación con días pasados parecidos, no una predicción. Noticias (CPI, FOMC, NFP) pueden salirse de todo.")


def calibrar(a, dias):
    filas = []
    for d, g in sorted(dias.items()):
        if d.year != a.calibrar:
            continue
        c = condicion(g, a.hora_m, a.tendencia)
        if c is None or a.hora_m not in g.index:
            continue
        real = historia(dias, [d], c[0], a.hora_m, a).iloc[0]
        o = un_dia(a, dias, d, g, silencioso=True)
        p = o["probabilidades"]
        filas.append({"fecha": d, "p_sl": p[NOMBRES[0]], "p_tp2": p[NOMBRES[2]], "R_prev": o["R_medio"],
                      "R_hist": o["historia"]["R_medio"], "res": int(real.res), "R_real": float(real.R) - a.com_r})
    T = pd.DataFrame(filas)
    print(f"Calibración {a.calibrar}: {len(T)} días operables")
    T["bin_sl"] = pd.cut(T.p_sl, [0, 30, 35, 40, 45, 50, 100])
    print("\nProbabilidad de SL pronosticada vs SL real:")
    print(T.groupby("bin_sl", observed=True).agg(dias=("res", "size"), pronostico=("p_sl", "mean"),
                                                   real=("res", lambda x: (x == 0).mean() * 100)).round(1).to_string())
    T["bin_tp2"] = pd.cut(T.p_tp2, [0, 20, 25, 30, 35, 100])
    print("\nProbabilidad de TP2 pronosticada vs TP2 real:")
    print(T.groupby("bin_tp2", observed=True).agg(dias=("res", "size"), pronostico=("p_tp2", "mean"),
                                                    real=("res", lambda x: (x == 2).mean() * 100)).round(1).to_string())
    med = T.R_prev.median()
    for nom, m in (("R pronosticado arriba de la mediana", T.R_prev > med), ("R pronosticado abajo de la mediana", T.R_prev <= med)):
        print(f"{nom}: {m.sum()} días, R real medio {T.R_real[m].mean():+.3f}, total {T.R_real[m].sum():+.1f} R")
    print(f"Todos: R real medio {T.R_real.mean():+.3f}, total {T.R_real.sum():+.1f} R")
    T.drop(columns=["bin_sl", "bin_tp2"]).to_csv(f"backtest/resultados/timemachine_calibracion_{a.inst}_{a.calibrar}.csv", index=False)


def main(argv=None):
    a = parse(argv)
    dias = dias_csv(a.folder)
    if a.calibrar:
        a.replicas = min(a.replicas, 3000)
        return calibrar(a, dias)
    if a.vivo:
        fecha, g = dia_yahoo(a.ysym, date.fromisoformat(a.fecha) if a.fecha else None)
        real = None
        c = condicion(g, a.hora_m, 0)
        if c and a.hora_m in g.index and g.index.max() >= CIERRE - 1:  # el día ya terminó: lo que pasó de verdad
            s = c[0] if not a.direccion else (1 if a.direccion == "compra" else -1)
            h = historia({**dias, fecha: g}, [fecha], s, a.hora_m, a).iloc[0]
            real = {"resultado": NOMBRES[int(h.res)], "R": float(h.R) - a.com_r}
        o = un_dia(a, dias, fecha, g, real)
    else:
        fecha = date.fromisoformat(a.fecha) if a.fecha else max(dias)
        if fecha not in dias:
            raise SystemExit(f"{fecha} no está en los CSV (último día: {max(dias)}). Usa --vivo para días recientes.")
        g = dias[fecha]
        real = None
        c = condicion(g, a.hora_m, 0)
        if c and a.hora_m in g.index:
            s = c[0] if not a.direccion else (1 if a.direccion == "compra" else -1)
            h = historia(dias, [fecha], s, a.hora_m, a).iloc[0]
            real = {"resultado": NOMBRES[int(h.res)], "R": float(h.R) - a.com_r}
        o = un_dia(a, dias, fecha, g, real)
    if a.json:
        Path(a.json).write_text(json.dumps(o, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
