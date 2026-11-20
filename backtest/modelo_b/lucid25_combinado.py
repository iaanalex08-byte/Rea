#!/usr/bin/env python3
"""Lucid Flex 25K FONDEADA con el ciclo combinado (Modelo B "Más dinero" + SP500 9:00 con confirmación).
Supuestos (verificar con Lucid): caída 1,000 USD al cierre del día que sigue al saldo más alto y se congela en +100;
retiro con 5 días de +100 o más desde el último retiro y saldo positivo; se retira el 50 % y el trader cobra el 90 %.
Tamaño por gap: completo si el gap ya se cerró antes de entrar; si no, la mitad redondeada hacia abajo (mínimo 1 MES).
Se arranca una cuenta en cada día hábil de 2024-01 a 2025-11 y se sigue 12 meses.
    python3 backtest/modelo_b/lucid25_combinado.py
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from lucid50_combinado import operaciones  # noqa: E402

DD, LOCK = 1000.0, 100.0


def pnl(lst, mb, sp, por_gap):
    t = 0.0
    for mod, v, cerrado in lst:
        full = cerrado or not por_gap
        if mod == "B" and mb:
            n = mb if full else max(1, mb // 2)
            t += v * (n / 2) * 1.25 - n * 2.49
        elif mod == "S" and sp:
            n = sp if full else max(1, sp // 2)
            t += v * 75.0 * n
    return t


def cuenta(dias, ops, i0, mb, sp, por_gap):
    bal = hwm = 0.0; buenos = 0; cob = 0.0; primero = None; n = 0
    for k in range(i0, min(len(dias), i0 + 252)):
        if dias[k] not in ops:
            continue
        u = pnl(ops[dias[k]], mb, sp, por_gap)
        bal += u; hwm = max(hwm, bal); buenos += u >= 100
        if bal <= min(hwm - DD, LOCK):
            return cob, primero, n, True
        if buenos >= 5 and bal > 0:
            r = bal * 0.5; cob += r * 0.9; bal -= r; buenos = 0; n += 1
            primero = primero or k - i0 + 1
    return cob, primero, n, False


ops = operaciones()
dias = list(pd.bdate_range("2024-01-02", "2026-11-04").date)
starts = [i for i, d in enumerate(dias) if d <= pd.Timestamp("2025-11-04").date()]
filas = []
for mb, sp in ((3, 0), (4, 0), (3, 1), (3, 2), (4, 2), (6, 2), (6, 3)):
    for pg in (False, True):
        R = [cuenta(dias, ops, i, mb, sp, pg) for i in starts]
        prim = [x[1] for x in R if x[1]]
        filas.append(dict(modelo_B=mb, sp500=sp, tamano_por_gap="sí" if pg else "no", riesgo_max_dia=round(mb * 39.99 + sp * 75),
                          llega_1er_retiro_pct=round(100 * len(prim) / len(R), 1), dias_habiles_1er_retiro=int(np.median(prim)) if prim else None,
                          semanas_1er_retiro=round(np.median(prim) / 5, 1) if prim else None, retiros_12m=round(np.mean([x[2] for x in R]), 1),
                          se_quema_pct=round(100 * np.mean([x[3] for x in R]), 1), cobrado_12m=round(np.mean([x[0] for x in R]))))
T = pd.DataFrame(filas); T.to_csv("backtest/resultados/lucid25_combinado.csv", index=False)
pd.set_option("display.width", 220); print(T.to_string(index=False))
