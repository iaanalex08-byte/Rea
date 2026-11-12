# Resultados del backtest (generado por run_backtest.py)

Datos: NSXUSD 1m (HistData), 2025-01-01 → 2026-11-06. Costes: 1.0 pts por operación. Riesgo: 0.5% de 50,000 USD = 250 USD por R.

## Caso base

| Métrica | Valor |
|---|---|
| Operaciones | 10 |
| Tasa de acierto (TP) | 50.0% |
| Esperanza por operación (R) | 0.45 |
| Resultado total (R) | 4.54 |
| Profit factor | 1.86 |
| Drawdown máximo (R) | 2.05 |
| Racha perdedora máxima | 2 |
| Stop medio (puntos) | 27.35 |
| Resultado en USD (250 USD/R) | 1,135 |
| IC 95% de la esperanza (bootstrap) | [-0.45, 1.36] R |
| Prob. bootstrap de esperanza ≤ 0 | 17% |

## Qué pasó cada día

| Resultado del día | Días |
|---|---|
| sin_zonas | 192 |
| no_llego | 191 |
| noticia | 57 |
| sin_sesgo | 12 |
| zona_rota | 12 |
| operacion | 10 |
| stop_fuera_rango | 3 |

## Por año y por lado

|                 |   count |   mean |   sum |
|:----------------|--------:|-------:|------:|
| (2025, 'LONG')  |       6 |   0.95 |  5.71 |
| (2025, 'SHORT') |       2 |  -1.05 | -2.11 |
| (2026, 'SHORT') |       2 |   0.47 |  0.93 |

## Por mes (R)

| month   |   count |   sum |
|:--------|--------:|------:|
| 2025-02 |       1 |  1.98 |
| 2025-04 |       2 |  0.92 |
| 2025-07 |       2 |  0.85 |
| 2025-08 |       1 | -1.06 |
| 2025-10 |       2 |  0.92 |
| 2026-01 |       1 | -1.03 |
| 2026-07 |       1 |  1.97 |

## Simulación de cuenta de fondeo 50K

Objetivo +3.000 USD, pérdida máxima trailing 2.000 USD. Se arranca la evaluación en cada operación de la serie histórica.

| Riesgo por operación | Pasa | Se quema | Sin resolver |
|---|---|---|---|
| 250 USD | 0% | 0% | 100% |
| 500 USD | 0% | 0% | 100% |
| 1000 USD | 20% | 40% | 40% |

## Sensibilidad (cada fila cambia una sola regla)

| variante                                    |   ops | acierto   |   esperanza_R |   total_R |   PF |   maxDD_R |
|:--------------------------------------------|------:|:----------|--------------:|----------:|-----:|----------:|
| Caso base                                   |    10 | 50%       |          0.45 |       4.5 | 1.86 |       2.1 |
| Entrar en todas las zonas (no saltar la 1ª) |    28 | 36%       |          0.12 |       3.3 | 1.18 |       3.5 |
| Saltar solo la 1ª zona                      |    13 | 54%       |          0.58 |       7.5 | 2.19 |       2   |
| Impulso medido con swings H1                |     9 | 11%       |         -0.44 |      -4   | 0.46 |       7.3 |
| Solo FVG (sin envolventes)                  |     9 | 56%       |          0.63 |       5.6 | 2.35 |       2.1 |
| Envolvente = cuerpo completo                |     9 | 56%       |          0.63 |       5.6 | 2.35 |       2.1 |
| Solo zonas H1                               |    11 | 45%       |          0.32 |       3.5 | 1.56 |       2.1 |
| Solo compras                                |     6 | 67%       |          0.95 |       5.7 | 3.71 |       1.1 |
| Sin filtro de noticias                      |    10 | 50%       |          0.45 |       4.5 | 1.86 |       2.1 |
| Ventana 9:30-10:00                          |     4 | 50%       |          0.46 |       1.8 | 1.87 |       1.1 |
| Ventana 9:30-11:00                          |    17 | 41%       |          0.2  |       3.4 | 1.33 |       3.1 |
| Ventana 9:30-11:30                          |    21 | 38%       |          0.23 |       4.8 | 1.38 |       3.1 |
| Ventana 9:30-11:00 + saltar solo la 1ª      |    26 | 50%       |          0.47 |      12.2 | 1.91 |       2.1 |
| RR 1:1.5                                    |    10 | 50%       |          0.2  |       2   | 1.39 |       2.1 |
| RR 1:3                                      |    10 | 50%       |          0.95 |       9.5 | 2.82 |       2.1 |
| Stop máx. 40 pts                            |     8 | 50%       |          0.45 |       3.6 | 1.85 |       1.1 |
| Stop máx. 100 pts                           |    12 | 42%       |          0.21 |       2.5 | 1.35 |       4.1 |
| Sin costes                                  |    10 | 50%       |          0.5  |       5   | 2    |       2   |
| Costes x2 (2 pts)                           |    10 | 50%       |          0.41 |       4.1 | 1.74 |       2.1 |

## Operaciones

| date       | side   | entry_time          |   entry |    stop |      tp |   risk_pts | result   |     R | zone_kind   | zone_tf   |
|:-----------|:-------|:--------------------|--------:|--------:|--------:|-----------:|:---------|------:|:------------|:----------|
| 2025-02-13 | LONG   | 2025-02-13 09:43:00 | 21796.7 | 21747.7 | 21894.7 |      48.99 | TP       |  1.98 | ENG         | H1        |
| 2025-04-15 | SHORT  | 2025-04-15 10:19:00 | 18813.3 | 18833.8 | 18772.3 |      20.5  | SL       | -1.05 | ENG         | H1        |
| 2025-04-29 | LONG   | 2025-04-29 10:20:00 | 19309.9 | 19276.1 | 19377.4 |      33.76 | TP       |  1.97 | FVG         | H1        |
| 2025-07-07 | LONG   | 2025-07-07 10:10:00 | 22753.6 | 22742.3 | 22776   |      11.23 | SL       | -1.09 | ENG         | H1        |
| 2025-07-21 | LONG   | 2025-07-21 10:16:00 | 23078.4 | 23062.4 | 23110.4 |      15.98 | TP       |  1.94 | ENG         | H1        |
| 2025-08-07 | SHORT  | 2025-08-07 09:57:00 | 23485.5 | 23502.9 | 23450.9 |      17.31 | SL       | -1.06 | ENG         | H1        |
| 2025-10-03 | LONG   | 2025-10-03 09:53:00 | 24909.4 | 24894   | 24940.4 |      15.47 | TP       |  1.94 | FVG         | H1        |
| 2025-10-31 | LONG   | 2025-10-31 10:08:00 | 25977.5 | 25926.5 | 26079.7 |      51.09 | SL       | -1.02 | FVG         | H1        |
| 2026-01-12 | SHORT  | 2026-01-12 09:54:00 | 25728.3 | 25758.2 | 25668.6 |      29.86 | SL       | -1.03 | ENG         | H1        |
| 2026-07-15 | SHORT  | 2026-07-15 10:08:00 | 29771   | 29800.3 | 29712.4 |      29.3  | TP       |  1.97 | FVG         | H1        |
