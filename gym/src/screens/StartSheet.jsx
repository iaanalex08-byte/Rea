import { useStore, routineForDay } from '../store';
import { Sheet, Icon } from '../components/ui';
import { DAY_SHORT } from '../utils';

export default function StartSheet({ open, onClose }) {
  const routines = useStore((s) => s.routines);
  const startWorkout = useStore((s) => s.startWorkout);
  const today = routineForDay(routines, new Date());

  const start = (id) => {
    startWorkout(id);
    onClose();
  };

  return (
    <Sheet open={open} onClose={onClose} title="Empezar entreno">
      <div className="stack">
        {routines.map((r) => (
          <button key={r.id} className={`routine-pick ${today?.id === r.id ? 'today' : ''}`} onClick={() => start(r.id)}>
            <span className="badge-letter">{r.name[0]}</span>
            <span className="grow">
              <b>{r.name}</b>
              <small>
                {r.items.length} ejercicios · {r.days.length ? r.days.map((d) => DAY_SHORT[d]).join(' ') : 'sin día fijo'}
              </small>
            </span>
            {today?.id === r.id && <span className="pill">Hoy</span>}
            <Icon name="play" size={16} fill="currentColor" />
          </button>
        ))}
        <button className="routine-pick ghost" onClick={() => start(null)}>
          <span className="badge-letter">+</span>
          <span className="grow">
            <b>Entreno libre</b>
            <small>Empieza vacío y agrega ejercicios sobre la marcha</small>
          </span>
        </button>
      </div>
    </Sheet>
  );
}
