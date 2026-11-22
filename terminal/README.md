# ORBE Terminal

Terminal de mercado en el navegador, sin build: `index.html` + módulos JavaScript.
Se publica en GitHub Pages en `/terminal/`.

## Herramientas y fuentes de datos

| Pestaña | Qué muestra | Fuente | Tipo |
|---|---|---|---|
| Mapa de gamma | GEX y DEX por strike, call wall, put wall, gamma flip, mapa de calor vencimiento × strike, delta nocional por minuto, flujo inusual | Tradier o Polygon vía proxy; si no, simulador | En vivo (15 min de retraso gratis) o SIM |
| Cripto | Precios y velas en vivo, liquidaciones de futuros, dominancia | Binance (data-api / data-stream, con respaldo Binance.US y Coinbase), Binance Futures y Bybit, CoinGecko | En vivo |
| Forex | Fuerza relativa, matriz de cruces, gráfico de cualquier par | Banco Central Europeo vía Frankfurter | Diario |
| Volatilidad | Superficie de IV en 3D, skew por vencimiento, estructura temporal | Tradier o Polygon vía proxy; si no, simulador | En vivo o SIM |
| Insiders y Congreso | Compras y ventas de directivos (Form 4), compras en grupo, operaciones de legisladores | SEC EDGAR y Quiver Quantitative, vía GitHub Action | Cada 30 min |
| Macro | Curva del Tesoro, diferenciales 10A−2A y 10A−3M, ciclo del G20 | home.treasury.gov, Banco Mundial | Diario / anual |

Cada panel indica con una etiqueta si sus datos son **SIM**, **EN VIVO**, **DIARIO** o **ANUAL**.

## Opciones: simulador o datos reales

Sin configuración, el mapa de gamma y la volatilidad usan un simulador: griegas de Black-Scholes
sobre una cadena sintética, con un precio que se mueve según el régimen de gamma.

Para datos reales, publica el proxy de `terminal/worker/` (Cloudflare Worker, gratis) y pon su
dirección en `terminal/js/config.js`. Funciona gratis con la cuenta de desarrollador de Tradier
(15 min de retraso) y también con Polygon. Pasos en [`worker/README.md`](worker/README.md).

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
