# Proxy de opciones (datos reales para el mapa de gamma y la volatilidad)

La página no puede llevar la clave del proveedor de datos: cualquiera que la abra la vería.
Este proxy es un Cloudflare Worker que guarda la clave, consulta al proveedor y entrega a la
terminal una cadena de opciones compacta, con caché de 20 segundos.

## Opción gratis: Tradier sandbox + Cloudflare Workers

Ninguna de las dos pide tarjeta. Los datos de Tradier sandbox llegan con **15 minutos de retraso**.

### 1. Token de Tradier
1. Crea una cuenta de desarrollador gratuita en <https://developer.tradier.com> (botón *Sign up*).
2. En tu panel, en *API Access*, copia el **Sandbox Access Token**.

### 2. Publicar el Worker (desde el navegador, sin instalar nada)
1. Crea una cuenta gratuita en <https://dash.cloudflare.com>.
2. Ve a **Workers & Pages → Create → Create Worker**, ponle de nombre `orbe-options` y pulsa *Deploy*.
3. Pulsa **Edit code**, borra el ejemplo, pega todo el contenido de `options-proxy.js` y pulsa *Deploy*.
4. En **Settings → Variables and Secrets** agrega:

   | Tipo | Nombre | Valor |
   |---|---|---|
   | Text | `PROVIDER` | `tradier` |
   | Text | `TRADIER_SANDBOX` | `true` |
   | Text | `ALLOWED_ORIGINS` | `https://iaanalex08-byte.github.io` |
   | **Secret** | `TRADIER_TOKEN` | el token del paso 1 |

5. Copia la dirección del Worker (algo como `https://orbe-options.tu-cuenta.workers.dev`) y
   comprueba que `.../health` responde `{"ok":true,"provider":"tradier"}`.

### 3. Conectar la terminal
En `terminal/js/config.js` pon la dirección del Worker:

```js
export const OPTIONS_API = 'https://orbe-options.tu-cuenta.workers.dev';
```

Haz commit en `main`. El mapa de gamma y la volatilidad mostrarán **EN VIVO · Tradier (con retraso de 15 min)**.
Si el proxy falla, la terminal vuelve al simulador y lo dice en el pie de página.

Para probar otra dirección solo en tu navegador, sin tocar el archivo, abre la consola y escribe
`localStorage.setItem('orbe.optionsApi', 'https://...')` (con `''` vuelves a la del archivo).

## Con la línea de comandos (alternativa)

```bash
cd terminal/worker
npx wrangler login
npx wrangler secret put TRADIER_TOKEN      # o POLYGON_KEY
npx wrangler deploy
```

Las variables no secretas están en `wrangler.toml`.

## Otros proveedores

- **Tradier en tiempo real:** con una cuenta de corretaje en Tradier, usa el token de producción
  y `TRADIER_SANDBOX = "false"`.
- **Polygon (Massive):** `PROVIDER = "polygon"`, secreto `POLYGON_KEY`. El plan Options Starter
  tiene 15 min de retraso (`POLYGON_DELAYED = "true"`). Para SPX el proxy usa el ticker `I:SPX`;
  tu plan debe incluir índices.

## Qué cambia con datos reales

- GEX, DEX, muros, gamma flip, mapa de calor y superficie de volatilidad salen del open interest
  y la volatilidad implícita reales de cada contrato.
- El open interest se publica una vez al día (lo calcula la OCC antes de la apertura).
- El flujo se calcula con el volumen operado entre actualizaciones. Sin una fuente de operaciones
  individuales no se sabe si cada operación fue compra o venta, así que la gráfica muestra la
  delta del volumen y no presión compradora o vendedora.
