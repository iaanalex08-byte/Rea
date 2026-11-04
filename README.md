# Fischer Investments — Landing editorial

Sitio web estático (HTML + CSS + JS, sin dependencias) basado en el diseño editorial "Fischer N.º 01 · Octubre 2026".

## Ver el sitio
Abre `index.html` en el navegador, o sirve la carpeta:

    python3 -m http.server 8000

## Efectos incluidos
- Fondo animado tipo "plano arquitectónico" en la portada (canvas, reacciona al cursor).
- Líneas ascendentes animadas en la sección *Largo Plazo*.
- Título FISCHER con entrada letra por letra y torre que se eleva con parallax.
- Cinta (marquee) Estrategia · Disciplina · Paciencia · Largo plazo.
- Revelado de secciones al hacer scroll, imágenes con máscara e inclinación 3D.
- Contadores animados, cursor personalizado, botón magnético, barra de progreso.
- Menú móvil, diseño responsive y soporte para `prefers-reduced-motion`.

## Imágenes
Las ilustraciones están en `assets/` (`tower.svg`, `city.svg`, `lookup.svg`).
Para usar fotografías reales, reemplaza los `src` en `index.html` por tus archivos (p. ej. `assets/city.jpg`).
