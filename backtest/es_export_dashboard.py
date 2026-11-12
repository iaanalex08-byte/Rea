"""Genera los CSV del dashboard (results/es/dashboard/) a partir de es_backtest.py."""
import json
import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
ES = os.path.join(ROOT, "results", "es")
OUT = os.path.join(ES, "dashboard")


def main():
    os.makedirs(OUT, exist_ok=True)
    d = json.load(open(os.path.join(ES, "es_data.json")))
    news = pd.read_csv(os.path.join(os.path.dirname(__file__), "news_calendar.csv"))
    cat = dict(zip(pd.to_datetime(news.date).dt.strftime("%Y-%m-%d"),
                   news.event.map(lambda e: "NFP/CPI 8:30" if e in ("NFP", "CPI") else "FOMC")))
    tr = []
    for z in ["NY", "CDMX"]:
        t = pd.read_csv(os.path.join(ES, f"es_trades_{z}.csv"))
        t["zone"] = z
        t["date"] = pd.to_datetime(t.date).dt.strftime("%Y-%m-%d")
        t["news"] = t.date.map(cat).fillna("Sin noticia")
        t["win"] = t.win.astype(int)
        t["usd"] = t.usd.round(2)
        tr.append(t[["zone", "model", "date", "side", "usd", "win", "news", "leg1", "leg2"]])
    pd.concat(tr).to_csv(os.path.join(OUT, "operaciones.csv"), index=False)

    rows = []
    for z, zd in d["zones"].items():
        for m, md in zd["models"].items():
            s = md["surface"]
            for i, tp in enumerate(s["tp"]):
                for j, sl in enumerate(s["sl"]):
                    rows.append(dict(zone=z, model=m, sl=sl, tp=tp, avg=s["avg"][i][j],
                                     pf=s["pf"][i][j], wr=s["wr"][i][j]))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "superficie.csv"), index=False)

    keys = ["n", "winrate", "pf", "net", "maxdd", "worst_streak"]
    rows = []
    for z, zd in d["zones"].items():
        for m, md in zd["models"].items():
            for v in md["variants"]:
                label = f"SL {v['sl']:g} · TP1 {v['tp1']:g} · TP2 {v['tp2']:g}" + (" (sin BE)" if v.get("note") else "")
                rows.append(dict(zone=z, model=m, group="variante", label=label, sl=v["sl"],
                                 tp1=v["tp1"], tp2=v["tp2"], **{k: v[k] for k in keys}))
            for v in md["rr"]:
                rows.append(dict(zone=z, model=m, group="rr", label=v["rr"], sl=v["sl"], tp1=v["tp"],
                                 tp2="", **{k: v[k] for k in keys}))
            for v in md["trends"]:
                rows.append(dict(zone=z, model=m, group="tendencia", label=v["trend"], sl="", tp1="",
                                 tp2="", **{k: v[k] for k in keys}))
    v = pd.DataFrame(rows)
    v[["winrate", "pf"]] = v[["winrate", "pf"]].round(4)
    v[["net", "maxdd"]] = v[["net", "maxdd"]].round(2)
    v.to_csv(os.path.join(OUT, "variantes.csv"), index=False)


if __name__ == "__main__":
    main()
