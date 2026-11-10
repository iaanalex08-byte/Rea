# Rea — backtest de la estrategia FVG / envolventes en Nasdaq

Backtest 2025–2026 de una versión **mecánica** de la estrategia (sesgo diario →
zonas H4/H1 → gatillo en 1 minuto, RR 1:2, ventana horaria y filtro de noticias).

- Reglas exactas: docstring de [`backtest/strategy.py`](backtest/strategy.py) (todas son parámetros de `Params`).
- Resultados: [`results/RESULTS.md`](results/RESULTS.md), [`results/trades.csv`](results/trades.csv),
  [`results/sensitivity.csv`](results/sensitivity.csv), [`results/equity.png`](results/equity.png).

## Cómo ejecutarlo

```bash
pip install pandas numpy matplotlib tabulate histdata
python backtest/download_data.py   # descarga NSXUSD 1m a data/raw/
python backtest/run_backtest.py    # genera results/
```

## Supuestos importantes

- **Datos**: NSXUSD (CFD del Nasdaq 100) de HistData.com, no el futuro NQ. Los niveles
  difieren ligeramente del NQ, pero la estructura intradía es equivalente.
- **Noticias**: `backtest/news_calendar.csv` es una lista aproximada de días de
  NFP, CPI y FOMC. Conviene revisarla con un calendario oficial.
- **Ejecución**: entrada al cierre de la vela gatillo, coste de 1 punto por operación; si una
  vela toca stop y objetivo a la vez, se cuenta como pérdida.
- Las partes discrecionales del método original (máximos "clave", "impulso fuerte",
  envolvente "válida") se tradujeron a reglas concretas; otras traducciones darán
  otros resultados.
