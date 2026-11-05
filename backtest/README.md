# Backtest — POC Apertura CDMX

Hay dos formas de correr el backtest. Ambas aplican las mismas reglas que el indicador `poc_apertura_cdmx.pine`.

## 1. Python, con tus datos (`poc_backtest.py`)

1. Exporta velas de **3 min** (también acepta 1 min) de **MES1!** o **ES1!**. Sirven TradingView ("Exportar datos del gráfico"), NinjaTrader, Sierra Chart o cualquier CSV con `time, open, high, low, close, volume`.
   - Si las velas son de 1 min, el script las agrupa en velas de 3 min.
   - Si el archivo es grande, puedes pasar varios CSV y el script los une.
2. Corre:

```bash
pip install pandas numpy matplotlib
python3 backtest/poc_backtest.py datos/MES_1m.csv
```

**Desde NinjaTrader 8:** también acepta los `.txt` que genera *Tools → Historical Data → Export* (formato `yyyyMMdd HHmmss;open;high;low;close;volume`). Puedes pasar los archivos sueltos, una carpeta o un `.zip`:

- Detecta sola la zona horaria del archivo (o la fijas con `--nt-tz America/Chicago`).
- Pasa la hora de cierre de vela que usa NinjaTrader a hora de apertura.
- Si hay un archivo por vencimiento (ES 03-24, ES 06-24, …), cada día usa el contrato con más volumen.

```bash
python3 backtest/poc_backtest.py export_ninjatrader.zip --start 2024-01-01
```

Por defecto usa los últimos 3 años del archivo y los valores de tu indicador: perfil 9:00 + 12 min, ventana 9:12–13:30, SL 9, R:R 2.5, TP1 a 1R con 50 %, 50 contratos y **$5/punto (MES)**.

Opciones útiles:

| Opción | Para qué |
|---|---|
| `--point-value 50` | ES en lugar de MES |
| `--commission 1.24` | comisión ida y vuelta por contrato en $ |
| `--slippage 0.25` | deslizamiento en puntos por operación |
| `--start 2023-11-01 --end 2026-10-31` | rango de fechas |
| `--input-tz UTC` | si la columna `time` viene en texto sin zona horaria y no es hora CDMX |
| `--sl 9 --rr 2.5 --partial-r 1 --partial-pct 50` | gestión |

Resultados en `backtest/resultados/`: `operaciones.csv`, `dias.csv`, `por_anio.csv`, `por_mes.csv`, `resumen.csv` y `equity.png`.

Pruebas de escenarios: `python3 backtest/test_poc_backtest.py`

## 2. TradingView (`poc_apertura_cdmx_strategy.pine`)

Es la versión `strategy()`. Pégala en el editor de Pine, ponla en MES1! a 3 min y abre el **Probador de Estrategias**. Para cubrir 3 años en 3 min necesitas *Deep Backtesting* (plan Premium o superior).

Diferencias con la versión de Python:

- **Orden de llenado:** cuando en una misma vela se tocan dos niveles, el emulador de TradingView decide el orden según la forma de la vela. Python siempre asume primero SL o BE.
- **Fin de día:** si la operación sigue abierta al cambiar de día, TradingView la cierra a mercado y cuenta el resultado real. Python solo cuenta lo cobrado en TP1 y la marca como "sin resolver".
- **Precio de entrada:** la entrada es una orden límite en el POC. Si el precio abre con gap a través del POC, se llena al precio de apertura.
