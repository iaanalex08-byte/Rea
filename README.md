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
