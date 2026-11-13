import { useMemo, useState } from 'react';
import { useStore, routineForDay, weekStreak, workoutsThisWeek } from '../store';
import { Icon, Sheet } from '../components/ui';
import { LineChart } from '../components/charts';
import Settings from './Settings';
import { DAY_SHORT, addDays, dayKey, fromKey, longDate, startOfWeek, fmtNum, shortDate } from '../utils';

export default function Home({ go, openStart }) {
  const routines = useStore((s) => s.routines);
  const workouts = useStore((s) => s.workouts);
  const weights = useStore((s) => s.weights);
  const goalWeight = useStore((s) => s.goalWeight);
  const weeklyGoal = useStore((s) => s.weeklyGoal);
  const active = useStore((s) => s.active);
  const startWorkout = useStore((s) => s.startWorkout);
  const patchActive = useStore((s) => s.patchActive);

  const [weekOffset, setWeekOffset] = useState(0);
  const [selected, setSelected] = useState(dayKey(new Date()));
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const todayKey = dayKey(new Date());
  const weekStart = addDays(startOfWeek(new Date()), weekOffset * 7);
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const trainedDays = useMemo(() => new Set(workouts.map((w) => dayKey(w.start))), [workouts]);

  const selDate = fromKey(selected);
  const selRoutine = routineForDay(routines, selDate);
  const selWorkouts = workouts.filter((w) => dayKey(w.start) === selected);
  const isToday = selected === todayKey;
  const isFuture = selected > todayKey;

  const latest = weights[weights.length - 1];
  const prev = weights[weights.length - 2];
  const delta = latest && prev ? latest.kg - prev.kg : null;
  const chartPts = useMemo(() => {
    const cutoff = Date.now() - 90 * 86400000;
    return weights.map((w) => ({ t: fromKey(w.date).getTime(), v: w.kg })).filter((p) => p.t >= cutoff);
  }, [weights]);

  const streak = weekStreak(workouts);
  const thisWeek = workoutsThisWeek(workouts);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Gym</h1>
          <p className="muted">{longDate(new Date())}</p>
        </div>
        <button className="icon-btn round" onClick={() => setSettingsOpen(true)} aria-label="Ajustes y datos">
          <Icon name="gear" size={18} />
        </button>
      </header>

      {active && (
        <button className="card resume-card" onClick={() => patchActive({ minimized: false })}>
          <span className="live-dot" />
          <span className="grow">
            <b>{active.name}</b>
            <small>Entreno en curso — toca para volver</small>
          </span>
          <Icon name="right" />
        </button>
      )}

      <section className="card">
        <div className="week-head">
          <button className="icon-btn" onClick={() => setWeekOffset(weekOffset - 1)} aria-label="Semana anterior">
            <Icon name="left" size={16} />
          </button>
          <span className="muted small">
            {weekOffset === 0 ? 'Esta semana' : `${shortDate(days[0])} – ${shortDate(days[6])}`}
          </span>
          <button className="icon-btn" onClick={() => setWeekOffset(weekOffset + 1)} aria-label="Semana siguiente">
            <Icon name="right" size={16} />
          </button>
        </div>
        <div className="week">
          {days.map((d, i) => {
            const k = dayKey(d);
            const planned = routineForDay(routines, d);
            return (
              <button key={k} className={`day ${k === selected ? 'sel' : ''} ${k === todayKey ? 'today' : ''}`} onClick={() => setSelected(k)}>
                <span className="dow">{DAY_SHORT[i]}</span>
                <span className="num">{d.getDate()}</span>
                <span className={`dot ${trainedDays.has(k) ? 'done' : planned ? 'planned' : ''}`} />
              </button>
            );
          })}
        </div>

        <div className="today-row">
          {selWorkouts.length > 0 ? (
            selWorkouts.map((w) => (
              <div key={w.id} className="today-item">
                <span className="badge-letter done">
                  <Icon name="check" size={16} stroke={3} />
                </span>
                <span className="grow">
                  <small className="muted">{isToday ? 'HOY' : longDate(selDate).toUpperCase()}</small>
                  <b>{w.name}</b>
                </span>
                <span className="pill">{Math.round((w.end - w.start) / 60000)} min</span>
              </div>
            ))
          ) : selRoutine ? (
            <div className="today-item">
              <span className="badge-letter">{selRoutine.name[0]}</span>
              <span className="grow">
                <small className="muted">{isToday ? 'HOY' : longDate(selDate).toUpperCase()}</small>
                <b>{selRoutine.name}</b>
              </span>
              {isToday && !active && (
                <button className="btn sm" onClick={() => startWorkout(selRoutine.id)}>
                  Empezar
                </button>
              )}
              {!isToday && !isFuture && <span className="pill muted">No entrenado</span>}
            </div>
          ) : (
            <div className="today-item">
              <span className="badge-letter ghost">–</span>
              <span className="grow">
                <small className="muted">{isToday ? 'HOY' : longDate(selDate).toUpperCase()}</small>
                <b>Descanso</b>
              </span>
              {isToday && !active && (
                <button className="btn sm ghost" onClick={openStart}>
                  Entrenar igual
                </button>
              )}
            </div>
          )}
        </div>
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
        {latest ? (
          <>
            <div className="big-number">
              {fmtNum(latest.kg)} <small>kg</small>
              {delta != null && (
                <span className={`delta ${Math.abs(delta) < 0.05 ? 'flat' : delta < 0 ? 'down' : 'up'}`}>
                  {Math.abs(delta) < 0.05 ? '= igual' : `${delta > 0 ? '↑' : '↓'} ${fmtNum(Math.abs(delta))}`}
                </span>
              )}
              <span className="muted small right">{shortDate(fromKey(latest.date))}</span>
            </div>
            {goalWeight != null && (
              <p className="goal-note">
                <i /> Meta {fmtNum(goalWeight)} kg ·{' '}
                {Math.abs(latest.kg - goalWeight) < 0.05
                  ? '¡meta alcanzada!'
                  : `${fmtNum(Math.abs(latest.kg - goalWeight))} kg por ${latest.kg > goalWeight ? 'bajar' : 'subir'}`}
              </p>
            )}
            <LineChart points={chartPts} goal={goalWeight} height={120} />
          </>
        ) : (
          <div className="empty">
            <p>Registra tu peso para ver la tendencia.</p>
            <button className="btn sm" onClick={() => setLogOpen(true)}>
              Registrar peso
            </button>
          </div>
        )}
      </section>

      <button className="card streak-card" onClick={() => go('stats')}>
        <span className="grow">
          <b>
            <Icon name="flame" size={18} className="flame" /> {streak} {streak === 1 ? 'semana' : 'semanas'} de racha
          </b>
          <small className="muted">
            {thisWeek} / {weeklyGoal} esta semana · {workouts.length} entrenos en total
          </small>
          <span className="goal-bar">
            <i style={{ width: `${Math.min(100, (thisWeek / weeklyGoal) * 100)}%` }} />
          </span>
        </span>
        <Icon name="calendar" size={18} />
      </button>

      {workouts.length === 0 && weights.length === 0 && (
        <section className="card hint">
          <p>
            <b>¿Primera vez?</b> Toca <b>Empezar</b> para tu primer entreno, o carga datos de ejemplo para ver
            cómo se ven las gráficas.
          </p>
          <button className="btn sm ghost" onClick={() => useStore.getState().loadDemo()}>
            Cargar datos de ejemplo
          </button>
        </section>
      )}

      <WeightSheet open={logOpen} onClose={() => setLogOpen(false)} />
      <Settings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}

export function WeightSheet({ open, onClose }) {
  const weights = useStore((s) => s.weights);
  const goalWeight = useStore((s) => s.goalWeight);
  const logWeight = useStore((s) => s.logWeight);
  const deleteWeight = useStore((s) => s.deleteWeight);
  const setGoalWeight = useStore((s) => s.setGoalWeight);
  const last = weights[weights.length - 1];
  const [kg, setKg] = useState('');
  const [date, setDate] = useState(dayKey(new Date()));
  const [goal, setGoal] = useState('');

  const save = () => {
    const n = parseFloat(String(kg || last?.kg || '').replace(',', '.'));
    if (Number.isFinite(n) && n > 20 && n < 400) logWeight(Math.round(n * 10) / 10, fromKey(date));
    const g = parseFloat(String(goal).replace(',', '.'));
    if (goal !== '' && Number.isFinite(g)) setGoalWeight(g);
    setKg('');
    setGoal('');
    onClose();
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Peso corporal"
      footer={
        <button className="btn block" onClick={save}>
          Guardar
        </button>
      }
    >
      <div className="form">
        <label>
          Peso (kg)
          <input inputMode="decimal" placeholder={last ? String(last.kg) : '75.0'} value={kg} onChange={(e) => setKg(e.target.value)} autoFocus />
        </label>
        <label>
          Fecha
          <input type="date" value={date} max={dayKey(new Date())} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          Meta (kg)
          <input inputMode="decimal" placeholder={goalWeight != null ? String(goalWeight) : 'opcional'} value={goal} onChange={(e) => setGoal(e.target.value)} />
        </label>
      </div>
      {weights.length > 0 && (
        <>
          <h3 className="sub">Registros recientes</h3>
          <ul className="plain-list">
            {weights
              .slice(-10)
              .reverse()
              .map((w) => (
                <li key={w.date}>
                  <span className="grow">{longDate(fromKey(w.date))}</span>
                  <b>{fmtNum(w.kg)} kg</b>
                  <button className="icon-btn" onClick={() => deleteWeight(w.date)} aria-label="Borrar registro">
                    <Icon name="trash" size={16} />
                  </button>
                </li>
              ))}
          </ul>
        </>
      )}
    </Sheet>
  );
}
