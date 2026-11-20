#!/usr/bin/env python3
"""Apex 25K (seguimiento intradía): pasar en 1 día con la SP500 de las 9:00, otro día de SP500 para el colchón
y luego días mínimos con el Rascacielos. Simulación minuto a minuto del límite que sube con la ganancia abierta.

Evaluación ($16.70): objetivo $1,500, pérdida máx. $1,000 que sigue al mejor saldo (incluida la ganancia abierta),
  deja de subir en +$100; 30 días. SP500 9:00 a favor de la tendencia (noche >= 20 pts), SL 15 pts, 12 MES ($900),
  TP 25.5 pts (+$1,530). Si no pasa ni se quema, repite en el siguiente día con señal (hasta 21 días hábiles).
Cuenta PA (supuestos, verificar con Apex): misma pérdida máx. $1,000 intradía (se fija en +$100);
  día de colchón: SP500 con 6 MES (mitad de contratos), SL 15, TP 30 pts (1:2);
  después Rascacielos 9:30 NY, 6 MNQ, TP 10.5, SL 80 (o lo que quede de margen) para juntar días de >= $100;
  retiro cuando hay 5 días de >= $100 y el saldo pasa de $1,600: se retira lo que exceda $1,100 (colchón de seguridad).
12 meses o hasta quemarse. Se prueba empezando en cada día con señal de 2024-2026.

    python3 backtest/apex_ciclo.py [TP del día de colchón en pts, 0 = sin colchón] [todo]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import rascacielos_50k as RZ  # noqa: E402
import sp500_0912_grid as g  # noqa: E402
from sp500_0912 import bars  # noqa: E402

DD, LOCK, FEE = 1000, 100, 16.70
COM_MES = 1.24 + 0.25 * 5  # comisión + 1 tick de deslizamiento por MES


def sp_day(day, n, sl, tp, bal, peak):
    """Una operación SP500 9:00 con n MES. Devuelve (estado, bal, peak). estado: tp, sl, cierre, quemada."""
    d, tm, O, H, L, C = day
    i = int(np.flatnonzero(tm == 540)[0])
    mv = C[tm < 540][-1] - O[0]
    s = 1 if mv > 0 else -1
    ent = O[i] + s * 0.25
    pv = 5.0 * n
    cost = COM_MES * n
    for j in range(i, len(C)):
        if tm[j] >= 900:
            b = bal + (O[j] - ent) * s * pv - cost
            return "cierre", b, max(peak, b)
        adv = ((L[j] if s == 1 else H[j]) - ent) * s
        fav = ((H[j] if s == 1 else L[j]) - ent) * s
        thr = min(peak - DD, LOCK)
        if adv <= -sl:
            b = bal - sl * pv - cost
            return ("quemada" if b <= thr else "sl"), b, peak
        if bal + adv * pv - cost <= thr:
            return "quemada", thr, peak
        if fav >= tp:
            b = bal + tp * pv - cost
            return "tp", b, max(peak, b)
        peak = max(peak, bal + fav * pv - cost)
    b = bal + (C[-1] - ent) * s * pv - cost
    return "cierre", b, max(peak, b)


def main():
    ctp = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0  # TP del día de colchón (pts); 0 = sin día de colchón
    all_starts = len(sys.argv) > 2 and sys.argv[2] == 'todo'
    days = [x for x in g.prep(bars("backtest/datos"))]
    sig = {}
    for x in days:
        d, tm, O, H, L, C = x
        if (tm == 540).sum() == 0 or (tm < 540).sum() == 0:
            continue
        if abs(C[tm < 540][-1] - O[0]) >= 20:
            sig[d] = x
    rz_list = RZ.rasca(10.5, 80, 6)
    rz = {d: v for d, v in zip(RZ.ALL, rz_list) if v != (0.0, 0.0)}
    allday = [d for d in pd.bdate_range("2024-01-02", "2026-11-06").date]
    starts = [i for i, d in enumerate(allday) if d in sig and (all_starts or d <= pd.Timestamp("2025-11-06").date())]
    rows = []
    for si in starts:
        # Evaluación
        bal = peak = 0.0; k = si; passed = None; tries = 0
        while k < len(allday) and k < si + 21:
            d = allday[k]; k += 1
            if d not in sig:
                continue
            tries += 1
            st, bal, peak = sp_day(sig[d], 12, 15, 25.5, bal, peak)
            if st == "quemada" or bal <= min(peak - DD, LOCK):
                passed = False; break
            if bal >= 1500:
                passed = True; break
        if not passed:
            rows.append({"inicio": allday[si], "pasa": False, "dias_eval": tries, "pasa_1er_dia": False, "colchon": None, "cobrado": 0.0, "retiros": 0, "quemada_pa": None})
            continue
        first = tries == 1
        # Cuenta PA: día de colchón con SP500 (6 MES, 1:2)
        bal = peak = 0.0; good = 0; cob = 0.0; nret = 0; burned = False; col = None
        end = min(len(allday), k + 252)
        while ctp > 0 and k < end:
            d = allday[k]; k += 1
            if d not in sig:
                continue
            st, bal, peak = sp_day(sig[d], 6, 15, ctp, bal, peak)
            col = st
            if st == "quemada" or bal <= min(peak - DD, LOCK):
                burned = True
            good += (bal >= 100)
            break
        # Días mínimos con Rascacielos
        while not burned and k < end:
            d = allday[k]; k += 1
            if d not in rz:
                continue
            pnl, mae = rz[d]
            thr = min(peak - DD, LOCK)
            if bal - mae <= thr or bal + pnl < thr:
                burned = True; break
            bal += pnl; peak = max(peak, bal); good += pnl >= 100
            if good >= 5 and bal >= 1600:
                cob += bal - 1100; nret += 1; bal = 1100.0; good = 0
        rows.append({"inicio": allday[si], "pasa": True, "dias_eval": tries, "pasa_1er_dia": first, "colchon": col, "cobrado": cob, "retiros": nret, "quemada_pa": burned})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/apex_ciclo.csv", index=False)
    p = T.pasa.mean(); p1 = T.pasa_1er_dia.mean()
    pa = T[T.pasa]
    print(f"Arranques probados: {len(T)}")
    print(f"Evaluación: pasa {100 * p:.1f}% (en el 1er día {100 * p1:.1f}%), días con operación para pasar {pa.dias_eval.mean():.1f}")
    print(f"Día de colchón (SP500 6 MES 1:2): {pa.colchon.value_counts(normalize=True).round(3).to_dict()}")
    print(f"Cuenta PA: llega a 1 retiro {100 * (pa.retiros >= 1).mean():.1f}%, a 3 {100 * (pa.retiros >= 3).mean():.1f}%, cobrado prom ${pa.cobrado.mean():,.0f} (mediana ${pa.cobrado.median():,.0f}), se quema {100 * pa.quemada_pa.mean():.0f}%")
    print(f"Neto esperado por evaluación comprada: ${p * pa.cobrado.mean() - FEE:,.0f}  (evaluaciones por cuenta PA: {1 / p:.1f}, costo ${FEE / p:,.0f})")
    by = pa.groupby(pd.to_datetime(pa.inicio).dt.year).cobrado.mean().round().to_dict()
    print("Cobrado por cuenta PA según año de inicio:", by)


if __name__ == "__main__":
    main()
