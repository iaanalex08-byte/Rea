"""Carga de velas de 1 minuto y construcción de velas H1 / H4 / diarias.

Todo el motor trabaja en "espacio de índice de 1 minuto": cada vela superior
guarda el índice de su primer minuto (start) y el índice siguiente a su último
minuto (end). Así no hay ambigüedades con horarios de verano.
"""
import glob
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


@dataclass
class Bars:
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    start: np.ndarray  # índice 1m del primer minuto
    end: np.ndarray    # índice 1m siguiente al último minuto (exclusivo)

    def mirrored(self):
        """Precios invertidos: un setup bajista pasa a ser uno alcista."""
        return Bars(-self.o, -self.l, -self.h, -self.c, self.start, self.end)


@dataclass
class Market:
    m1: Bars
    h1: Bars
    h4: Bars
    d1: Bars
    local: pd.DatetimeIndex   # hora local de Nueva York (sin tz) de cada minuto
    d1_day: np.ndarray        # fecha (trading day) de cada vela diaria

    def mirrored(self):
        return Market(self.m1.mirrored(), self.h1.mirrored(), self.h4.mirrored(),
                      self.d1.mirrored(), self.local, self.d1_day)


def load_m1(path=RAW):
    files = sorted(glob.glob(os.path.join(path, "*.csv")))
    if not files:
        raise FileNotFoundError(
            f"No hay CSV en {path}. Ejecuta: python backtest/download_data.py")
    df = pd.concat(
        pd.read_csv(f, sep=";", header=None,
                    names=["dt", "o", "h", "l", "c", "v"]) for f in files)
    ts = pd.to_datetime(df["dt"], format="%Y%m%d %H%M%S")
    ts = ts.dt.tz_localize("Etc/GMT+5").dt.tz_convert("America/New_York")
    df.index = ts
    df = df[~df.index.duplicated()].sort_index()
    return df[["o", "h", "l", "c"]]


def _aggregate(o, h, l, c, keys):
    cut = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    end = np.r_[cut[1:], len(keys)]
    return Bars(o[cut], np.maximum.reduceat(h, cut), np.minimum.reduceat(l, cut),
                c[end - 1], cut, end)


def build_market(df):
    o, h, l, c = (df[k].to_numpy(float) for k in "ohlc")
    local = df.index.tz_localize(None)
    m1 = Bars(o, h, l, c, np.arange(len(o)), np.arange(1, len(o) + 1))

    utc_hour = df.index.tz_convert("UTC").tz_localize(None).to_numpy().astype("datetime64[h]").astype(np.int64)
    h1 = _aggregate(o, h, l, c, utc_hour)

    # Día de trading: la sesión de futuros va de 18:00 a 17:00 (hora NY).
    tday = (local + pd.Timedelta(hours=6)).normalize()
    tday_num = tday.to_numpy().astype("datetime64[D]").astype(np.int64)
    block = ((local.hour - 18) % 24) // 4          # velas H4: 18,22,02,06,10,14
    h4 = _aggregate(o, h, l, c, tday_num * 10 + block.to_numpy())
    d1 = _aggregate(o, h, l, c, tday_num)
    d1_day = tday[d1.start].date
    return Market(m1, h1, h4, d1, local, np.array(d1_day))
