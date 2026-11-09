#!/usr/bin/env python3
"""Apex 25K intradía arriesgando $500-$700 por operación, solo con la 10:30, para pasar en 1-2 días.

Entrada: la 10:30 (POC 10:30-10:42, orden límite en el POC), con y sin "Evitar días malos". SL 66.5 pts.
Tamaño: el que hace que el SL valga $500 (4 MNQ = $532, o tamaño exacto como referencia).
La pérdida máxima de $1,000 sube con el mejor saldo, incluso con la operación abierta (deja de subir en +$100).
Planes:
  A) 1 día: TP de $1,500 (1:3 aprox.) en una operación.
  B) 2 días: TP de $750 por operación (1:1.5); pasa si ganan las dos.
  C) 2 días: día 1 TP $1,500; si pierde, día 2 con lo que queda de margen y TP por lo que falta.
Cierre forzado 15:55 CDMX. Se prueba empezando en cada día con señal (2024-2026).

    python3 backtest/apex_1030_50.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import apex_all_in as ap  # noqa: E402
import retroceso_1100 as rf  # noqa: E402

TARGET, DD, LOCK, SL = 1500, 1000, 100, 66.5
SIZES = [("4 MNQ ($532 de riesgo)", 8.0, 4 * 1.24), ("5 MNQ ($671 de riesgo)", 10.0, 5 * 1.24), ("tamaño exacto ($700)", 700 / SL, 5.26 * 1.24)]


def main():
    m1 = rf.bars()
    tm = (m1.index.hour * 60 + m1.index.minute).to_numpy()
    H, L, C = m1.high.to_numpy(), m1.low.to_numpy(), m1.close.to_numpy()
    S = ap.poc_entries("10:30", None).dropna().drop_duplicates("date")
    ops = pd.read_csv("backtest/resultados/ops_3_estrategias.csv")
    good = set(pd.to_datetime(ops[ops.estrategia == "10:30 con tendencia"].fecha).dt.date)

    def trade(sg, bal, peak, ppt, com, tp_usd, sl_usd):
        """Devuelve (estado, bal, peak). estado: tp, sl, quemada, cierre."""
        i = m1.index.searchsorted(sg.t)
        while i < len(C) and m1.index[i].date() == sg.date and tm[i] < 955:
            adv = ((L[i] if sg.dir == 1 else H[i]) - sg.px) * sg.dir * ppt
            fav = ((H[i] if sg.dir == 1 else L[i]) - sg.px) * sg.dir * ppt
            thr = min(peak - DD, LOCK)
            if adv <= -sl_usd:
                st_bal = bal - sl_usd - com
                if st_bal <= thr:
                    return "quemada", st_bal, peak
                return "sl", st_bal, peak
            if bal + adv - com <= thr:
                return "quemada", thr, peak
            if fav - com >= tp_usd:
                b = bal + tp_usd
                return "tp", b, max(peak, b)
            peak = max(peak, bal + fav - com)
            i += 1
        b = bal + (C[min(i, len(C) - 1) - 1] - sg.px) * sg.dir * ppt - com
        return "cierre", b, max(peak, b)

    rows = []
    for filt in ("sin filtro", "Evitar días malos"):
        X = S[S.date.isin(good)] if filt != "sin filtro" else S
        X = X.reset_index(drop=True)
        for sz, ppt, com in SIZES:
            sl_usd = SL * ppt
            resA, resB, resC = [], [], []
            for k in range(len(X) - 2):
                a, b = X.iloc[k], X.iloc[k + 1]
                st, bal, pk = trade(a, 0.0, 0.0, ppt, com, TARGET, sl_usd)
                resA.append(st == "tp")
                # C) segundo intento si no pasó y no se quemó
                if st == "tp":
                    resC.append(True)
                elif st == "quemada":
                    resC.append(False)
                else:
                    room = bal - min(pk - DD, LOCK)
                    st2, bal2, _ = trade(b, bal, pk, ppt, com, TARGET - bal, min(sl_usd, room - 1))
                    resC.append(st2 == "tp")
                # B) dos operaciones de $750
                st1, bal1, pk1 = trade(a, 0.0, 0.0, ppt, com, 750, sl_usd)
                if st1 == "quemada":
                    resB.append(False)
                else:
                    st2, bal2, _ = trade(b, bal1, pk1, ppt, com, TARGET - bal1, sl_usd)
                    resB.append(st2 == "tp" and bal2 >= TARGET - 1)
            yrs = pd.to_datetime(X.date.iloc[:len(resA)]).dt.year.to_numpy()
            for plan, r in (("A) 1 día, TP $1,500", resA), ("B) 2 días, $750 + $750", resB), ("C) 2 días, segundo intento", resC)):
                r = np.array(r)
                rows.append({"10:30": filt, "tamaño": sz, "plan": plan, "pasa %": round(100 * r.mean(), 1),
                             "2024-25 %": round(100 * r[yrs <= 2025].mean(), 1), "2026 %": round(100 * r[yrs == 2026].mean(), 1),
                             "pasa al menos 1 de 10 (misma op.) %": round(100 * r.mean(), 1),
                             "pasa al menos 1 de 10 (días distintos) %": round(100 * (1 - (1 - r.mean()) ** 10), 1),
                             "muestras": len(r)})
    T = pd.DataFrame(rows)
    T.to_csv("backtest/resultados/apex_1030_50.csv", index=False)
    pd.set_option("display.width", 250)
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
