# Gym

App para planear rutinas, registrar entrenamientos y seguir tu progreso y peso corporal. Hecha con React 19, Vite y Zustand; se instala como PWA en el teléfono y funciona sin conexión.

## Qué hace

- **Inicio**: semana con días entrenados y planeados, la rutina de hoy con botón para empezar, peso corporal con meta y gráfica de 90 días, racha de semanas y meta semanal.
- **Entreno**: series con peso y reps, palomita por serie, descanso automático (vibra al terminar), cronómetro con pausa, "última vez", récord y sugerencia de +2.5 kg si completaste todas las reps. Puedes minimizarlo y volver con el botón central.
- **Plan**: rutinas por día de la semana; crea, edita, reordena ejercicios y fija series, reps y peso inicial.
- **Stats**: totales, mapa de actividad de 12 meses, peso corporal (1M/3M/1A/Todo), progreso de fuerza por ejercicio con 1RM estimado e historial.
- **Ejercicios**: biblioteca de 39 ejercicios por músculo, ejercicios propios y la historia de cada uno.
- **Datos**: todo se guarda en el dispositivo; exporta o importa un respaldo JSON en Ajustes (engrane en Inicio).

## Uso local

```bash
cd gym
npm install
npm run dev      # http://localhost:5173
npm run build    # genera dist/
```

En GitHub Pages queda en `https://<usuario>.github.io/<repositorio>/gym/` (el flujo `.github/workflows/pages.yml` la compila).
