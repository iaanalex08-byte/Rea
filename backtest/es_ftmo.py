"""Modelo B (9:12 CDMX · SL 45 · TP 30/60) en una evaluación FTMO de 2 fases.

Reglas supuestas (FTMO 2-Step estándar, confirmar en ftmo.com):
  Fase 1: +10% · Fase 2: +5% · pérdida diaria máx. 5% · pérdida máx. 10% del saldo inicial (estática)
  mínimo 4 días operados por fase · sin límite de tiempo.
  Cuenta fondeada: mismos límites; primer retiro a los 14 días naturales (~10 días hábiles), 80% de la ganancia.
Se arranca la evaluación en cada día posible de la historia y se cuenta qué pasa.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
B = pd.read_csv(os.path.join(ROOT, "results/es/analisis_B_CDMX_45_30_60/b45_operaciones.csv"))
U2 = B.usd.to_numpy()          # USD por día con 2 ES


def fase(u, start, A, target_pct):
    eq, dias = 0.0, 0
    for i in range(start, len(u)):
        x = u[i]; dias += 1
        if x <= -0.05 * A or eq + x <= -0.10 * A:
            return "quema", i, dias
        eq += x
        if eq >= target_pct * A and dias >= 4:
            return "pasa", i, dias
    return "sin terminar", len(u) - 1, dias


def simular(A, contratos_es):
    u = U2 * contratos_es / 2
    res = []
    for s in range(len(u) - 20):
        r1, i1, d1 = fase(u, s, A, 0.10)
        if r1 != "pasa":
            res.append(dict(final=f"Fase 1: {r1}", dias=d1)); continue
        r2, i2, d2 = fase(u, i1 + 1, A, 0.05)
        if r2 != "pasa":
            res.append(dict(final=f"Fase 2: {r2}", dias=d1 + d2)); continue
        # cuenta fondeada: primer retiro tras 10 días hábiles si hay ganancia, sin perder el 10%
        eq, k, pago = 0.0, 0, None
        for j in range(i2 + 1, len(u)):
            k += 1
            if u[j] <= -0.05 * A or eq + u[j] <= -0.10 * A:
                pago = "quema"; break
            eq += u[j]
            if k >= 10 and eq > 0:
                pago = 0.8 * eq; break
        res.append(dict(final="Pasa las 2 fases", dias=d1 + d2, dias_f1=d1, dias_f2=d2,
                        primer_retiro=pago if isinstance(pago, float) else np.nan,
                        dias_retiro=(d1 + d2 + k) if isinstance(pago, float) else np.nan,
                        quema_fondeada=float(pago == "quema")))
    return pd.DataFrame(res)


rows = []
for A in (100_000, 200_000):
    for c in (1, 2, 4, 6):
        r = simular(A, c)
        ok = r[r.final == "Pasa las 2 fases"]
        stop = 1159 * c / 2
        rows.append(dict(cuenta=f"{A // 1000}K", contratos_ES=c, stop_usd=round(stop), stop_pct=stop / A,
                         pasa=(r.final == "Pasa las 2 fases").mean(),
                         quema_f1=(r.final == "Fase 1: quema").mean(), quema_f2=(r.final == "Fase 2: quema").mean(),
                         sin_terminar=r.final.str.contains("sin terminar").mean(),
                         dias_pasar_mediana=ok.dias.median(), dias_pasar_media=ok.dias.mean(),
                         dias_f1=ok.dias_f1.median() if len(ok) else np.nan, dias_f2=ok.dias_f2.median() if len(ok) else np.nan,
                         dias_hasta_primer_retiro=ok.dias_retiro.median() if len(ok) else np.nan,
                         primer_retiro_mediana=ok.primer_retiro.median() if len(ok) else np.nan,
                         quema_fondeada=ok.quema_fondeada.astype(float).mean() if len(ok) else np.nan))
R = pd.DataFrame(rows)
R.round(3).to_csv(os.path.join(ROOT, "results/es/ftmo_modelo_b.csv"), index=False)
pd.set_option("display.width", 250)
print(R.round(3).to_string(index=False))
