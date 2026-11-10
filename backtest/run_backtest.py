"""Ejecuta el backtest 2025-2026 y genera los resultados en results/.

    python backtest/run_backtest.py
"""
import os
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data import load_m1, build_market
from strategy import Params, backtest, stats

OUT = os.path.join(os.path.dirname(__file__), "..", "results")
ACCOUNT = 50_000
RISK_PCT = 0.005            # 0,5% por operación -> 250 USD por R


def bootstrap(r, n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    means = rng.choice(r, (n, len(r)), replace=True).mean(1)
    return np.percentile(means, [2.5, 97.5]), float((means <= 0).mean())


def prop_sim(r, risk_usd, target=3_000, mll=2_000):
    """Evaluación tipo fondeo 50K: objetivo +3.000 USD, pérdida máxima
    trailing de 2.000 USD (se congela en el saldo inicial). Se arranca en cada
    operación de la serie y se cuenta cuántas veces se pasa / se quema."""
    out = {"pasa": 0, "quema": 0, "sin_resolver": 0}
    for s in range(len(r)):
        bal, peak = 0.0, 0.0
        res = "sin_resolver"
        for x in r[s:]:
            bal += x * risk_usd
            peak = max(peak, bal)
            floor = min(peak - mll, 0.0)
            if bal >= target:
                res = "pasa"
                break
            if bal <= floor:
                res = "quema"
                break
        out[res] += 1
    return out


def fmt(x, d=2):
    return f"{x:.{d}f}" if isinstance(x, (float, np.floating)) else str(x)


def main():
    os.makedirs(OUT, exist_ok=True)
    mk = build_market(load_m1())
    base = Params()
    tr, log = backtest(mk, base)
    tr.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    log.to_csv(os.path.join(OUT, "daily_log.csv"), index=False)
    st = stats(tr)
    r = tr["R"].to_numpy()

    md = []
    md.append("# Resultados del backtest (generado por run_backtest.py)\n")
    md.append(f"Datos: NSXUSD 1m (HistData), {mk.local[0]:%Y-%m-%d} → {mk.local[-1]:%Y-%m-%d}. "
              f"Costes: {base.cost_pts} pts por operación. Riesgo: {RISK_PCT:.1%} de "
              f"{ACCOUNT:,} USD = {ACCOUNT*RISK_PCT:.0f} USD por R.\n")
    md.append("## Caso base\n")
    md.append("| Métrica | Valor |\n|---|---|")
    names = dict(trades="Operaciones", winrate="Tasa de acierto (TP)", avg_R="Esperanza por operación (R)",
                 total_R="Resultado total (R)", profit_factor="Profit factor",
                 max_dd_R="Drawdown máximo (R)", max_losing_streak="Racha perdedora máxima",
                 avg_risk_pts="Stop medio (puntos)")
    for k, v in st.items():
        md.append(f"| {names[k]} | {v:.1%} |" if k == "winrate" else f"| {names[k]} | {fmt(v)} |")
    md.append(f"| Resultado en USD (250 USD/R) | {st['total_R']*ACCOUNT*RISK_PCT:,.0f} |")
    if len(r) > 1:
        ci, p0 = bootstrap(r)
        md.append(f"| IC 95% de la esperanza (bootstrap) | [{ci[0]:.2f}, {ci[1]:.2f}] R |")
        md.append(f"| Prob. bootstrap de esperanza ≤ 0 | {p0:.0%} |")
    md.append("")

    md.append("## Qué pasó cada día\n")
    oc = log["outcome"].value_counts()
    md.append("| Resultado del día | Días |\n|---|---|")
    for k, v in oc.items():
        md.append(f"| {k} | {v} |")
    md.append("")

    md.append("## Por año y por lado\n")
    tr["year"] = pd.to_datetime(tr["date"]).dt.year
    g = tr.groupby(["year", "side"])["R"].agg(["count", "mean", "sum"]).round(2)
    md.append(g.to_markdown())
    md.append("")
    md.append("## Por mes (R)\n")
    tr["month"] = pd.to_datetime(tr["date"]).dt.to_period("M").astype(str)
    mo = tr.groupby("month")["R"].agg(["count", "sum"]).round(2)
    md.append(mo.to_markdown())
    md.append("")

    md.append("## Simulación de cuenta de fondeo 50K\n")
    md.append("Objetivo +3.000 USD, pérdida máxima trailing 2.000 USD. Se arranca la evaluación "
              "en cada operación de la serie histórica.\n")
    md.append("| Riesgo por operación | Pasa | Se quema | Sin resolver |\n|---|---|---|---|")
    for ru in (250, 500, 1000):
        ps = prop_sim(r, ru)
        n = sum(ps.values())
        md.append(f"| {ru} USD | {ps['pasa']/n:.0%} | {ps['quema']/n:.0%} | {ps['sin_resolver']/n:.0%} |")
    md.append("")

    # --------------------------------------------------------- sensibilidad
    variants = [
        ("Caso base", {}),
        ("Entrar en todas las zonas (no saltar la 1ª)", dict(select="all")),
        ("Saltar solo la 1ª zona", dict(select="skip_first")),
        ("Impulso medido con swings H1", dict(leg_tf="H1")),
        ("Solo FVG (sin envolventes)", dict(use_engulf=False)),
        ("Envolvente = cuerpo completo", dict(engulf_mode="body")),
        ("Solo zonas H1", dict(zone_tfs=("H1",))),
        ("Solo compras", dict(directions="long")),
        ("Sin filtro de noticias", dict(news_filter=False)),
        ("Ventana 9:30-10:00", dict(entry_end="10:00")),
        ("Ventana 9:30-11:00", dict(entry_end="11:00")),
        ("Ventana 9:30-11:30", dict(entry_end="11:30")),
        ("Ventana 9:30-11:00 + saltar solo la 1ª", dict(entry_end="11:00", select="skip_first")),
        ("RR 1:1.5", dict(rr=1.5)),
        ("RR 1:3", dict(rr=3.0)),
        ("Stop máx. 40 pts", dict(max_risk=40)),
        ("Stop máx. 100 pts", dict(max_risk=100)),
        ("Sin costes", dict(cost_pts=0.0)),
        ("Costes x2 (2 pts)", dict(cost_pts=2.0)),
    ]
    rows = []
    for name, kw in variants:
        t, _ = backtest(mk, replace(base, **kw))
        s = stats(t)
        rows.append(dict(variante=name, ops=s.get("trades", 0),
                         acierto=f"{s.get('winrate', 0):.0%}",
                         esperanza_R=round(s.get("avg_R", 0), 2),
                         total_R=round(s.get("total_R", 0), 1),
                         PF=round(s.get("profit_factor", 0), 2),
                         maxDD_R=round(s.get("max_dd_R", 0), 1)))
    sens = pd.DataFrame(rows)
    sens.to_csv(os.path.join(OUT, "sensitivity.csv"), index=False)
    md.append("## Sensibilidad (cada fila cambia una sola regla)\n")
    md.append(sens.to_markdown(index=False))
    md.append("")
    md.append("## Operaciones\n")
    md.append(tr[["date", "side", "entry_time", "entry", "stop", "tp", "risk_pts", "result",
                  "R", "zone_kind", "zone_tf"]].round({"entry": 2, "stop": 2, "tp": 2, "risk_pts": 2, "R": 2})
              .to_markdown(index=False))
    with open(os.path.join(OUT, "RESULTS.md"), "w") as f:
        f.write("\n".join(md) + "\n")

    # --------------------------------------------------------- gráfico
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), height_ratios=[2, 1], sharex=False)
    x = pd.to_datetime(tr["date"])
    eq = np.cumsum(r)
    ax[0].step(x, eq, where="post", color="#2563eb", lw=2)
    ax[0].axhline(0, color="#888", lw=0.8)
    ax[0].set_title("Curva de capital (R acumulados) — caso base, 2025-2026")
    ax[0].set_ylabel("R")
    ax[0].grid(alpha=0.3)
    ax2 = ax[0].twinx()
    d1c = pd.Series(mk.d1.c, index=pd.to_datetime(mk.d1_day))
    ax2.plot(d1c.index, d1c.values, color="#999", lw=0.8, alpha=0.6)
    ax2.set_ylabel("Nasdaq 100", color="#999")
    colors = ["#16a34a" if v > 0 else "#dc2626" for v in r]
    ax[1].bar(range(len(r)), r, color=colors)
    ax[1].set_title("Resultado de cada operación (R)")
    ax[1].set_xlabel("Nº de operación")
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "equity.png"), dpi=130)
    print("\n".join(md[:40]))


if __name__ == "__main__":
    main()
