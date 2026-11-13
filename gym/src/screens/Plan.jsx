import { useState } from 'react';
import { useStore, routineForDay } from '../store';
import { MUSCLES } from '../data';
import { Icon, Sheet, Stepper } from '../components/ui';
import ExercisePicker from '../components/ExercisePicker';
import { DAY_SHORT, DAY_LONG, weekday, uid, fmtNum } from '../utils';

export default function Plan() {
  const routines = useStore((s) => s.routines);
  const exercises = useStore((s) => s.exercises);
  const active = useStore((s) => s.active);
  const startWorkout = useStore((s) => s.startWorkout);
  const [editing, setEditing] = useState(null);
  const exMap = Object.fromEntries(exercises.map((e) => [e.id, e]));
  const todayWd = weekday(new Date());

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Plan</h1>
          <p className="muted">Rutinas y semana</p>
        </div>
        <button className="icon-btn round accent" onClick={() => setEditing({ id: '', name: '', days: [], items: [] })} aria-label="Nueva rutina">
          <Icon name="plus" size={18} />
        </button>
      </header>

      <section className="card">
        <div className="card-head">
          <span className="muted small">Tu semana</span>
        </div>
        <ul className="week-plan">
          {DAY_LONG.map((d, i) => {
            const r = routineForDay(routines, (() => {
              const x = new Date();
              x.setDate(x.getDate() + (i - todayWd));
              return x;
            })());
            return (
              <li key={d} className={i === todayWd ? 'today' : ''}>
                <span className="wp-day">{DAY_SHORT[i]}</span>
                <span className="grow">{r ? r.name : <span className="muted">Descanso</span>}</span>
                {i === todayWd && <span className="pill">Hoy</span>}
              </li>
            );
          })}
        </ul>
      </section>

      {routines.map((r) => {
        const muscles = [...new Set(r.items.map((it) => exMap[it.exerciseId]?.muscle).filter(Boolean))];
        const sets = r.items.reduce((a, it) => a + it.sets, 0);
        return (
          <section key={r.id} className="card routine-card">
            <div className="card-head">
              <span className="row gap">
                <span className="badge-letter">{r.name[0]}</span>
                <span>
                  <b>{r.name}</b>
                  <small className="muted block">
                    {r.items.length} ejercicios · {sets} series · {r.days.length ? r.days.map((d) => DAY_SHORT[d]).join(' ') : 'sin día'}
                  </small>
                </span>
              </span>
              <button className="icon-btn" onClick={() => setEditing(structuredClone(r))} aria-label={`Editar ${r.name}`}>
                <Icon name="edit" size={16} />
              </button>
            </div>
            <div className="tags">
              {muscles.map((m) => (
                <span key={m}>{MUSCLES[m]}</span>
              ))}
            </div>
            <ol className="routine-items">
              {r.items.map((it, i) => (
                <li key={i}>
                  <span className="grow">{exMap[it.exerciseId]?.name || 'Ejercicio borrado'}</span>
                  <span className="muted small">
                    {it.sets}×{it.reps}
                    {it.weight > 0 ? ` · ${fmtNum(it.weight)} kg` : ''}
                  </span>
                </li>
              ))}
            </ol>
            {!active && (
              <button className="btn block ghost" onClick={() => startWorkout(r.id)}>
                <Icon name="play" size={14} fill="currentColor" /> Empezar {r.name}
              </button>
            )}
          </section>
        );
      })}

      {routines.length === 0 && (
        <div className="empty">
          <p>No tienes rutinas. Crea una con el botón +.</p>
        </div>
      )}

      {editing && <RoutineEditor routine={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function RoutineEditor({ routine, onClose }) {
  const exercises = useStore((s) => s.exercises);
  const routines = useStore((s) => s.routines);
  const saveRoutine = useStore((s) => s.saveRoutine);
  const deleteRoutine = useStore((s) => s.deleteRoutine);
  const [r, setR] = useState(routine);
  const [picker, setPicker] = useState(false);
  const exMap = Object.fromEntries(exercises.map((e) => [e.id, e]));
  const isNew = !routine.id;

  const setItem = (i, patch) => setR({ ...r, items: r.items.map((it, j) => (j === i ? { ...it, ...patch } : it)) });
  const move = (i, d) => {
    const items = [...r.items];
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    [items[i], items[j]] = [items[j], items[i]];
    setR({ ...r, items });
  };
  const toggleDay = (d) => setR({ ...r, days: r.days.includes(d) ? r.days.filter((x) => x !== d) : [...r.days, d].sort() });
  const takenBy = (d) => routines.find((x) => x.id !== r.id && x.days.includes(d));

  const save = () => {
    if (!r.name.trim()) return alert('Ponle nombre a la rutina.');
    // un día solo puede tener una rutina: se lo quitamos a las otras
    for (const other of routines) {
      if (other.id === r.id) continue;
      const days = other.days.filter((d) => !r.days.includes(d));
      if (days.length !== other.days.length) saveRoutine({ ...other, days });
    }
    saveRoutine({ ...r, name: r.name.trim(), id: r.id || uid() });
    onClose();
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title={isNew ? 'Nueva rutina' : 'Editar rutina'}
      footer={
        <div className="btn-row">
          {!isNew && (
            <button
              className="btn danger"
              onClick={() => {
                if (confirm(`¿Borrar "${routine.name}"? Tu historial se conserva.`)) {
                  deleteRoutine(routine.id);
                  onClose();
                }
              }}
            >
              <Icon name="trash" size={16} />
            </button>
          )}
          <button className="btn block" onClick={save}>
            Guardar
          </button>
        </div>
      }
    >
      <div className="form">
        <label>
          Nombre
          <input value={r.name} placeholder="Ej. Torso A" onChange={(e) => setR({ ...r, name: e.target.value })} />
        </label>
      </div>
      <h3 className="sub">Días</h3>
      <div className="day-toggle">
        {DAY_SHORT.map((d, i) => (
          <button key={d} className={r.days.includes(i) ? 'on' : ''} onClick={() => toggleDay(i)} title={takenBy(i) ? `Ahora: ${takenBy(i).name}` : ''}>
            {d}
            {takenBy(i) && !r.days.includes(i) && <i />}
          </button>
        ))}
      </div>
      <p className="muted small">Un punto indica que ese día ya tiene otra rutina; si lo eliges, se reasigna.</p>

      <h3 className="sub">Ejercicios</h3>
      <ul className="edit-items">
        {r.items.map((it, i) => (
          <li key={i}>
            <div className="row gap">
              <b className="grow">{exMap[it.exerciseId]?.name || 'Ejercicio borrado'}</b>
              <button className="icon-btn" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Subir">
                <Icon name="left" size={14} style={{ transform: 'rotate(90deg)' }} />
              </button>
              <button className="icon-btn" onClick={() => move(i, 1)} disabled={i === r.items.length - 1} aria-label="Bajar">
                <Icon name="right" size={14} style={{ transform: 'rotate(90deg)' }} />
              </button>
              <button className="icon-btn" onClick={() => setR({ ...r, items: r.items.filter((_, j) => j !== i) })} aria-label="Quitar">
                <Icon name="trash" size={14} />
              </button>
            </div>
            <div className="item-steppers">
              <label>
                Series
                <Stepper value={it.sets} onChange={(v) => setItem(i, { sets: Math.max(1, v) })} label="series" decimals={0} />
              </label>
              <label>
                Reps
                <Stepper value={it.reps} onChange={(v) => setItem(i, { reps: Math.max(1, v) })} label="repeticiones" decimals={0} />
              </label>
              <label>
                Kg inicial
                <Stepper value={it.weight} step={2.5} onChange={(v) => setItem(i, { weight: v })} label="peso inicial" />
              </label>
            </div>
          </li>
        ))}
      </ul>
      <button className="btn ghost block" onClick={() => setPicker(true)}>
        <Icon name="plus" size={16} /> Agregar ejercicio
      </button>
      <ExercisePicker
        open={picker}
        onClose={() => setPicker(false)}
        exclude={r.items.map((it) => it.exerciseId)}
        onPick={(id) => setR({ ...r, items: [...r.items, { exerciseId: id, sets: 3, reps: 10, weight: 0 }] })}
      />
    </Sheet>
  );
}
