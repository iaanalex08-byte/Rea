export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

const pad = (n) => String(n).padStart(2, '0');
export const dayKey = (d) => {
  const x = new Date(d);
  return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`;
};
export const fromKey = (k) => {
  const [y, m, d] = k.split('-').map(Number);
  return new Date(y, m - 1, d);
};
export const startOfDay = (d) => {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
};
export const addDays = (d, n) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};
// Lunes = 0 … domingo = 6
export const weekday = (d) => (new Date(d).getDay() + 6) % 7;
export const startOfWeek = (d) => addDays(startOfDay(d), -weekday(d));

export const DAY_SHORT = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA', 'DO'];
export const DAY_LONG = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
export const MONTH_SHORT = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
export const MONTH_LONG = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

export const longDate = (d) => {
  const x = new Date(d);
  const s = `${DAY_LONG[weekday(x)]} ${x.getDate()} de ${MONTH_LONG[x.getMonth()]}`;
  return s[0].toUpperCase() + s.slice(1);
};
export const shortDate = (d) => {
  const x = new Date(d);
  return `${x.getDate()} ${MONTH_SHORT[x.getMonth()]}`;
};

export const fmtClock = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
};

export const fmtNum = (n, digits = 1) => {
  if (n == null || Number.isNaN(n)) return '—';
  const r = Math.round(n * 10 ** digits) / 10 ** digits;
  return String(r);
};

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
