#!/usr/bin/env python3
"""Apex 25K: evaluación en un día con el Modelo B (todo el drawdown en una operación), día de colchón también
"todo en una" con el Modelo B, y luego días mínimos con el Rascacielos (igual que apex_ciclo.py, que usaba la SP500 9:00).

Límite de Apex minuto a minuto: sigue al mejor saldo, incluida la ganancia abierta, y se fija en +$100.
Evaluación: meta $1,500, caída $1,000, 30 días (unas 21 sesiones); se opera solo en días con señal del Modelo B
  (10:12 NY, A y C por volumen, sin BOS en contra, VWAP), con k ES: stop = lo que queda hasta el límite, objetivo = la meta.
Cuenta PA (supuestos, verificar con Apex): misma caída de $1,000 intradía; día de colchón con el Modelo B buscando
  +$1,100 con el stop en el límite; después Rascacielos 9:30 NY, 6 MNQ, TP 10.5, SL 80 para juntar días de >= $100;
  retiro cuando hay 5 días de >= $100 y el saldo pasa de $1,600: se retira lo que pase de $1,100. 12 meses o hasta quemarse.
Se prueba empezando en cada día con señal hasta nov 2025 (para que haya 12 meses de datos después).

    python3 backtest/apex_ciclo_modelo_b.py
Salida: backtest/resultados/apex_ciclo_modelo_b.csv
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parent / "modelo_b"))
import rascacielos_50k as RZ  # noqa: E402
import perfil_volumen as pv  # noqa: E402
from estructura import cargar, velas, eventos  # noqa: E402
from variaciones import dias_ny, bos_contra  # noqa: E402

DD, LOCK, FEE = 1000.0, 100.0, 16.70
COSTO_ES = 17.0


def todo_en_una(d, k, meta, bal, peak):
    """Una operación del Modelo B con k ES, stop justo antes del límite y objetivo en `meta`. -> (estado, bal, peak)"""
    tv, cost = 12.5 * k, COSTO_ES * k
    piso0 = min(peak - DD, LOCK)
    sl = math.floor((bal - piso0 - cost) / tv) - 1
    tp = math.ceil((meta - bal + cost) / tv)
    if sl < 4 or tp < 1:
        return "sin margen", bal, peak
    up, dn = d["up"], d["dn"]
    for i in range(len(up)):
        piso = min(peak - DD, LOCK)
        if bal + dn[i] * tv - cost <= piso or dn[i] <= -sl:
            b = bal - sl * tv - cost if dn[i] <= -sl else piso
            return "quemada" if b <= min(peak - DD, LOCK) else "sl", b, peak
        if up[i] >= tp:
            b = bal + tp * tv - cost
            return "tp", b, max(peak, b)
        peak = max(peak, bal + up[i] * tv - cost)
    b = bal + d["cl"] * tv - cost
    return "cierre", b, max(peak, b)


def main():
    df = cargar()
    F = dias_ny(df, 10, 12, 20, 3)
    bc = bos_contra(F, eventos(velas(df, 3)))
    V = pv.rasgos_volumen(F)
    F = [d for d in F if d["date"] in V]
    f = pd.DataFrame([V[d["date"]] for d in F])
    m = f.A_vol.values & f.C_vol.values & np.array([not bc[d["date"]] for d in F]) & f["VWAP a favor"].values
    sig = {pd.Timestamp(d["date"]).date(): d for d, x in zip(F, m) if x}
    rz_list = RZ.rasca(10.5, 80, 6)
    rz = {d: v for d, v in zip(RZ.ALL, rz_list) if v != (0.0, 0.0)}
    allday = [d for d in pd.bdate_range("2024-01-02", "2026-11-04").date]
    starts = [i for i, d in enumerate(allday) if d in sig and d <= pd.Timestamp("2025-11-04").date()]
    out = []
    for k_eval in (2, 3):
        for k_col in (0, 2, 3):
            rows = []
            for si in starts:
                bal = peak = 0.0; k = si; passed = None; tries = 0
                while k < len(allday) and k < si + 21:
                    d = allday[k]; k += 1
                    if d not in sig:
                        continue
                    tries += 1
                    st, bal, peak = todo_en_una(sig[d], k_eval, 1500.0, bal, peak)
                    if st in ("quemada", "sin margen") or bal <= min(peak - DD, LOCK):
                        passed = False; break
                    if bal >= 1500:
                        passed = True; break
                if not passed:
                    rows.append(dict(pasa=False, cobrado=0.0, retiros=0, colchon=None, quemada=None)); continue
                bal = peak = 0.0; good = 0; cob = 0.0; nret = 0; burned = False; col = "sin día de colchón"
                end = min(len(allday), k + 252)
                while k_col and k < end:
                    d = allday[k]; k += 1
                    if d not in sig:
                        continue
                    st, bal, peak = todo_en_una(sig[d], k_col, 1100.0, bal, peak)
                    col = st
                    if st == "quemada" or bal <= min(peak - DD, LOCK):
                        burned = True
                    good += bal >= 100
                    if st in ("tp", "quemada") or bal >= 1100:
                        break
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
                rows.append(dict(pasa=True, cobrado=cob, retiros=nret, colchon=col, quemada=burned))
            T = pd.DataFrame(rows)
            p = T.pasa.mean(); pa = T[T.pasa]
            out.append(dict(eval_ES=k_eval, colchon_ES=k_col or "sin día de colchón", arranques=len(T), pasa_eval_pct=round(100 * p, 1),
                            colchon_tp_pct=round(100 * (pa.colchon == "tp").mean(), 1) if k_col else None,
                            retiro_1_pct=round(100 * (pa.retiros >= 1).mean(), 1), retiro_3_pct=round(100 * (pa.retiros >= 3).mean(), 1),
                            se_quema_pct=round(100 * pa.quemada.mean(), 1), cobrado_por_PA=round(pa.cobrado.mean()),
                            neto_por_eval=round(p * pa.cobrado.mean() - FEE), costo_por_PA=round(FEE / p) if p else None))
    O = pd.DataFrame(out)
    O.to_csv("backtest/resultados/apex_ciclo_modelo_b.csv", index=False)
    pd.set_option("display.width", 220)
    print(O.to_string(index=False))


if __name__ == "__main__":
    main()
