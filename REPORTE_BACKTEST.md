# Backtest: tendencia M30 + EMA20 + imbalances (FVG) + límite de pérdida diario

**Activos:** NQ (Nasdaq-100 E-mini, $20/pt) y ES (S&P 500 E-mini, $50/pt), 1 contrato por cuenta.
**Datos:** Yahoo Finance (futuros continuos).
- **M30 real**: últimos ~60 días (31-ago-2026 → 8-nov-2026), con fills y salidas resueltos en velas de **5 minutos**.
- **H1 como sustituto**: ~2 años (17-jun-2024 → 8-nov-2026). Yahoo solo da 60 días de datos intradía en 30m, así que H1 es la única forma gratuita de tener una muestra grande.

**Costes:** $5 de comisión ida y vuelta por contrato y 1 tick de slippage en las salidas a mercado.

> **Conclusión corta:** con reglas objetivas, **la metodología no muestra ventaja estadística**. En 2 años
> de H1 la versión fiel al video pierde dinero en NQ (−$3,885) y en ES (−$10,915). La simulación de
> evaluación Apex 50K pasa solo un **4 %** de las veces en NQ y un **13 %** en ES. Los 60 días de M30 salen en positivo,
> pero con **8 y 4 trades** no se puede sacar ninguna conclusión de ahí. La única pieza que sí aporta algo es el
> filtro del imbalance: entrar sin él (control) es mucho peor.

---

## 1. Cómo se tradujeron las reglas a código

| Regla del video | Implementación (`backtest/strategy.py`) |
|---|---|
| Tendencia diagonal en M30 + EMA20 | Alcista si `close > EMA20` **y** la EMA20 sube respecto a hace 5 velas. Bajista: lo contrario. Si no se cumple ninguna, no se opera. |
| Máximos / mínimos relevantes | Pivotes fractales con 3 velas a cada lado. Un pivote solo se usa una vez confirmado (3 velas después), así que no hay look-ahead. |
| Imbalance | Fair Value Gap de 3 velas que todavía no ha sido tocado (como máximo 48 velas de antigüedad). |
| Compra: imbalance **por debajo de mínimos** | En tendencia alcista, FVG alcista cuyo techo está **por debajo del último mínimo relevante** → orden **límite de compra** en el techo del FVG (variante: en el 50 %). Las ventas son el espejo. |
| Sin stop por estructura; corte por flotante (personal daily loss) | Sin stop. Se cierra todo cuando el flotante llega a −DLL (por defecto **$1,000**). Ese día no se vuelve a operar. |
| Promediadas | Variante con 1 entrada extra de 1 contrato a 20 pts en contra (NQ) o 5 pts en contra (ES). El límite de $ se mantiene, así que con 2 contratos el corte llega antes en puntos. |
| Pocas ejecuciones | Máximo 2 trades por día. |
| *No especificado en el video* **[supuesto]** | Objetivo = último máximo/mínimo relevante opuesto (liquidez), con variante de objetivo fijo (40 pts NQ / 10 pts ES). Órdenes solo entre 08:00 y 15:00 hora NY, cierre forzado a las 15:55 (Apex cierra a las 16:59 ET). |

**Ejecución conservadora:** dentro de una misma vela se evalúa primero la pérdida y después el objetivo. Además,
**en la vela donde se llena la orden no se acepta el objetivo**, porque no se sabe si el máximo o mínimo ocurrió antes
del fill. Esta regla importa mucho (ver §4).

## 2. Resultados de la versión fiel al video (DLL $1,000, FVG bajo mínimo / sobre máximo, objetivo = swing)

| | NQ M30 (60 d) | NQ H1 (2 a) | ES M30 (60 d) | ES H1 (2 a) |
|---|---|---|---|---|
| Trades | 8 | 52 | 4 | 53 |
| % ganadores | 25 % | 19 % | 100 % | 32 % |
| Neto (USD) | +3,295 | **−3,885** | +4,655 | **−10,915** |
| Profit factor | 1.54 | 0.90 | ∞ | 0.67 |
| Ganancia media / pérdida media | +4,678 / −1,010 | +3,700 / −973 | +1,164 / — | +1,319 / −926 |
| Máx. drawdown | −5,050 | −23,560 | 0 | −16,818 |
| Días que tocaron el límite de pérdida | 6 de 8 | 40 de 52 | 0 | 32 de 53 |
| Evaluación Apex 50K: pasa / quema | — | **4 % / 94 %** | — | **13 % / 87 %** |

**Con 1 promediada:** NQ H1 −$10,450 y ES H1 −$13,810. La promediada **empeora** el resultado en la muestra larga:
como el límite de pérdida está fijo en dólares, duplicar el tamaño hace que el corte llegue antes.

El perfil es siempre el mismo: muchos días se van al límite de pérdida y unos pocos días grandes al objetivo.
En NQ, una pérdida de $1,000 son solo **50 pts**, cuando el rango medio de una vela M30 llega a ~237 pts en el día.
Con ese límite, el ruido normal del mercado alcanza el corte antes que la tesis.

Gráficos: `results/NQ_equity_H1.png`, `results/ES_equity_H1.png`, `results/*_equity_M30.png`.
Todos los trades están en `results/*_trades_*.csv`.

## 3. Robustez: barrido de 96 combinaciones + walk-forward

Variables barridas: modo FVG (`below_pivot` / `any` / `none` = control sin imbalance), entrada (borde / 50 %),
objetivo (swing / fijo), DLL ($500 / $1,000 / $1,500 / $2,500) y promediada (0 / 1).

| H1, 2 años | NQ: % combinaciones rentables | NQ: neto mediano | ES: % rentables | ES: neto mediano |
|---|---|---|---|---|
| FVG bajo mínimo / sobre máximo (fiel) | 31 % | −$6,098 | 9 % | −$8,878 |
| Cualquier FVG a favor de tendencia | 0 % | −$62,530 | 0 % | −$58,117 |
| **Control sin FVG** (entrar a mercado en tendencia) | 0 % | −$219,405 | 0 % | −$145,727 |

- **El imbalance sí filtra:** entrar sin él es entre 3 y 35 veces peor. Y la versión "bajo mínimos / sobre máximos"
  es claramente mejor que "cualquier FVG". Esto coincide con lo que dice Gerard: operar **después** de máximos y mínimos relevantes.
- **Un DLL más ajustado sale menos malo** en H1, porque las pérdidas se cortan antes.
- **Walk-forward** (elegir la mejor combinación en jun-24→ago-25 y probarla en ago-25→nov-26):
  - NQ: la mejor in-sample ganó +$4,825 y en out-of-sample perdió **−$27,870**. 0 % de las combinaciones fueron rentables en ambos periodos.
  - ES: +$1,650 in-sample y **−$29,268** out-of-sample.
- Las mejores combinaciones en H1 completo (por ejemplo NQ `below_pivot|mid|swing|DLL500`, +$9,745, PF 1.49) ganan **solo con los cortos**
  (+$21k cortos / −$11k largos) en un periodo en el que NQ subió de 19,693 a 27,218. Eso apunta a suerte de muestra, no a una ventaja estructural.

## 4. Advertencias importantes

1. **Sesgo intravela.** En la primera versión del backtest, si una vela llenaba la orden y también tocaba el objetivo,
   se contaba como ganador. Con eso, las mismas reglas daban +$105k a +$145k en 2 años, con profit factor de 1.3 a 2.8.
   Esos números eran falsos. Cualquier backtest de esta estrategia hecho a mano con velas M30 o H1 tiene el mismo riesgo.
   **Hay que resolver los fills con datos de 1–5 minutos o tick.**
2. **H1 no es M30.** Con los mismos 60 días, comparé H1 conservador contra H1 con ejecución en 5m. En las variantes de
   objetivo fijo, H1 conservador **subestima** el resultado (NQ +$9.6k frente a +$22.5k). En las variantes de objetivo
   swing, lo **sobreestima** (+$18.7k frente a +$12.8k). La dirección del error depende de la configuración.
3. **La muestra M30 es muy pequeña** (de 1 a 43 trades por combinación). Las configuraciones con DLL $2,500 y promediada
   salen muy bien en M30 (NQ +$18k), pero en H1 de 2 años son de las peores. No hay que fiarse del resultado de 60 días.
4. **Lo que no se puede capturar del video:** el criterio discrecional de Gerard (qué máximo es "relevante", qué tendencia
   es "diagonal" de verdad), noticias, y la gestión manual del trade. El backtest mide la versión **mecánica** de las reglas.
5. **Simulación Apex:** cuenta de 50K, objetivo +$3,000, trailing de $2,500 que se congela en saldo inicial + $100, máximo 30 días.
   Es una aproximación: el trailing se sigue con el PnL cerrado y el peor flotante (MAE) de cada trade.

## 5. Recomendación

- **No operarla en cuentas Apex con estas reglas mecánicas.** En la muestra larga, la probabilidad de quemar la evaluación es de 87–94 %.
- Lo que merece seguir investigando es el **filtro de imbalance bajo mínimos / sobre máximos**, que es lo único con señal.
  Probarlo con un stop por estructura (debajo del FVG o del mínimo barrido) en lugar del corte por flotante, y con objetivos en múltiplos de R.
- Conseguir **M30 + 1m de al menos 2 años** (Databento, FirstRate Data o un export de NinjaTrader/Tradovate) y volver a correr el
  estudio. El código acepta cualquier CSV con `time,open,high,low,close,volume`.

## 6. Cómo reproducir

```bash
pip install pandas numpy matplotlib yfinance
python -m backtest.run --download   # baja datos frescos y corre todo (~8 min)
python -m backtest.run              # usa los CSV de data/
```

Los parámetros están en `backtest/strategy.py::Params`. Los resultados se escriben en `results/`
(`summary.json`, `*_sweep.csv`, `*_walkforward.csv`, `*_trades_*.csv`, `*.png`).
