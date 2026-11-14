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

## App Gym

En `gym/`: app de rutinas, entrenamientos y peso corporal (React + Vite + Zustand, PWA). Se publica en `/gym/`. Ver `gym/README.md`.
