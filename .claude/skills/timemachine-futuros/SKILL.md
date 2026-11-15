---
name: timemachine-futuros
description: >-
  Time Machine para futuros ES/MES y NQ/MNQ, en compra y venta. Antes de entrar en la estrategia de tendencia
  (dirección = movimiento 00:00-8:59 CDMX, entrada a mercado a la hora elegida), simula el resto del día 10,000 veces
  con días pasados parecidos y da la probabilidad de SL, TP1 + BE, TP1 + TP2 o cierre a las 15:00, el R medio y la
  historia real de la misma regla. Lee el día de hoy de Yahoo Finance (--vivo) o un día de los CSV de NinjaTrader.
  Usar cuando el usuario diga "time machine", "simula la de las 9", "qué probabilidad tiene hoy", "corre la de hoy",
  "simula el SP500 / NQ de hoy", o pida las odds de TP1/TP2/SL antes de entrar.
argument-hint: "[ES|NQ] [hora] [sl tp1 tp2 en ticks]"
---

# timemachine-futuros

Script: `backtest/timemachine_futuros.py` (en la raíz del repo). Corre desde la raíz:

```bash
python3 backtest/timemachine_futuros.py --vivo                                  # ES hoy, 9:00, SL 60 / TP1 60 + BE / TP2 120
python3 backtest/timemachine_futuros.py --vivo --hora 9:12 --sl 45 --tp1 30 --tp2 60
python3 backtest/timemachine_futuros.py --inst NQ --vivo --sl 200 --tp1 200 --tp2 400   # NQ: tendencia mínima 70 pts por defecto
python3 backtest/timemachine_futuros.py --fecha 2026-11-04                      # día de los CSV, con lo que pasó de verdad
python3 backtest/timemachine_futuros.py --calibrar 2026                         # pronóstico vs realidad de todo un año
```

Otras opciones: `--tendencia PTS`, `--parcial 0.5`, `--sin-be`, `--contratos 2`, `--direccion compra|venta`,
`--entrada PRECIO`, `--ajustar-vol`, `--bloque 60`, `--replicas 10000`, `--seed 19`, `--json archivo`.

## Cómo explicarlo al usuario (en español, horas CDMX)

1. Dirección, movimiento de la noche y si pasa el filtro de tendencia. Si dice PROVISIONAL, aún no son las 9:00.
2. Niveles: entrada, SL, TP1, TP2 en precio.
3. Las probabilidades, el R medio en R y en USD, y la historia real de la misma regla.
4. El veredicto tal cual, y "lo que pasó de verdad" si el día ya cerró.
5. Siempre decir la limitación medida: en la calibración de 2025 y 2026 el pronóstico casi no cambia de un día a
   otro (SL 43-50 %) y NO separa los días buenos de los malos. Sirve para saber qué esperar de la regla
   (frecuencia de SL, de BE y de TP2, tamaño de las rachas), no como filtro para decidir qué días operar.
6. No es una predicción: noticias (CPI, FOMC, NFP) pueden salirse de todo. Nunca envía órdenes.
