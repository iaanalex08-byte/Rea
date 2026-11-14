import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { BASE_EXERCISES, BASE_ROUTINES } from './data';
import { uid, dayKey, addDays, startOfDay, weekday, startOfWeek } from './utils';

const newSet = (w = 0, r = 0) => ({ w, r, done: false });

/* ---------- consultas puras sobre el historial ---------- */

export function lastPerformance(workouts, exerciseId, beforeTs = Infinity) {
  for (let i = workouts.length - 1; i >= 0; i--) {
    const wk = workouts[i];
    if (wk.start >= beforeTs) continue;
    const ex = wk.exercises.find((e) => e.exerciseId === exerciseId);
    if (ex) {
      const sets = ex.sets.filter((s) => s.done);
      if (sets.length) return { date: wk.start, sets, target: ex.target };
    }
  }
  return null;
}

export function bestWeight(workouts, exerciseId) {
  let best = null;
  for (const wk of workouts)
    for (const ex of wk.exercises)
      if (ex.exerciseId === exerciseId)
        for (const s of ex.sets) if (s.done && (best == null || s.w > best)) best = s.w;
  return best;
}

// Estimación de 1RM (Epley)
export const e1rm = (w, r) => (r <= 1 ? w : w * (1 + r / 30));

export function exerciseHistory(workouts, exerciseId) {
  const out = [];
  for (const wk of workouts) {
    const ex = wk.exercises.find((e) => e.exerciseId === exerciseId);
    if (!ex) continue;
    const done = ex.sets.filter((s) => s.done);
    if (!done.length) continue;
    out.push({
      date: wk.start,
      top: Math.max(...done.map((s) => s.w)),
      e1rm: Math.max(...done.map((s) => e1rm(s.w, s.r))),
      volume: done.reduce((a, s) => a + s.w * s.r, 0),
      sets: done,
    });
  }
  return out;
}

// Sugerencia de progresión: si la última vez completó todas las series con las reps objetivo, subir 2.5 kg.
export function suggestion(workouts, exerciseId, targetReps, beforeTs) {
  const last = lastPerformance(workouts, exerciseId, beforeTs);
  if (!last) return null;
  const reps = targetReps || last.target || 0;
  const top = Math.max(...last.sets.map((s) => s.w));
  if (top <= 0) return null;
  const allHit = reps > 0 && last.sets.every((s) => s.r >= reps);
  return allHit ? { kind: 'up', weight: top + 2.5 } : { kind: 'same', weight: top };
}

export function weekStreak(workouts, now = new Date()) {
  if (!workouts.length) return 0;
  const weeks = new Set(workouts.map((w) => dayKey(startOfWeek(w.start))));
  let cur = startOfWeek(now);
  // si esta semana aún no hay entreno, la racha cuenta desde la semana pasada
  if (!weeks.has(dayKey(cur))) cur = addDays(cur, -7);
  let n = 0;
  while (weeks.has(dayKey(cur))) {
    n++;
    cur = addDays(cur, -7);
  }
  return n;
}

export function workoutsThisWeek(workouts, now = new Date()) {
  const s = startOfWeek(now).getTime();
  return workouts.filter((w) => w.start >= s).length;
}

export function routineForDay(routines, date) {
  const wd = weekday(date);
  return routines.find((r) => r.days.includes(wd)) || null;
}

/* ---------- datos de ejemplo ---------- */

function demoData(routines) {
  const workouts = [];
  const weights = [];
  const today = startOfDay(new Date());
  const start = addDays(today, -300);
  const prog = {}; // peso actual por ejercicio
  for (const r of routines) for (const it of r.items) prog[it.exerciseId] = it.weight * 0.8;
  let bw = 81.5;
  for (let d = new Date(start); d < today; d = addDays(d, 1)) {
    const r = routineForDay(routines, d);
    bw += (Math.random() - 0.56) * 0.35;
    if (Math.random() < 0.55) weights.push({ date: dayKey(d), kg: Math.round(bw * 10) / 10 });
    if (!r || Math.random() < 0.3) continue;
    const t0 = new Date(d);
    t0.setHours(7 + Math.floor(Math.random() * 12), Math.floor(Math.random() * 60));
    const exercises = r.items.map((it) => {
      const w = Math.round(prog[it.exerciseId] / 2.5) * 2.5;
      const sets = Array.from({ length: it.sets }, (_, i) => {
        const miss = Math.random() < 0.12 * (i + 1);
        return { w, r: miss ? Math.max(1, it.reps - 1 - Math.floor(Math.random() * 2)) : it.reps, done: true };
      });
      if (sets.every((s) => s.r >= it.reps) && it.weight > 0) prog[it.exerciseId] += 1.25;
      return { exerciseId: it.exerciseId, target: it.reps, sets };
    });
    const mins = 40 + Math.floor(Math.random() * 45);
    workouts.push({
      id: uid(),
      routineId: r.id,
      name: r.name,
      start: t0.getTime(),
      end: t0.getTime() + mins * 60000,
      exercises,
    });
  }
  return { workouts, weights };
}

/* ---------- store ---------- */

export const useStore = create(
  persist(
    (set, get) => ({
      exercises: BASE_EXERCISES,
      routines: BASE_ROUTINES,
      workouts: [],
      weights: [],
      goalWeight: null,
      weeklyGoal: 4,
      restSeconds: 90,
      active: null,

      /* rutinas */
      saveRoutine: (routine) =>
        set((s) => {
          const exists = s.routines.some((r) => r.id === routine.id);
          return {
            routines: exists
              ? s.routines.map((r) => (r.id === routine.id ? routine : r))
              : [...s.routines, { ...routine, id: routine.id || uid() }],
          };
        }),
      deleteRoutine: (id) => set((s) => ({ routines: s.routines.filter((r) => r.id !== id) })),

      /* ejercicios */
      addExercise: (ex) => {
        const e = { ...ex, id: uid(), custom: true };
        set((s) => ({ exercises: [...s.exercises, e] }));
        return e.id;
      },
      deleteExercise: (id) => set((s) => ({ exercises: s.exercises.filter((e) => e.id !== id) })),

      /* peso corporal */
      logWeight: (kg, date = new Date()) =>
        set((s) => {
          const k = dayKey(date);
          const rest = s.weights.filter((w) => w.date !== k);
          return { weights: [...rest, { date: k, kg }].sort((a, b) => (a.date < b.date ? -1 : 1)) };
        }),
      deleteWeight: (date) => set((s) => ({ weights: s.weights.filter((w) => w.date !== date) })),
      setGoalWeight: (kg) => set({ goalWeight: kg }),
      setWeeklyGoal: (n) => set({ weeklyGoal: n }),
      setRestSeconds: (n) => set({ restSeconds: n }),

      /* entrenamiento activo */
      startWorkout: (routineId) => {
        const s = get();
        if (s.active) return;
        const r = s.routines.find((x) => x.id === routineId);
        const exercises = (r ? r.items : []).map((it) => {
          const last = lastPerformance(s.workouts, it.exerciseId);
          const sets = Array.from({ length: it.sets }, (_, i) => {
            const prev = last?.sets[i] || last?.sets[last.sets.length - 1];
            return newSet(prev ? prev.w : it.weight, it.reps);
          });
          return { exerciseId: it.exerciseId, target: it.reps, sets };
        });
        set({
          active: {
            id: uid(),
            routineId: r ? r.id : null,
            name: r ? r.name : 'Entreno libre',
            start: Date.now(),
            pausedAt: null,
            pausedTotal: 0,
            idx: 0,
            restUntil: null,
            minimized: false,
            exercises,
          },
        });
      },
      patchActive: (patch) => set((s) => (s.active ? { active: { ...s.active, ...patch } } : {})),
      updateSet: (ei, si, patch) =>
        set((s) => {
          if (!s.active) return {};
          const exercises = s.active.exercises.map((ex, i) =>
            i !== ei ? ex : { ...ex, sets: ex.sets.map((st, j) => (j !== si ? st : { ...st, ...patch })) }
          );
          return { active: { ...s.active, exercises } };
        }),
      toggleSet: (ei, si) => {
        const s = get();
        if (!s.active) return;
        const st = s.active.exercises[ei].sets[si];
        const done = !st.done;
        get().updateSet(ei, si, { done });
        if (done) get().patchActive({ restUntil: Date.now() + s.restSeconds * 1000 });
      },
      addSet: (ei) =>
        set((s) => {
          if (!s.active) return {};
          const exercises = s.active.exercises.map((ex, i) => {
            if (i !== ei) return ex;
            const last = ex.sets[ex.sets.length - 1];
            return { ...ex, sets: [...ex.sets, newSet(last?.w ?? 0, last?.r ?? ex.target ?? 8)] };
          });
          return { active: { ...s.active, exercises } };
        }),
      removeSet: (ei, si) =>
        set((s) => {
          if (!s.active) return {};
          const exercises = s.active.exercises.map((ex, i) =>
            i !== ei ? ex : { ...ex, sets: ex.sets.filter((_, j) => j !== si) }
          );
          return { active: { ...s.active, exercises } };
        }),
      addExerciseToActive: (exerciseId) =>
        set((s) => {
          if (!s.active) return {};
          const last = lastPerformance(s.workouts, exerciseId);
          const sets = last
            ? last.sets.map((x) => newSet(x.w, x.r))
            : [newSet(0, 10), newSet(0, 10), newSet(0, 10)];
          const exercises = [...s.active.exercises, { exerciseId, target: sets[0].r, sets }];
          return { active: { ...s.active, exercises, idx: exercises.length - 1 } };
        }),
      removeExerciseFromActive: (ei) =>
        set((s) => {
          if (!s.active) return {};
          const exercises = s.active.exercises.filter((_, i) => i !== ei);
          return {
            active: { ...s.active, exercises, idx: Math.max(0, Math.min(s.active.idx, exercises.length - 1)) },
          };
        }),
      togglePause: () =>
        set((s) => {
          const a = s.active;
          if (!a) return {};
          if (a.pausedAt) return { active: { ...a, pausedAt: null, pausedTotal: a.pausedTotal + (Date.now() - a.pausedAt) } };
          return { active: { ...a, pausedAt: Date.now() } };
        }),
      finishWorkout: () => {
        const a = get().active;
        if (!a) return null;
        const end = a.pausedAt || Date.now();
        const exercises = a.exercises
          .map((ex) => ({ ...ex, sets: ex.sets.filter((x) => x.done) }))
          .filter((ex) => ex.sets.length);
        if (!exercises.length) {
          set({ active: null });
          return null;
        }
        const wk = {
          id: a.id,
          routineId: a.routineId,
          name: a.name,
          start: a.start,
          end: end - a.pausedTotal,
          exercises,
        };
        set((s) => ({ workouts: [...s.workouts, wk].sort((x, y) => x.start - y.start), active: null }));
        return wk;
      },
      discardWorkout: () => set({ active: null }),
      deleteWorkout: (id) => set((s) => ({ workouts: s.workouts.filter((w) => w.id !== id) })),

      /* datos */
      loadDemo: () => set((s) => ({ ...demoData(s.routines), goalWeight: 74 })),
      importData: (data) =>
        set(() => {
          const keys = ['exercises', 'routines', 'workouts', 'weights', 'goalWeight', 'weeklyGoal', 'restSeconds'];
          const out = {};
          for (const k of keys) if (k in data) out[k] = data[k];
          return out;
        }),
      resetAll: () =>
        set({
          exercises: BASE_EXERCISES,
          routines: BASE_ROUTINES,
          workouts: [],
          weights: [],
          goalWeight: null,
          weeklyGoal: 4,
          restSeconds: 90,
          active: null,
        }),
    }),
    { name: 'gym-data', version: 1 }
  )
);

export const useExerciseMap = () => {
  const exercises = useStore((s) => s.exercises);
  return Object.fromEntries(exercises.map((e) => [e.id, e]));
};
