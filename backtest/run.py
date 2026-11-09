"""
Ejecuta todo el estudio y escribe results/*.csv, results/*.png y results/summary.json.

    python -m backtest.run            # usa los CSV de data/
    python -m backtest.run --download # vuelve a bajar datos de Yahoo Finance
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import replace, asdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .strategy import Params, run, stats

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "results"
SYMBOLS = {"NQ": dict(ticker="NQ=F", point_value=20.0), "ES": dict(ticker="ES=F", point_value=50.0)}


def download():
    import yfinance as yf
    DATA.mkdir(exist_ok=True)
    for name, s in SYMBOLS.items():
        for period, iv in [("60d", "30m"), ("60d", "5m"), ("730d", "1h")]:
            d = yf.download(s["ticker"], period=period, interval=iv, progress=False, auto_adjust=False)
            d.columns = [c[0].lower() for c in d.columns]
            d = d[["open", "high", "low", "close", "volume"]].dropna()
            d.index = d.index.tz_convert("America/New_York")
            d.index.name = "time"
            d.to_csv(DATA / f"{name}_{iv}.csv")


def load(name, iv):
    d = pd.read_csv(DATA / f"{name}_{iv}.csv", index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("America/New_York")
    return d


GRID = dict(
    fvg_mode=["below_pivot", "any", "none"],
    entry=["edge", "mid"],
    target_mode=["swing", "fixed"],
    daily_loss_usd=[500, 1000, 1500, 2500],
    max_adds=[0, 1],
)


def grid(base: Params):
    keys = list(GRID)
    for vals in itertools.product(*GRID.values()):
        yield replace(base, **dict(zip(keys, vals)))


def label(p: Params):
    return (f"{p.fvg_mode}|{p.entry}|{p.target_mode}|DLL{int(p.daily_loss_usd)}|adds{p.max_adds}")


def apex_eval(tr: pd.DataFrame, target=3000.0, trailing=2500.0, max_days=30):
    """Simula evaluaciones Apex 50K arrancando cada día con operativa.
    Aproximación: el trailing drawdown se sigue con el PnL realizado (cierre de trade)
    y con el peor flotante de cada trade (MAE) -> ligeramente conservador vs. real
    porque el máximo flotante a favor no se registra."""
    if tr.empty:
        return dict(attempts=0)
    tr = tr.copy()
    tr["day"] = pd.to_datetime(tr["exit_time"]).dt.date
    days = sorted(tr["day"].unique())
    res = []
    for k, start in enumerate(days):
        bal, peak, outcome = 0.0, 0.0, "timeout"
        sub = tr[tr["day"] >= start]
        for d in days[k:k + max_days]:
            for _, t in sub[sub["day"] == d].iterrows():
                if bal + t["mae_usd"] <= peak - trailing:
                    outcome = "bust"; break
                bal += t["pnl_usd"]
                peak = min(max(peak, bal), trailing + 100)  # Apex: el umbral deja de subir en saldo inicial + 100
                if bal <= peak - trailing:
                    outcome = "bust"; break
                if bal >= target:
                    outcome = "pass"; break
            if outcome != "timeout":
                break
        res.append(outcome)
    s = pd.Series(res)
    return dict(attempts=len(s), pass_pct=round(100 * (s == "pass").mean(), 1),
                bust_pct=round(100 * (s == "bust").mean(), 1),
                timeout_pct=round(100 * (s == "timeout").mean(), 1))


def equity_plot(curves: dict, path: Path, title: str):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for name, tr in curves.items():
        if tr.empty:
            continue
        x = pd.to_datetime(tr["exit_time"])
        ax.step(x, tr["pnl_usd"].cumsum(), where="post", label=name, lw=1.6)
    ax.axhline(0, color="#888", lw=0.8)
    ax.set_title(title)
    ax.set_ylabel("PnL acumulado (USD, 1 contrato)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    if a.download:
        download()
    OUT.mkdir(exist_ok=True)
    summary = {}
    base_cfgs = {
        "base (fiel al video)": dict(),
        "base + 1 promediada": dict(max_adds=1),
    }

    for sym, s in SYMBOLS.items():
        m30, m5, h1 = load(sym, "30m"), load(sym, "5m"), load(sym, "1h")
        base = Params(point_value=s["point_value"],
                      add_step_pts=20.0 if sym == "NQ" else 5.0,
                      target_pts=40.0 if sym == "NQ" else 10.0,
                      min_target_pts=10.0 if sym == "NQ" else 2.5)
        summary[sym] = {"data": {
            "M30": [str(m30.index[0]), str(m30.index[-1]), len(m30)],
            "H1": [str(h1.index[0]), str(h1.index[-1]), len(h1)]}}

        # 1) configuración base en los tres modos de datos
        curves_m30, curves_h1 = {}, {}
        for name, kw in base_cfgs.items():
            p = replace(base, **kw)
            tr_a, _ = run(m30, p, m5)
            tr_b, _ = run(h1, p)
            tr_a.to_csv(OUT / f"{sym}_trades_M30_{'adds' if kw else 'base'}.csv", index=False)
            tr_b.to_csv(OUT / f"{sym}_trades_H1_{'adds' if kw else 'base'}.csv", index=False)
            curves_m30[name], curves_h1[name] = tr_a, tr_b
            summary[sym][name] = {
                "M30 (60 días, ejecución 5m)": stats(tr_a), "H1 (2 años)": stats(tr_b),
                "Apex 50K eval (H1)": apex_eval(tr_b)}

        # 2) barrido de parámetros
        rows = []
        for p in grid(base):
            for tf, df, ex in [("M30", m30, m5), ("H1", h1, None)]:
                tr, _ = run(df, p, ex)
                st = stats(tr)
                rows.append(dict(cfg=label(p), tf=tf, **st))
        sweep = pd.DataFrame(rows)
        sweep.to_csv(OUT / f"{sym}_sweep.csv", index=False)

        # 3) walk-forward en H1: elegir en el 1er año, probar en el 2º
        mid = h1.index[0] + (h1.index[-1] - h1.index[0]) / 2
        is_df, oos_df = h1[h1.index < mid], h1[h1.index >= mid]
        wf = []
        for p in grid(base):
            tr_is, _ = run(is_df, p)
            tr_oos, _ = run(oos_df, p)
            si, so = stats(tr_is), stats(tr_oos)
            wf.append(dict(cfg=label(p), is_trades=si.get("trades", 0), is_net=si.get("net_usd", 0),
                           is_pf=si.get("profit_factor", 0), oos_trades=so.get("trades", 0),
                           oos_net=so.get("net_usd", 0), oos_pf=so.get("profit_factor", 0),
                           params=p))
        wf = pd.DataFrame(wf)
        ctrl = wf[wf.cfg.str.startswith("none")]
        wf = wf[~wf.cfg.str.startswith("none")]
        best = wf[wf.is_trades >= 30].sort_values("is_net", ascending=False).iloc[0]
        wf.drop(columns="params").to_csv(OUT / f"{sym}_walkforward.csv", index=False)
        corr = np.corrcoef(wf.is_net, wf.oos_net)[0, 1]
        bp = best["params"]
        tr_best_h1, _ = run(h1, bp)
        tr_best_m30, _ = run(m30, bp, m5)
        curves_h1["mejor in-sample (" + label(bp) + ")"] = tr_best_h1
        curves_m30["mejor in-sample (" + label(bp) + ")"] = tr_best_m30
        summary[sym]["walk_forward"] = dict(
            split=str(mid.date()), best_in_sample=label(bp),
            is_net=float(best.is_net), is_pf=float(best.is_pf), oos_net=float(best.oos_net),
            oos_pf=float(best.oos_pf), oos_trades=int(best.oos_trades),
            pct_cfgs_profitable_is=round(100 * (wf.is_net > 0).mean(), 1),
            pct_cfgs_profitable_oos=round(100 * (wf.oos_net > 0).mean(), 1),
            pct_cfgs_profitable_both=round(100 * ((wf.is_net > 0) & (wf.oos_net > 0)).mean(), 1),
            corr_is_oos=round(float(corr), 2),
            median_oos_net_strategy=float(wf.oos_net.median()),
            median_oos_net_control_sin_fvg=float(ctrl.oos_net.median()),
            median_is_net_strategy=float(wf.is_net.median()),
            median_is_net_control_sin_fvg=float(ctrl.is_net.median()),
            best_full_H1=stats(tr_best_h1), best_M30=stats(tr_best_m30),
            best_apex=apex_eval(tr_best_h1))

        equity_plot(curves_m30, OUT / f"{sym}_equity_M30.png", f"{sym} – M30, últimos 60 días (ejecución en 5m)")
        equity_plot(curves_h1, OUT / f"{sym}_equity_H1.png", f"{sym} – H1, ~2 años")

    with open(OUT / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o),
                  ensure_ascii=False)
    print(json.dumps(summary, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
