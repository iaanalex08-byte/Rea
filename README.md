# Standard & Pool's 500

Página web del Modelo B en el futuro ES (SL 45 · TP1 30 · TP2 60, entrada 9:12 CDMX, 2 contratos): backtest real de 476 operaciones (ene 2025 – nov 2026), costos interactivos, rango de esperanza, Monte Carlo y proyección a 3 años en 3D, más un simulador de 45 ticks y la sección "Lab.".

Es un solo archivo, `index.html`, sin build. Para verla en tu computadora basta con abrirlo en el navegador.

## Publicarla en GitHub Pages

1. Une esta rama con `main`.
2. En GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Cada cambio en `main` publica la página con el flujo `.github/workflows/pages.yml`. La dirección queda como `https://<usuario>.github.io/<repositorio>/`.

Si el repositorio es privado, GitHub Pages requiere un plan de pago; con un repositorio público es gratis.

## Datos

`data-modelo-b.json` (la misma data va incrustada en `index.html`): operaciones, rejilla SL × TP1, configuraciones vecinas y riesgo del tablero "ES Modelo B · CDMX 45/30/60" (backtest con velas de 1 minuto SPXUSD de HistData), más velas diarias de ES=F 2026 (Yahoo Finance).

## Indicador y estrategia para TradingView

En `pine/` (Pine Script v6):

- `modelo_b_indicador.pine`: marca la entrada de las 9:12 CDMX, dibuja entrada, stop, TP1 y TP2, mueve el stop a break-even al tocar TP1, cierra a las 15:59 NY, etiqueta el resultado de cada día y lleva una tabla con operaciones, win rate, factor de beneficio, neto y expectativa. Incluye alertas de compra, venta, TP1, TP2, stop, break-even y cierre.
- `modelo_b_estrategia.pine`: la misma lógica como estrategia para el Probador de estrategias, con 2 contratos, 4.50 USD de comisión por contrato y 1 tick de deslizamiento.

Para usarlos: en TradingView abre el Editor de Pine, pega el archivo, guarda y "Añadir al gráfico". Úsalos en ES1! (o el contrato vigente) con velas de 1 minuto.

## Backtest en velas de 3 minutos

En `backtest/`: `engine.py` es el motor del Modelo B y `run.py` lo corre en velas de 1 y 3 minutos y con otras formas de elegir la dirección. Usa las velas de 1 minuto SPXUSD de histdata.com (no se incluyen en el repositorio; `run.py` explica cómo descargarlas). Con velas de 1 minuto reproduce las 476 operaciones del tablero original. `operaciones_1min.csv` y `operaciones_3min.csv` tienen el detalle por día.

## Modelo B + perfil de mercado

`backtest/perfil.py` arma el perfil de cada sesión regular (9:30–16:00 NY) por tiempo (TPO), porque las velas SPXUSD de HistData no traen volumen: POC, VAH, VAL, nodos de alto volumen y la forma del perfil en desarrollo. `backtest/analisis_perfil.py` agrega esos rasgos a cada operación del Modelo B y compara filtros, separando 2025 (para buscar patrones) y 2026 (para comprobarlos):

```
python3 backtest/analisis_perfil.py datos/
```

Resultado con datos hasta el 13 nov 2026 (479 operaciones con perfil del día anterior):

| Filtro | Ops | PF 2025 | PF 2026 | PF total | Neto | DD máx |
|---|---|---|---|---|---|---|
| Sin filtro | 479 | 1.01 | 1.14 | 1.07 | +14,438 | −12,501 |
| A: saltar si la entrada cae dentro del área de valor de ayer | 355 | 1.05 | 1.35 | 1.18 | +25,230 | −10,634 |
| A + C: además saltar si el perfil del día ya es P (compra) o b (venta) | 264 | 1.11 | 1.49 | 1.27 | +27,867 | −8,589 |

El modelo funciona mejor cuando el precio está lejos del valor de ayer, sobre todo si está del lado contrario a la señal (vuelta al valor), y peor dentro del valor (rotación) o persiguiendo un movimiento que ya extendió. La mejora se mantiene con cajas de 0.5, 1 y 2 puntos y con áreas de valor de 60, 70 y 80 %, pero la muestra es chica: una prueba de permutación da p ≈ 0.03–0.06 y los filtros se eligieron mirando los datos, así que hay que seguir validándolos con operaciones nuevas.

### Bracket para EMA + perfil A + C

`backtest/rejilla_filtro.py` prueba SL × TP1 × TP2 (en ticks) sobre los días que pasan los filtros A + C, con la misma lógica que `engine.run` (con 45/30/60 da exactamente lo mismo).

| Bracket | Ops | Ganadoras | PF 2025 | PF 2026 | PF total | Neto | DD máx |
|---|---|---|---|---|---|---|---|
| 45 / 30 / 60 (actual) | 264 | 66.3 % | 1.11 | 1.49 | 1.27 | +27,867 | −8,589 |
| 25 / 30 / 160 | 264 | 55.3 % | 1.47 | 1.65 | 1.55 | +42,519 | −6,360 |
| 25 / 35 / 160 | 264 | 53.0 % | 1.48 | 1.76 | 1.60 | +49,207 | −5,610 |

La zona buena es amplia (SL 20–30, TP1 30–40, TP2 100–200) y también mejora el Modelo B sin filtros de perfil (PF 1.07 → 1.24 con 25/30/160), así que no depende de una sola combinación. Se probaron unas 340 combinaciones: valídalo con operaciones nuevas antes de cambiar el tamaño.

### Qué mejorar (`backtest/mejoras.py`)

Prueba cada idea contra la base (EMA 20 de 3 min + A + C + 45/30/60 a las 9:12 CDMX) y solo la cuenta como mejora si sube el PF en 2025 **y** en 2026: bracket, break-even, hora de entrada, parámetros de la EMA, filtros de rango, distancia a la EMA, apertura, día de la semana y noticias. También mide qué tan sensible es cada versión al minuto exacto de entrada (9:06 a 9:18).

```
python3 backtest/mejoras.py datos/ mejoras.json data-modelo-b.json
```

| Versión | Ops | PF 2025 | PF 2026 | PF total | Neto | DD máx | PF de 9:06 a 9:18 |
|---|---|---|---|---|---|---|---|
| Actual: EMA 20 de 3 min + A + C + 45/30/60 | 264 | 1.11 | 1.49 | 1.27 | +27,867 | −8,589 | 0.87 a 1.27 |
| Propuesta: EMA 20 de 5 min + A + C + 35/30/120 | 264 | 1.44 | 1.65 | 1.53 | +47,155 | −5,340 | 1.07 a 1.53 |

La versión actual solo es buena justo a las 9:12; la propuesta queda arriba de 1 en todos los minutos probados. Filtrar por cercanía a la EMA da PF 2.15, pero solo a las 9:12, así que no se adopta. No ayudan: otra hora de entrada, quitar el break-even, filtrar por día de la semana, por noticias o por rango.

### Prueba fuera de muestra 2023–2024 (`backtest/cuatro_anios.py`)

```
python3 backtest/cuatro_anios.py datos_2023_2025/ datos/ cuatro_anios.json
```

| Versión | PF 2023 | PF 2024 | PF 2025 | PF 2026 | PF 4 años | DD máx |
|---|---|---|---|---|---|---|
| Solo EMA · 45/30/60 | 1.05 | 1.09 | 1.01 | 1.14 | 1.07 | −12,637 |
| Actual · EMA 20 de 3 min + A + C · 45/30/60 | 1.12 | 0.94 | 1.11 | 1.49 | 1.14 | −17,464 |
| **Recomendada · EMA 20 de 3 min + A + C · 35/30/120** | **1.15** | **1.14** | **1.34** | **1.58** | **1.29** | **−8,989** |
| EMA 20 de 5 min + A + C · 35/30/120 | 1.07 | 1.12 | 1.44 | 1.65 | 1.29 | −13,307 |

La recomendada es la única con PF > 1 en los cuatro años y la menor caída; solo cambia el bracket. La EMA de 5 min, el bracket 25/30/160 y el filtro de cercanía a la EMA se ven bien en 2025–2026 pero no se sostienen en 2023–2024.

El indicador `pine/modelo_b_indicador.pine` ya usa 35/30/120 por defecto (antes 45/30/60).
