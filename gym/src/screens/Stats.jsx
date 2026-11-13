import { useMemo, useState } from 'react';
import { useStore, weekStreak, exerciseHistory } from '../store';
import { Icon, Segmented, Sheet } from '../components/ui';
import { LineChart, Heatmap } from '../components/charts';
import { WeightSheet } from './Home';
import { fromKey, fmtNum, longDate, startOfDay } from '../utils';

const RANGES = [
  { value: 30, label: '1M' },
  { value: 90, label: '3M' },
  { value: 365, label: '1A' },
  { value: 0, label: 'Todo' },
];

export default function Stats() {
  const workouts = useStore((s) => s.workouts);
  const weights = useStore((s) => s.weights);
  const goalWeight = useStore((s) => s.goalWeight);
  const exercises = useStore((s) => s.exercises);
  const deleteWorkout = useStore((s) => s.deleteWorkout);
  const [range, setRange] = useState(90);
  const [logOpen, setLogOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const exMap = Object.fromEntries(exercises.map((e) => [e.id, e]));

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).getTime();
  const thisMonth = workouts.filter((w) => w.start >= monthStart).length;
  const streak = weekStreak(workouts);

  const weight30 = useMemo(() => {
    if (!weights.length) return null;
    const last = weights[weights.length - 1];
    const cutoff = startOfDay(now).getTime() - 30 * 86400000;
    const base = weights.find((w) => fromKey(w.date).getTime() >= cutoff);
    return base && base !== last ? last.kg - base.kg : null;
  }, [weights]);

  const pts = useMemo(() => {
    const cutoff = range ? Date.now() - range * 86400000 : 0;
    return weights.map((w) => ({ t: fromKey(w.date).getTime(), v: w.kg })).filter((p) => p.t >= cutoff);
  }, [weights, range]);

  const totalMins = workouts.reduce((a, w) => a + (w.end - w.start) / 60000, 0);
  const totalVolume = workouts.reduce(
    (a, w) => a + w.exercises.reduce((b, e) => b + e.sets.reduce((c, s) => c + s.w * s.r, 0), 0),
    0
  );

  // ejercicios más usados para progreso de fuerza
  const topExercises = useMemo(() => {
    const count = {};
    for (const w of workouts) for (const e of w.exercises) count[e.exerciseId] = (count[e.exerciseId] || 0) + 1;
    return Object.entries(count)
      .sort((a, b) => b[1] - a[1])
      .map(([id]) => id)
      .filter((id) => exMap[id])
      .slice(0, 8);
  }, [workouts, exercises]);
  const [exSel, setExSel] = useState(null);
  const exId = exSel && topExercises.includes(exSel) ? exSel : topExercises[0];
  const exHist = useMemo(() => (exId ? exerciseHistory(workouts, exId) : []), [workouts, exId]);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Stats</h1>
          <p className="muted">Progreso e historial</p>
        </div>
        <button className="icon-btn round" onClick={() => setHistoryOpen(true)} aria-label="Historial de entrenos">
          <Icon name="history" size={18} />
        </button>
      </header>

      <div className="stat-grid">
        <div className="stat">
          <small>
            <Icon name="stats" size={12} /> Entrenos
          </small>
          <b>{workouts.length}</b>
        </div>
        <div className="stat">
          <small>
            <Icon name="calendar" size={12} /> Este mes
          </small>
          <b>{thisMonth}</b>
        </div>
        <div className="stat">
          <small>
            <Icon name="flame" size={12} /> Racha (semanas)
          </small>
          <b>{streak}</b>
        </div>
        <div className="stat">
          <small>
            <Icon name="scale" size={12} /> Peso 30 días
          </small>
          <b className={weight30 == null ? '' : weight30 <= 0 ? 'accent-text' : 'warn-text'}>
            {weight30 == null ? '—' : `${weight30 > 0 ? '+' : ''}${fmtNum(weight30)} kg`}
          </b>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <span className="muted small">Actividad — últimos 12 meses · por tiempo entrenado</span>
        </div>
        <Heatmap workouts={workouts} />
        <p className="muted small">
          {Math.round(totalMins / 60)} h entrenadas · {fmtNum(totalVolume / 1000, 1)} t levantadas
        </p>
      </section>

      <section className="card">
        <div className="card-head">
          <span className="muted small">Peso corporal</span>
          <span className="row gap">
            {goalWeight != null && (
              <span className="goal-chip">
                <i /> {fmtNum(goalWeight)}
              </span>
            )}
            <button className="link" onClick={() => setLogOpen(true)}>
              + Registrar
            </button>
          </span>
        </div>
        <Segmented options={RANGES} value={range} onChange={setRange} />
        <LineChart points={pts} goal={goalWeight} height={150} />
      </section>

      <section className="card">
        <div className="card-head">
          <span className="muted small">Fuerza — peso máximo por sesión</span>
        </div>
        {topExercises.length ? (
          <>
            <select className="select" value={exId} onChange={(e) => setExSel(e.target.value)}>
              {topExercises.map((id) => (
                <option key={id} value={id}>
                  {exMap[id].name}
                </option>
              ))}
            </select>
            <LineChart points={exHist.map((h) => ({ t: h.date, v: h.top }))} height={140} color="var(--blue)" />
            {exHist.length > 0 && (
              <p className="muted small">
                Récord {fmtNum(Math.max(...exHist.map((h) => h.top)))} kg · 1RM estimado{' '}
                {fmtNum(Math.max(...exHist.map((h) => h.e1rm)))} kg · {exHist.length} sesiones
              </p>
            )}
          </>
        ) : (
          <div className="empty">
            <p>Termina tu primer entreno para ver tu progreso de fuerza.</p>
          </div>
        )}
      </section>

      <WeightSheet open={logOpen} onClose={() => setLogOpen(false)} />

      <Sheet open={historyOpen} onClose={() => setHistoryOpen(false)} title="Historial">
        {workouts.length === 0 && <p className="muted">Aún no hay entrenos.</p>}
        <ul className="history">
          {[...workouts]
            .reverse()
            .slice(0, 100)
            .map((w) => (
              <li key={w.id}>
                <div className="row gap">
                  <span className="grow">
                    <b>{w.name}</b>
                    <small className="muted block">
                      {longDate(w.start)} · {Math.round((w.end - w.start) / 60000)} min
                    </small>
                  </span>
                  <button
                    className="icon-btn"
                    aria-label="Borrar entreno"
                    onClick={() => confirm('¿Borrar este entreno del historial?') && deleteWorkout(w.id)}
                  >
                    <Icon name="trash" size={14} />
                  </button>
                </div>
                <ul className="history-ex">
                  {w.exercises.map((e, i) => (
                    <li key={i}>
                      <span className="grow">{exMap[e.exerciseId]?.name || 'Ejercicio borrado'}</span>
                      <span className="muted small">{e.sets.map((s) => `${fmtNum(s.w)}×${s.r}`).join(', ')}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
        </ul>
      </Sheet>
    </>
  );
}
