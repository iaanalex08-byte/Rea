# ORBE Terminal

Terminal de mercado en el navegador, sin build: `index.html` + módulos JavaScript.
Se publica en GitHub Pages en `/terminal/`.

## Herramientas y fuentes de datos

| Pestaña | Qué muestra | Fuente | Tipo |
|---|---|---|---|
| Mapa de gamma | GEX y DEX por strike, call wall, put wall, gamma flip, mapa de calor vencimiento × strike, delta nocional por minuto, flujo inusual | Simulador (`js/sim/options.js`) | SIM |
| Cripto | Precios y velas en vivo, liquidaciones de futuros, dominancia | Binance (data-api / data-stream, con respaldo Binance.US y Coinbase), Binance Futures y Bybit, CoinGecko | En vivo |
| Forex | Fuerza relativa, matriz de cruces, gráfico de cualquier par | Banco Central Europeo vía Frankfurter | Diario |
| Volatilidad | Superficie de IV en 3D, skew por vencimiento, estructura temporal | Simulador | SIM |
| Insiders y Congreso | Compras y ventas de directivos (Form 4), compras en grupo, operaciones de legisladores | SEC EDGAR y Quiver Quantitative, vía GitHub Action | Cada 30 min |
| Macro | Curva del Tesoro, diferenciales 10A−2A y 10A−3M, ciclo del G20 | home.treasury.gov, Banco Mundial | Diario / anual |

Cada panel indica con una etiqueta si sus datos son **SIM**, **EN VIVO**, **DIARIO** o **ANUAL**.

## Opciones: por qué está simulado y cómo conectar datos reales

Los datos de opciones en tiempo real (cadena completa con open interest) no tienen fuente gratuita
que se pueda usar desde una página. El simulador calcula griegas con Black-Scholes sobre una cadena
sintética (open interest por strike y vencimiento, superficie de volatilidad) y mueve el precio según
el régimen de gamma: con gamma positiva el precio tiende a quedarse cerca del strike con más gamma,
con gamma negativa los movimientos se amplifican.

Para usar datos reales hay que reemplazar `OptionsSim` por un proveedor (Polygon, ThetaData, Tradier,
CBOE DataShop…) que entregue lo mismo: `spot`, `candles`, `expiries`, `strikes`, `oi[vencimiento][strike]`
e `iv(K, T)`. Los cálculos de exposición (`snapshot`) y todas las vistas funcionan sin cambios.
La clave del proveedor **no** debe ir en el código de la página (sería pública): se necesita un pequeño
servidor o función que la guarde y reenvíe los datos.

## Insiders y Congreso (GitHub Action)

`.github/workflows/terminal-data.yml` corre cada 30 minutos en horario de mercado y ejecuta
`terminal/tools/fetch-insiders.mjs`, que escribe `terminal/data/insiders.json` y `terminal/data/congress.json`.

1. **Insiders (gratis):** en el repositorio, *Settings → Secrets and variables → Actions → Variables*,
   crea `SEC_USER_AGENT` con un nombre y tu correo, por ejemplo `ORBE Terminal tu-correo@dominio.com`.
   La SEC exige que quien descarga se identifique así.
2. **Congreso (opcional, de paga):** en *Secrets*, crea `QUIVER_API_KEY` con tu clave de Quiver Quantitative.
3. Ejecuta la Action una vez a mano desde la pestaña *Actions → Datos de la terminal → Run workflow*.

Mientras no estén configuradas, esas tablas muestran cómo activarlas.

## Verla en tu computadora

Los módulos de JavaScript no cargan abriendo el archivo directamente; hace falta un servidor local:

```bash
cd terminal
python3 -m http.server 8000
# abre http://localhost:8000
```
