// All user data lives in this browser (localStorage). Nothing is sent anywhere.

const KEY = 'orbe.calorias.v1';
const empty = () => ({ version: 1, profile: null, customGoals: null, days: {}, weights: [], recents: [], favorites: [], custom: [] });

let state = empty();
export let storageOk = true;
try {
  const raw = localStorage.getItem(KEY);
  if (raw) state = { ...empty(), ...JSON.parse(raw) };
} catch { storageOk = false; }

const listeners = new Set();
export const onChange = (f) => listeners.add(f);

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); storageOk = true; } catch { storageOk = false; }
  listeners.forEach((f) => f());
}

export const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
export const dateKey = (d = new Date()) => d.toLocaleDateString('en-CA'); // YYYY-MM-DD, local time
export const shiftDate = (key, n) => { const d = new Date(key + 'T12:00:00'); d.setDate(d.getDate() + n); return dateKey(d); };

export const MEALS = [
  ['desayuno', 'Desayuno'],
  ['comida', 'Comida'],
  ['cena', 'Cena'],
  ['snacks', 'Snacks'],
];

// ---------- nutrition math ----------
export const scale = (food, grams) => ({
  kcal: (food.kcal * grams) / 100,
  p: (food.p * grams) / 100,
  c: (food.c * grams) / 100,
  f: (food.f * grams) / 100,
});
export function totals(entries) {
  const t = { kcal: 0, p: 0, c: 0, f: 0 };
  for (const e of entries) { const s = scale(e.food, e.grams); t.kcal += s.kcal; t.p += s.p; t.c += s.c; t.f += s.f; }
  return t;
}

export const ACTIVITY = [
  [1.2, 'Sedentario', 'Trabajo de escritorio, casi sin ejercicio'],
  [1.375, 'Ligero', 'Ejercicio 1 a 3 días por semana'],
  [1.55, 'Moderado', 'Ejercicio 3 a 5 días por semana'],
  [1.725, 'Activo', 'Ejercicio intenso 6 a 7 días'],
  [1.9, 'Muy activo', 'Trabajo físico o doble entrenamiento'],
];
export const GOALS = [
  [-550, 'Bajar 0.5 kg por semana'],
  [-275, 'Bajar 0.25 kg por semana'],
  [0, 'Mantener mi peso'],
  [275, 'Subir 0.25 kg por semana'],
];

// Mifflin–St Jeor resting energy × activity, plus the weekly-goal adjustment.
export function computeGoals(p) {
  if (!p) return null;
  const bmr = 10 * p.weight + 6.25 * p.height - 5 * p.age + (p.sex === 'h' ? 5 : -161);
  const tdee = bmr * p.activity;
  const floor = p.sex === 'h' ? 1500 : 1200;
  let kcal = Math.round((tdee + p.goal) / 10) * 10;
  const floored = kcal < floor;
  if (floored) kcal = floor;
  const protein = Math.round(p.weight * (p.goal !== 0 ? 1.8 : 1.6));
  const fat = Math.round((kcal * 0.27) / 9);
  const carbs = Math.max(50, Math.round((kcal - protein * 4 - fat * 9) / 4));
  return { kcal, p: protein, c: carbs, f: fat, bmr: Math.round(bmr), tdee: Math.round(tdee), floored, water: Math.round((p.weight * 35) / 250) * 250 };
}

export function goals() {
  const g = computeGoals(state.profile);
  if (!g) return null;
  return state.customGoals ? { ...g, ...state.customGoals, custom: true } : g;
}

// ---------- accessors / mutations ----------
export const get = () => state;
export function day(key) { return state.days[key] ?? { entries: [], water: 0 }; }
function ensureDay(key) { return (state.days[key] ??= { entries: [], water: 0 }); }

const slim = (f) => ({ id: f.id, src: f.src, name: f.name, brand: f.brand || '', kcal: +f.kcal, p: +f.p || 0, c: +f.c || 0, f: +f.f || 0, serving: f.serving || null, code: f.code || null });

export function addEntry(key, meal, food, grams) {
  ensureDay(key).entries.push({ id: uid(), meal, grams: +grams, food: slim(food), at: Date.now() });
  touchRecent(food);
  save();
}
export function updateEntry(key, id, patch) {
  const e = ensureDay(key).entries.find((x) => x.id === id);
  if (e) Object.assign(e, patch);
  save();
}
export function removeEntry(key, id) {
  const d = ensureDay(key);
  d.entries = d.entries.filter((x) => x.id !== id);
  save();
}
export function copyMeal(fromKey, toKey, meal) {
  const src = day(fromKey).entries.filter((e) => e.meal === meal);
  const d = ensureDay(toKey);
  for (const e of src) d.entries.push({ ...e, id: uid(), at: Date.now() });
  save();
  return src.length;
}
export function addWater(key, ml) {
  const d = ensureDay(key);
  d.water = Math.max(0, (d.water || 0) + ml);
  save();
}

function touchRecent(food) {
  const s = slim(food);
  state.recents = [s, ...state.recents.filter((r) => r.id !== s.id)].slice(0, 40);
}
export const isFav = (food) => state.favorites.some((f) => f.id === food.id);
export function toggleFav(food) {
  if (isFav(food)) state.favorites = state.favorites.filter((f) => f.id !== food.id);
  else state.favorites = [slim(food), ...state.favorites];
  save();
}
export function addCustom(food) {
  const f = { ...food, id: 'c' + uid(), src: food.src || 'custom' };
  state.custom = [slim(f), ...state.custom];
  save();
  return f;
}
export function removeCustom(id) {
  state.custom = state.custom.filter((f) => f.id !== id);
  state.favorites = state.favorites.filter((f) => f.id !== id);
  save();
}

export function setProfile(p) {
  const first = !state.profile;
  state.profile = p;
  // Log the starting weight once so the progress chart has a first point.
  if (first && !state.weights.length) state.weights.push({ date: dateKey(), kg: p.weight });
  save();
}
export function setCustomGoals(g) { state.customGoals = g; save(); }
export function addWeight(date, kg) {
  state.weights = [...state.weights.filter((w) => w.date !== date), { date, kg: +kg }].sort((a, b) => a.date.localeCompare(b.date));
  if (state.profile && date >= (state.weights.at(-1)?.date ?? '')) state.profile = { ...state.profile, weight: +kg };
  save();
}
export function removeWeight(date) { state.weights = state.weights.filter((w) => w.date !== date); save(); }

export function exportData() { return JSON.stringify({ app: 'orbe-calorias', exported: new Date().toISOString(), ...state }, null, 1); }
export function importData(text) {
  const d = JSON.parse(text);
  if (!d || typeof d !== 'object' || !d.days) throw new Error('El archivo no es un respaldo de ORBE Calorías');
  const { app, exported, ...rest } = d;
  state = { ...empty(), ...rest };
  save();
}
export function resetAll() { state = empty(); save(); }
