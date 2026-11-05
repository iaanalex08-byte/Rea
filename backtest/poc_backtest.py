#!/usr/bin/env python3
"""
Backtest de "POC Apertura CDMX" — réplica en Python de la lógica del indicador Pine.

Uso:
    python3 backtest/poc_backtest.py datos.csv [otro.csv ...] [opciones]

CSV esperado (export de TradingView, NinjaTrader, etc.): columnas time, open, high,
low, close, volume (los nombres no distinguen mayúsculas). `time` puede ser Unix
(segundos o milisegundos) o fecha/hora en texto. Si el texto no trae zona horaria
se interpreta con --input-tz. Si las velas son de menos de 3 min se re-muestrean.

Reglas (idénticas al indicador):
  * Tendencia: apertura de la 1.ª vela del día (CDMX) vs último cierre antes del perfil.
  * Perfil de volumen en [inicio, inicio+duración); volumen repartido en partes iguales
    entre las filas que toca cada vela; POC = fila de mayor volumen.
  * Ruptura (vela completa o solo cierre) a favor de la tendencia, en una vela posterior
    a la que calcula el POC.
  * Entrada: primera vela posterior a la ruptura que toca el POC, dentro de la ventana.
  * Gestión desde la vela siguiente a la entrada:
      - SL antes del parcial            -> PERDIDA
      - TP1 (parcial) y luego TP2       -> GANADA
      - TP1 y luego regresa a la entrada -> PARCIAL + BE
      - Sin resolver al cambiar de día  -> SIN RESOLVER (se conserva lo cobrado en TP1)
    Si en una vela se tocan dos niveles, se asume primero SL / BE (conservador).
"""
import argparse
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Backtest POC Apertura CDMX")
    p.add_argument("csv", nargs="+", help="Archivo(s) CSV con velas OHLCV")
    p.add_argument("--input-tz", default="Etc/GMT+6",
                   help="Zona horaria de la columna time si no trae offset (default: UTC-6)")
    p.add_argument("--nt-tz", default="auto",
                   help="Zona horaria de los archivos de NinjaTrader (default: auto-detectar)")
    p.add_argument("--tz", default="Etc/GMT+6",
                   help="Zona horaria de la estrategia (default: UTC-6 fija, sin horario de verano; "
                        "en notación IANA 'Etc/GMT+6' = UTC-6)")
    p.add_argument("--tf", type=int, default=3, help="Temporalidad en minutos (default 3)")
    p.add_argument("--start", help="Fecha inicial YYYY-MM-DD (default: 3 años antes del último dato)")
    p.add_argument("--end", help="Fecha final YYYY-MM-DD")
    # Perfil
    p.add_argument("--prof-hour", type=int, default=9)
    p.add_argument("--prof-min", type=int, default=0)
    p.add_argument("--prof-dur", type=int, default=12)
    # Ventana
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--win-start", default="09:12")
    p.add_argument("--win-end", default="13:30")
    # Perfil de volumen
    p.add_argument("--row-size", type=float, default=None,
                   help="Tamaño de fila en puntos (si no se da, automático 20 filas)")
    p.add_argument("--brk-mode", choices=["vela", "cierre"], default="vela")
    # Gestión
    p.add_argument("--sl", type=float, default=9.0, help="Stop loss en puntos")
    p.add_argument("--rr", type=float, default=2.5, help="Ratio R:R del TP2")
    p.add_argument("--partial-r", type=float, default=1.0, help="TP1 en múltiplos de R")
    p.add_argument("--partial-pct", type=float, default=50.0, help="%% de contratos en TP1")
    p.add_argument("--no-be", action="store_true", help="No mover el SL a BE tras el parcial")
    p.add_argument("--max-wait", type=float, default=None,
                   help="Minutos máximos entre la ruptura y el retroceso (si se pasa, no se opera ese día)")
    p.add_argument("--min-trend", type=float, default=0.0, help="Tendencia previa mínima en pts")
    p.add_argument("--min-range", type=float, default=0.0, help="Rango mínimo del perfil en pts")
    # Dinero
    p.add_argument("--qty", type=float, default=50, help="Contratos")
    p.add_argument("--point-value", type=float, default=5.0, help="$ por punto (MES=5, ES=50)")
    p.add_argument("--mintick", type=float, default=0.25)
    p.add_argument("--commission", type=float, default=0.0,
                   help="Comisión ida y vuelta por contrato en $")
    p.add_argument("--slippage", type=float, default=0.0,
                   help="Deslizamiento en puntos por operación (se descuenta del resultado)")
    p.add_argument("--min-coverage", type=float, default=0.9,
                   help="Fracción mínima de velas presentes entre 00:00 y el fin de la ventana para usar el día "
                        "(descarta días con huecos en los datos; 0 = usar todos)")
    p.add_argument("--out", default="backtest/resultados", help="Carpeta de salida")
    return p.parse_args(argv)


# ----------------------------------------------------------------------------- datos
NT_TZ_CANDIDATES = ["UTC", "America/New_York", "America/Chicago", "America/Mexico_City",
                    "America/Denver", "America/Los_Angeles", "Europe/Madrid"]


def _is_ninjatrader(path):
    """Export de NinjaTrader 8: 'yyyyMMdd HHmmss;open;high;low;close;volume' sin encabezado."""
    with open(path, "r", errors="ignore") as f:
        first = f.readline().strip()
    return bool(re.match(r"^\d{8} \d{6};", first))


def _contract_name(path):
    m = re.search(r"([A-Z]{1,4})[ _](\d{2}-\d{2})", Path(path).name)
    return f"{m.group(1)} {m.group(2)}" if m else Path(path).stem


def _guess_nt_tz(raw):
    """Las exportaciones de NinjaTrader no dicen su zona horaria. Se elige la zona en la que
    el pico de volumen cae en la apertura de Nueva York (9:30 ET)."""
    best, best_share = None, -1.0
    sample = raw.iloc[:: max(1, len(raw) // 200000)]
    for cand in NT_TZ_CANDIDATES:
        ts = sample["ts_local"].dt.tz_localize(cand, ambiguous="NaT", nonexistent="NaT")
        ny = ts.dt.tz_convert("America/New_York")
        m = ny.dt.hour * 60 + ny.dt.minute
        v = sample["volume"].to_numpy()
        tot = np.nansum(v)
        share = np.nansum(v[((m >= 570) & (m < 575)).to_numpy()]) / tot if tot else 0
        if share > best_share:
            best, best_share = cand, share
    return best


def _read_one(path, input_tz, nt_tz):
    if _is_ninjatrader(path):
        raw = pd.read_csv(path, sep=";", header=None,
                          names=["t", "open", "high", "low", "close", "volume"])
        raw["ts_local"] = pd.to_datetime(raw["t"], format="%Y%m%d %H%M%S")
        tzname = nt_tz
        if tzname in (None, "auto"):
            tzname = _guess_nt_tz(raw)
            print(f"{Path(path).name}: formato NinjaTrader, zona horaria detectada = {tzname}", file=sys.stderr)
        ts = raw["ts_local"].dt.tz_localize(tzname, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
        # NinjaTrader marca la vela con su hora de CIERRE; se pasa a hora de apertura
        step = ts.diff().dropna().dt.total_seconds().mode()
        step = pd.Timedelta(seconds=float(step.iloc[0]) if len(step) else 60)
        df = raw.assign(ts=ts - step)
        df["contract"] = _contract_name(path)
        return df[["ts", "open", "high", "low", "close", "volume", "contract"]].dropna(subset=["ts"])

    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ("time", "datetime", "date", "timestamp") if c in df.columns), None)
    if tcol is None:
        sys.exit(f"{path}: falta columna de tiempo (time/datetime/date/timestamp)")
    if "volume" not in df.columns:
        vc = next((c for c in df.columns if "vol" in c), None)
        if vc is None:
            sys.exit(f"{path}: falta columna volume")
        df = df.rename(columns={vc: "volume"})
    t = df[tcol]
    if pd.api.types.is_numeric_dtype(t):
        unit = "ms" if t.max() > 1e11 else "s"
        ts = pd.to_datetime(t, unit=unit, utc=True)
    else:
        t = t.astype(str).str.strip()
        has_offset = t.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True).all()
        if has_offset:
            ts = pd.to_datetime(t, utc=True, format="mixed")
        else:
            ts = pd.to_datetime(t, format="mixed")
            ts = ts.dt.tz_localize(input_tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    df = df.assign(ts=ts, contract=_contract_name(path))
    return df[["ts", "open", "high", "low", "close", "volume", "contract"]].dropna(subset=["ts"])


def _expand(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(x for x in p.rglob("*") if x.suffix.lower() in (".txt", ".csv"))
        elif p.suffix.lower() == ".zip":
            dest = p.with_suffix("")
            with zipfile.ZipFile(p) as z:
                z.extractall(dest)
            out += sorted(x for x in dest.rglob("*") if x.suffix.lower() in (".txt", ".csv"))
        else:
            out.append(p)
    return out


def load_bars(paths, input_tz, tz, tf, nt_tz="auto"):
    frames = [_read_one(p, input_tz, nt_tz) for p in _expand(paths)]
    df = pd.concat(frames)
    df["volume"] = df["volume"].fillna(0)

    # Varios contratos (un archivo por vencimiento): cada día se usa el de mayor volumen
    if df["contract"].nunique() > 1 and df.groupby("ts").size().max() > 1:
        day = df["ts"].dt.tz_convert(tz).dt.date
        vol = df.groupby([day, "contract"])["volume"].sum()
        front = vol.groupby(level=0).idxmax().map(lambda x: x[1])
        df = df[df["contract"].to_numpy() == day.map(front).to_numpy()]
        rolls = front[front != front.shift()]
        print("Contrato usado por fecha: " + ", ".join(f"{d} {c}" for d, c in rolls.items()), file=sys.stderr)

    df = df.drop_duplicates("ts").sort_values("ts").set_index("ts").drop(columns="contract")

    step = df.index.to_series().diff().dt.total_seconds().div(60).median()
    if step < tf - 1e-9:
        df = df.resample(f"{tf}min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna(subset=["open"])
    elif step > tf + 1e-9:
        print(f"AVISO: las velas son de {step:g} min, mayores a --tf {tf}.", file=sys.stderr)
    df.index = df.index.tz_convert(tz)
    return df


# ----------------------------------------------------------------------------- motor
def round_tick(x, tick):
    # Igual que math.round_to_mintick de Pine: al tick más cercano, empates hacia arriba
    return math.floor(x / tick + 0.5) * tick


def run(df, a):
    tick = a.mintick
    pStart = a.prof_hour * 60 + a.prof_min
    pEnd = pStart + a.prof_dur
    wsh, wsm = map(int, a.win_start.split(":"))
    weh, wem = map(int, a.win_end.split(":"))
    wStart, wEnd = wsh * 60 + wsm, weh * 60 + wem
    fPart = a.partial_pct / 100.0
    tp1Pts = a.sl * a.partial_r
    tp2Pts = a.sl * a.rr

    idx = df.index
    O, H, L, C, V = (df[c].to_numpy(float) for c in ("open", "high", "low", "close", "volume"))
    tmins = (idx.hour * 60 + idx.minute).to_numpy()
    days = idx.day.to_numpy()
    dates = idx.date

    trades = []
    days_info = []
    cur = None  # operación en curso

    def close_day_record():
        if day is not None:
            days_info.append(day)

    day = None
    for i in range(len(df)):
        tmin = tmins[i]
        newDay = i == 0 or days[i] != days[i - 1]
        if newDay:
            if cur is not None and cur["result"] is None:
                cur["result"] = "SIN RESOLVER"
                cur["exit_time"] = idx[i - 1]
                cur["pts"] = cur["banked"]
            close_day_record()
            day = {"date": dates[i], "status": "sin tendencia"}
            trendOpen, trendClose = O[i], C[i]
            pHigh = pLow = None
            bH, bL, bV = [], [], []
            startIdx = sigBar = brkBar = entryBar = None
            pocLvl = slLvl = tpLvl = partLvl = None
            dirTrend = 0
            stage = 0
            done = False
            partDone = False
            resolved = False
            cur = None

        if tmin < pStart:
            trendClose = C[i]

        if pStart <= tmin < pEnd:
            if startIdx is None:
                startIdx = i
            pHigh = H[i] if pHigh is None else max(pHigh, H[i])
            pLow = L[i] if pLow is None else min(pLow, L[i])
            bH.append(H[i]); bL.append(L[i]); bV.append(V[i])

        if not done and tmin >= pEnd and len(bV) > 0:
            done = True
            rs = a.row_size if a.row_size else max(tick, (pHigh - pLow) / 20)
            nRows = max(1, int(math.ceil((pHigh - pLow) / rs)))
            vols = [0.0] * nRows
            for k in range(len(bV)):
                rFrom = min(nRows - 1, int(math.floor((bL[k] - pLow) / rs)))
                rTo = min(nRows - 1, int(math.floor((bH[k] - pLow) / rs)))
                cnt = max(1, rTo - rFrom + 1)
                for r in range(rFrom, rTo + 1):
                    vols[r] += bV[k] / cnt
            maxV = max(vols)
            pocRow = vols.index(maxV) if maxV > 0 else int(nRows / 2)
            poc = round_tick(pLow + (pocRow + 0.5) * rs, tick)
            day.update(poc=poc, trend="alcista" if trendClose > trendOpen else
                       ("bajista" if trendClose < trendOpen else "plana"))
            if trendClose != trendOpen and abs(trendClose - trendOpen) >= a.min_trend \
                    and (pHigh - pLow) >= a.min_range:
                isUp = trendClose > trendOpen
                dirTrend = 1 if isUp else -1
                pocLvl = poc
                sigBar = i
                slLvl = round_tick(poc - a.sl if isUp else poc + a.sl, tick)
                tpLvl = round_tick(poc + tp2Pts if isUp else poc - tp2Pts, tick)
                partLvl = round_tick(poc + tp1Pts if isUp else poc - tp1Pts, tick)
                day["status"] = "sin ruptura"

        # Ruptura
        if stage == 0 and dirTrend != 0 and pocLvl is not None and i > sigBar:
            if a.brk_mode == "vela":
                brokeDown, brokeUp = H[i] < pocLvl, L[i] > pocLvl
            else:
                brokeDown, brokeUp = C[i] < pocLvl, C[i] > pocLvl
            if (dirTrend == -1 and brokeDown) or (dirTrend == 1 and brokeUp):
                stage = 1
                brkBar = i
                day["status"] = "ruptura sin retroceso"

        # Entrada
        inWin = a.no_window or (wStart <= tmin < wEnd)
        if stage == 1 and a.max_wait is not None and i > brkBar and \
                (idx[i] - idx[brkBar]).total_seconds() / 60 > a.max_wait:
            stage = 3
            day["status"] = "retroceso tardío"
        if stage == 1 and i > brkBar and inWin:
            retest = H[i] >= pocLvl if dirTrend == -1 else L[i] <= pocLvl
            if retest:
                stage = 2
                entryBar = i
                cur = {"date": dates[i], "dir": "COMPRA" if dirTrend == 1 else "VENTA",
                       "entry_time": idx[i], "entry": pocLvl, "sl": slLvl, "tp1": partLvl,
                       "tp2": tpLvl, "result": None, "exit_time": None, "banked": 0.0,
                       "partial": False, "pts": 0.0,
                       "brk_time": idx[brkBar], "trend_pts": trendClose - trendOpen,
                       "prof_range": pHigh - pLow, "entry_idx": i}
                trades.append(cur)
                day["status"] = "operó"

        # Gestión
        if stage == 2 and not resolved and i > entryBar:
            up = dirTrend == 1
            slHit = L[i] <= slLvl if up else H[i] >= slLvl
            tpHit = H[i] >= tpLvl if up else L[i] <= tpLvl
            beLvl = slLvl if a.no_be else pocLvl
            beHit = L[i] <= beLvl if up else H[i] >= beLvl
            if not partDone:
                partHit = H[i] >= partLvl if up else L[i] <= partLvl
                if slHit:
                    resolved = True
                    cur.update(result="PERDIDA", exit_time=idx[i], pts=-a.sl)
                elif partHit:
                    partDone = True
                    cur["partial"] = True
                    cur["banked"] = tp1Pts * fPart
                    if tpHit and not beHit:
                        resolved = True
                        cur.update(result="GANADA", exit_time=idx[i],
                                   pts=tp1Pts * fPart + tp2Pts * (1 - fPart))
            else:
                if beHit:
                    resolved = True
                    cur.update(result="PARCIAL + BE" if not a.no_be else "PARCIAL + SL", exit_time=idx[i],
                               pts=tp1Pts * fPart - (a.sl * (1 - fPart) if a.no_be else 0))
                elif tpHit:
                    resolved = True
                    cur.update(result="GANADA", exit_time=idx[i],
                               pts=tp1Pts * fPart + tp2Pts * (1 - fPart))

    if cur is not None and cur["result"] is None:
        cur.update(result="ABIERTA", exit_time=idx[-1], pts=cur["banked"])
    close_day_record()
    return pd.DataFrame(trades), pd.DataFrame(days_info)


def filter_days(df, a):
    """Descarta días con huecos en los datos."""
    if a.min_coverage <= 0:
        return df, 0
    weh, wem = map(int, a.win_end.split(":"))
    lim = weh * 60 + wem
    tm = df.index.hour * 60 + df.index.minute
    d = pd.Series(df.index.date, index=df.index)
    cnt = d[tm < lim].groupby(d[tm < lim]).size()
    prof = d[(tm >= a.prof_hour * 60 + a.prof_min) & (tm < a.prof_hour * 60 + a.prof_min + a.prof_dur)]
    pcnt = prof.groupby(prof).size()
    good = set(cnt[cnt >= a.min_coverage * lim / a.tf].index) & set(pcnt[pcnt >= a.prof_dur / a.tf].index)
    keep = d.isin(good).to_numpy()
    return df[keep], len(set(d)) - len(good)


# ----------------------------------------------------------------------------- reporte
def add_money(tr, a):
    if tr.empty:
        return tr
    tr = tr.copy()
    tr["pts_netos"] = tr["pts"] - a.slippage
    tr["usd"] = tr["pts_netos"] * a.point_value * a.qty - a.commission * a.qty
    tr["equity"] = tr["usd"].cumsum()
    return tr


def summary(tr):
    n = len(tr)
    c = tr["result"].value_counts()
    w, be, l = c.get("GANADA", 0), c.get("PARCIAL + BE", 0), c.get("PERDIDA", 0)
    u = c.get("SIN RESOLVER", 0) + c.get("ABIERTA", 0)
    closed = w + be + l
    gp = tr.loc[tr.usd > 0, "usd"].sum()
    gl = -tr.loc[tr.usd < 0, "usd"].sum()
    eq = tr["equity"]
    dd = (eq - eq.cummax().clip(lower=0)).min() if n else 0.0
    # rachas de pérdidas
    streak = mx = 0
    for r in tr["result"]:
        streak = streak + 1 if r == "PERDIDA" else 0
        mx = max(mx, streak)
    return {
        "Operaciones": n,
        "Ganadas (TP2)": w,
        "Parcial + BE": be,
        "Perdidas": l,
        "Sin resolver": u,
        "% acierto (TP2)": 100 * w / closed if closed else 0.0,
        "% llegó a TP1": 100 * (w + be) / closed if closed else 0.0,
        "Neto (pts/contrato)": tr["pts_netos"].sum(),
        "Neto ($)": tr["usd"].sum(),
        "Promedio por operación ($)": tr["usd"].mean() if n else 0.0,
        "Profit factor": gp / gl if gl else float("inf"),
        "Máx. drawdown ($)": dd,
        "Máx. racha de pérdidas": mx,
    }


def fmt(v):
    if isinstance(v, (float, np.floating)):
        return f"{v:,.2f}"
    return f"{v:,}" if isinstance(v, (int, np.integer)) else str(v)


def main(argv=None):
    a = parse_args(argv)
    df = load_bars(a.csv, a.input_tz, a.tz, a.tf, a.nt_tz)
    end = pd.Timestamp(a.end, tz=a.tz) + pd.Timedelta(days=1) if a.end else df.index[-1] + pd.Timedelta(minutes=1)
    start = pd.Timestamp(a.start, tz=a.tz) if a.start else end - pd.DateOffset(years=3)
    df = df[(df.index >= start) & (df.index < end)]
    if df.empty:
        sys.exit("No hay datos en el rango pedido.")

    df, skipped = filter_days(df, a)
    if df.empty:
        sys.exit("Ningún día tiene datos completos (prueba --min-coverage 0).")
    tr, days = run(df, a)
    tr = add_money(tr, a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\nDatos: {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}  "
          f"({len(df):,} velas de {a.tf} min, {len(days):,} días)")
    print(f"Parámetros: perfil {a.prof_hour:02d}:{a.prof_min:02d}+{a.prof_dur}min, ventana "
          f"{'sin límite' if a.no_window else a.win_start + '-' + a.win_end}, SL {a.sl} pts, "
          f"R:R {a.rr}, TP1 {a.partial_r}R al {a.partial_pct:g}%, {a.qty:g} contratos × "
          f"${a.point_value:g}/pt, comisión ${a.commission:g}/contrato, slippage {a.slippage:g} pts")
    if skipped:
        print(f"Días descartados por huecos en los datos: {skipped:,}")
    if not days.empty:
        print("Días: " + ", ".join(f"{k}: {v}" for k, v in days["status"].value_counts().items()))
    if tr.empty:
        print("\nNo hubo operaciones.")
        return

    s = summary(tr)
    print("\n=== RESUMEN ===")
    for k, v in s.items():
        print(f"  {k:<28}{fmt(v):>14}")

    tr["año"] = pd.to_datetime(tr["date"]).dt.year
    rows = []
    for y, g in tr.groupby("año"):
        sy = summary(g.assign(equity=g["usd"].cumsum()))
        rows.append({"Año": y, **{k: sy[k] for k in ("Operaciones", "Ganadas (TP2)", "Parcial + BE",
                     "Perdidas", "Sin resolver", "% acierto (TP2)", "Neto ($)", "Máx. drawdown ($)")}})
    by_year = pd.DataFrame(rows)
    print("\n=== POR AÑO ===")
    print(by_year.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

    tr["mes"] = pd.to_datetime(tr["date"]).dt.to_period("M")
    monthly = tr.groupby("mes")["usd"].sum()
    print(f"\nMeses positivos: {(monthly > 0).sum()} de {len(monthly)}  |  "
          f"mejor mes ${monthly.max():,.0f}  |  peor mes ${monthly.min():,.0f}")

    tr.drop(columns=["año", "mes"]).to_csv(out / "operaciones.csv", index=False)
    days.to_csv(out / "dias.csv", index=False)
    by_year.to_csv(out / "por_anio.csv", index=False)
    monthly.rename("usd").to_csv(out / "por_mes.csv")
    pd.Series(s).to_csv(out / "resumen.csv", header=["valor"])
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 4.5))
        x = pd.to_datetime(tr["exit_time"].astype(str).str[:19])
        ax.plot(x, tr["equity"], color="#089981", lw=1.6)
        ax.fill_between(x, tr["equity"], tr["equity"].cummax().clip(lower=0), color="#f23645", alpha=0.15)
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_title("POC Apertura CDMX — curva de capital ($)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / "equity.png", dpi=130)
        print(f"\nArchivos en {out}/: operaciones.csv, dias.csv, por_anio.csv, por_mes.csv, resumen.csv, equity.png")
    except ImportError:
        print(f"\nArchivos en {out}/ (instala matplotlib para la gráfica equity.png)")


if __name__ == "__main__":
    main()
