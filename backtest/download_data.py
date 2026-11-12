"""Descarga velas de 1 minuto del Nasdaq 100 (NSXUSD) desde HistData.com.

Uso:
    pip install histdata
    python backtest/download_data.py

Los CSV quedan en data/raw/. HistData publica la hora en EST fija (UTC-5, sin
horario de verano); backtest/data.py la convierte a hora de Nueva York.
"""
import os
import zipfile
from datetime import date

from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as T

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def main(years=(2025, 2026), pair="nsxusd"):
    os.makedirs(OUT, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(OUT)
    try:
        today = date.today()
        for y in years:
            if y < today.year:
                files = [dl(year=str(y), month=None, pair=pair,
                            platform=P.GENERIC_ASCII, time_frame=T.ONE_MINUTE)]
            else:
                files = []
                for m in range(1, today.month + 1):
                    try:
                        files.append(dl(year=str(y), month=m, pair=pair,
                                        platform=P.GENERIC_ASCII,
                                        time_frame=T.ONE_MINUTE))
                    except Exception as e:  # mes aún no publicado
                        print(f"{y}-{m:02d}: {e}")
            for f in files:
                with zipfile.ZipFile(f) as z:
                    for n in z.namelist():
                        if n.endswith(".csv"):
                            z.extract(n)
                os.remove(f)
    finally:
        os.chdir(cwd)


if __name__ == "__main__":
    main()
