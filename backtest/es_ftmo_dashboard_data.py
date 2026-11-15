"""Datos del dashboard FTMO 100K para el modelo B: resultado por día de arranque y recorrido día a día."""
import os
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "results/es/ftmo_100k")
os.makedirs(OUT, exist_ok=True)
B = pd.read_csv(os.path.join(ROOT, "results/es/analisis_B_CDMX_45_30_60/b45_operaciones.csv"))
dates = B.date.to_numpy(); U2 = B.usd.to_numpy()
A = 100_000


def run(u, s):
    """Devuelve el recorrido día a día desde s: evaluación fase 1, fase 2 y cuenta fondeada hasta el primer retiro."""
    path, fase_n, eq, dias_fase, k_fund = [], 1, 0.0, 0, 0
    res = dict(final="Sin terminar (se acabaron los datos)", dias_f1=np.nan, dias_f2=np.nan, dias_retiro=np.nan, primer_retiro=np.nan)
    total = 0
    for i in range(s, len(u)):
        x = u[i]; total += 1; dias_fase += 1
        quema = x <= -0.05 * A or eq + x <= -0.10 * A
        eq_new = eq + x
        fase_lbl = {1: "Fase 1", 2: "Fase 2", 3: "Fondeada"}[fase_n]
        path.append(dict(dia=total, date=dates[i], fase=fase_lbl, usd=round(x, 2), saldo_fase=round(eq_new, 2)))
        if quema:
            res["final"] = {1: "Se quema en fase 1", 2: "Se quema en fase 2", 3: "Pasa, pero se quema fondeada"}[fase_n]
            break
        eq = eq_new
        if fase_n == 1 and eq >= 0.10 * A and dias_fase >= 4:
            res["dias_f1"] = dias_fase; fase_n, eq, dias_fase = 2, 0.0, 0
        elif fase_n == 2 and eq >= 0.05 * A and dias_fase >= 4:
            res["dias_f2"] = dias_fase; fase_n, eq, dias_fase = 3, 0.0, 0
            res["final"] = "Pasa (sin llegar aún al retiro)"
        elif fase_n == 3 and dias_fase >= 10 and eq > 0:
            res["final"] = "Pasa y cobra el primer retiro"; res["dias_retiro"] = total; res["primer_retiro"] = round(0.8 * eq, 2)
            break
    res["dias_total"] = total
    return res, path


rows, paths = [], []
starts_mes = pd.Series(range(len(dates))).groupby(pd.Series(dates).str[:7]).first()
for c in (1, 2, 4, 6):
    u = U2 * c / 2
    for s in range(len(u)):
        r, p = run(u, s)
        rows.append(dict(contratos=f"{c} ES", inicio=dates[s], **r))
        if s in starts_mes.values:
            for q in p:
                paths.append(dict(contratos=f"{c} ES", inicio=dates[s], **q))
R = pd.DataFrame(rows); P = pd.DataFrame(paths)
R.to_csv(os.path.join(OUT, "ftmo_arranques.csv"), index=False)
P.to_csv(os.path.join(OUT, "ftmo_recorridos.csv"), index=False)
print(R.groupby(["contratos", "final"]).size().unstack(fill_value=0))
print(len(P), os.path.getsize(os.path.join(OUT, "ftmo_recorridos.csv")))
