import { useStore, bestWeight } from '../store';
import { Sheet, Icon } from '../components/ui';
import { fmtNum } from '../utils';

export default function Summary({ workout, onClose }) {
  const workouts = useStore((s) => s.workouts);
  const exercises = useStore((s) => s.exercises);
  if (!workout) return null;
  const exMap = Object.fromEntries(exercises.map((e) => [e.id, e]));
  const before = workouts.filter((w) => w.id !== workout.id && w.start < workout.start);
  const sets = workout.exercises.reduce((a, e) => a + e.sets.length, 0);
  const volume = workout.exercises.reduce((a, e) => a + e.sets.reduce((b, s) => b + s.w * s.r, 0), 0);
  const prs = workout.exercises
    .map((e) => {
      const prev = bestWeight(before, e.exerciseId);
      const top = Math.max(...e.sets.map((s) => s.w));
      return prev != null && top > prev && top > 0 ? { name: exMap[e.exerciseId]?.name, top, prev } : null;
    })
    .filter(Boolean);

  return (
    <Sheet
      open
      onClose={onClose}
      title="¡Entreno guardado!"
      footer={
        <button className="btn block" onClick={onClose}>
          Listo
        </button>
      }
    >
      <div className="stat-grid">
        <div className="stat">
          <small>Duración</small>
          <b>{Math.round((workout.end - workout.start) / 60000)} min</b>
        </div>
        <div className="stat">
          <small>Series</small>
          <b>{sets}</b>
        </div>
        <div className="stat">
          <small>Volumen</small>
          <b>{fmtNum(volume / 1000, 2)} t</b>
        </div>
        <div className="stat">
          <small>Ejercicios</small>
          <b>{workout.exercises.length}</b>
        </div>
      </div>
      {prs.length > 0 && (
        <>
          <h3 className="sub">
            <Icon name="trophy" size={16} /> Nuevos récords
          </h3>
          <ul className="plain-list">
            {prs.map((p) => (
              <li key={p.name}>
                <span className="grow">{p.name}</span>
                <b className="accent-text">{fmtNum(p.top)} kg</b>
                <small className="muted">antes {fmtNum(p.prev)}</small>
              </li>
            ))}
          </ul>
        </>
      )}
    </Sheet>
  );
}
