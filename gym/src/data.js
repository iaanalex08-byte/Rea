// Biblioteca base de ejercicios. muscle: grupo principal (para filtros y la figura).
export const MUSCLES = {
  chest: 'Pecho',
  back: 'Espalda',
  shoulders: 'Hombros',
  biceps: 'Bíceps',
  triceps: 'Tríceps',
  legs: 'Piernas',
  glutes: 'Glúteos',
  core: 'Abdomen',
  cardio: 'Cardio',
};

export const EQUIPMENT = {
  barbell: 'Barra',
  dumbbell: 'Mancuernas',
  machine: 'Máquina',
  cable: 'Polea',
  bodyweight: 'Peso corporal',
  other: 'Otro',
};

const E = (id, name, muscle, equipment) => ({ id, name, muscle, equipment });

export const BASE_EXERCISES = [
  E('bench', 'Press de banca con barra', 'chest', 'barbell'),
  E('incline-db', 'Press inclinado con mancuernas', 'chest', 'dumbbell'),
  E('db-fly', 'Aperturas con mancuernas', 'chest', 'dumbbell'),
  E('cable-cross', 'Cruce de poleas', 'chest', 'cable'),
  E('dips', 'Fondos en paralelas', 'chest', 'bodyweight'),
  E('pushup', 'Lagartijas', 'chest', 'bodyweight'),
  E('deadlift', 'Peso muerto', 'back', 'barbell'),
  E('pullup', 'Dominadas', 'back', 'bodyweight'),
  E('row', 'Remo con barra', 'back', 'barbell'),
  E('db-row', 'Remo con mancuerna', 'back', 'dumbbell'),
  E('lat-pull', 'Jalón al pecho', 'back', 'cable'),
  E('seated-row', 'Remo sentado en polea', 'back', 'cable'),
  E('ohp', 'Press militar', 'shoulders', 'barbell'),
  E('db-shoulder', 'Press de hombro con mancuernas', 'shoulders', 'dumbbell'),
  E('lat-raise', 'Elevaciones laterales', 'shoulders', 'dumbbell'),
  E('face-pull', 'Face pull', 'shoulders', 'cable'),
  E('rear-delt', 'Pájaros (deltoides posterior)', 'shoulders', 'dumbbell'),
  E('curl', 'Curl con barra', 'biceps', 'barbell'),
  E('db-curl', 'Curl con mancuernas', 'biceps', 'dumbbell'),
  E('hammer', 'Curl martillo', 'biceps', 'dumbbell'),
  E('preacher', 'Curl predicador', 'biceps', 'machine'),
  E('pushdown', 'Extensión de tríceps en polea', 'triceps', 'cable'),
  E('skull', 'Press francés', 'triceps', 'barbell'),
  E('oh-ext', 'Extensión sobre la cabeza', 'triceps', 'dumbbell'),
  E('squat', 'Sentadilla con barra', 'legs', 'barbell'),
  E('front-squat', 'Sentadilla frontal', 'legs', 'barbell'),
  E('leg-press', 'Prensa de piernas', 'legs', 'machine'),
  E('lunge', 'Zancadas', 'legs', 'dumbbell'),
  E('leg-ext', 'Extensión de cuádriceps', 'legs', 'machine'),
  E('leg-curl', 'Curl femoral', 'legs', 'machine'),
  E('calf', 'Elevación de talones', 'legs', 'machine'),
  E('rdl', 'Peso muerto rumano', 'glutes', 'barbell'),
  E('hip-thrust', 'Hip thrust', 'glutes', 'barbell'),
  E('bulgarian', 'Sentadilla búlgara', 'glutes', 'dumbbell'),
  E('plank', 'Plancha (segundos)', 'core', 'bodyweight'),
  E('crunch', 'Crunch en polea', 'core', 'cable'),
  E('leg-raise', 'Elevación de piernas colgado', 'core', 'bodyweight'),
  E('run', 'Caminadora (minutos)', 'cardio', 'machine'),
  E('bike', 'Bicicleta (minutos)', 'cardio', 'machine'),
];

const item = (exerciseId, sets, reps, weight) => ({ exerciseId, sets, reps, weight });

// days: 0 = lunes … 6 = domingo
export const BASE_ROUTINES = [
  {
    id: 'push',
    name: 'Día de empuje',
    days: [0, 3],
    items: [
      item('bench', 3, 8, 60),
      item('incline-db', 3, 10, 20),
      item('ohp', 3, 8, 35),
      item('lat-raise', 3, 12, 8),
      item('pushdown', 3, 12, 20),
      item('dips', 3, 10, 0),
    ],
  },
  {
    id: 'pull',
    name: 'Día de jalón',
    days: [1, 4],
    items: [
      item('deadlift', 3, 5, 80),
      item('pullup', 3, 8, 0),
      item('row', 3, 8, 50),
      item('face-pull', 3, 15, 15),
      item('curl', 3, 10, 25),
    ],
  },
  {
    id: 'legs',
    name: 'Día de pierna',
    days: [2, 5],
    items: [
      item('squat', 4, 6, 70),
      item('rdl', 3, 8, 60),
      item('leg-press', 3, 10, 120),
      item('leg-curl', 3, 12, 35),
      item('calf', 4, 12, 60),
    ],
  },
];
