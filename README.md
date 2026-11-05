# Rea

## Lumen — plataforma de streaming de ejemplo

`lumen/` es una aplicación web de streaming original (sin dependencias ni paso de compilación):

- Página de bienvenida con registro por correo
- Selección de perfiles ("¿Quién está viendo?")
- Portada destacada y filas horizontales por categoría (Tendencias, Series, Animación…)
- Ficha de cada título con episodios, "Mi lista" y reproducción
- Búsqueda por título, género o sinopsis
- Reproductor que recuerda dónde te quedaste ("Seguir viendo"), por perfil
- Diseño adaptable a celular

Los títulos y sinopsis son inventados, el arte de las portadas se genera con CSS y los
videos de muestra son cortometrajes abiertos de la Blender Foundation (licencia CC BY).

### Cómo ejecutarla

```bash
cd lumen
python3 -m http.server 8000
```

Abre http://localhost:8000. Para cambiar el catálogo, edita `lumen/data.js`.
