"""Días promedio para llegar a un retiro con el modelo B (9:12 CDMX, SL 45 · TP 30/60).

Ciclos sobre la historia real: se arranca en 0; cuando la ganancia desde el último retiro llega
al objetivo se retira y se vuelve a 0. Si la pérdida desde el arranque del ciclo llega al límite
de la cuenta (pérdida máxima trailing de fin de día), la cuenta se quema y se empieza otra.
También se mide arrancando en cada día posible (para no depender de un único punto de partida).
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
B = pd.read_csv(os.path.join(ROOT, "results/es/analisis_B_CDMX_45_30_60/b45_operaciones.csv"))
usd_2es = B.usd.to_numpy()


def ciclos(u, target, limit):
    pagos, quemas, dias, d, eq, peak = [], 0, [], 0, 0.0, 0.0
    for x in u:
        d += 1; eq += x; peak = max(peak, eq)
        if eq >= target:
            dias.append(d); pagos.append(eq); d = 0; eq = 0.0; peak = 0.0
        elif limit and eq <= peak - limit:
            quemas += 1; d = 0; eq = 0.0; peak = 0.0
    return dias, quemas


def desde_cada_dia(u, target, limit):
    res = []
    for s in range(len(u)):
        eq = peak = 0.0
        for k, x in enumerate(u[s:], 1):
            eq += x; peak = max(peak, eq)
            if eq >= target:
                res.append(("retiro", k)); break
            if limit and eq <= peak - limit:
                res.append(("quema", k)); break
        else:
            res.append(("sin llegar", len(u) - s))
    r = pd.DataFrame(res, columns=["fin", "dias"])
    ok = r[r.fin == "retiro"]
    return dict(pct_retiro=(r.fin == "retiro").mean(), pct_quema=(r.fin == "quema").mean(),
                dias_media=ok.dias.mean(), dias_mediana=ok.dias.median(), dias_p80=ok.dias.quantile(.8))


rows = []
for cuenta, factor, limit in [("2 ES · cuenta propia (sin límite)", 1, None), ("2 ES · límite de pérdida 6 000", 1, 6000),
                              ("1 ES · límite de pérdida 3 000 (tipo 100K)", .5, 3000),
                              ("4 MES · límite de pérdida 2 000 (tipo 50K)", .2, 2000), ("2 MES · límite 2 000", .1, 2000)]:
    u = usd_2es * factor
    for target in (500, 1000, 2000, 3000, 5000):
        dias, quemas = ciclos(u, target, limit)
        e = desde_cada_dia(u, target, limit)
        rows.append(dict(cuenta=cuenta, retiro=target, retiros_en_historia=len(dias), quemas_en_historia=quemas,
                         neto_retiros_menos_quemas=len(dias) * target - quemas * (limit or 0),
                         dias_promedio_ciclos=np.mean(dias) if dias else np.nan, **e))
R = pd.DataFrame(rows)
R.round(3).to_csv(os.path.join(ROOT, "results/es/retiros_modelo_b.csv"), index=False)
pd.set_option("display.width", 220)
print(R.round(2).to_string(index=False))
print("días hábiles en la historia:", len(u))
