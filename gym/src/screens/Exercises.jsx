import { useMemo, useState } from 'react';
import { useStore, exerciseHistory } from '../store';
import { MUSCLES, EQUIPMENT } from '../data';
import { Icon, Sheet } from '../components/ui';
import { LineChart, BodyFigure } from '../components/charts';
import { fmtNum, shortDate } from '../utils';

export default function Exercises() {
  const exercises = useStore((s) => s.exercises);
  const workouts = useStore((s) => s.workouts);
  const [q, setQ] = useState('');
  const [muscle, setMuscle] = useState('');
  const [detail, setDetail] = useState(null);
  const [adding, setAdding] = useState(false);

  const stats = useMemo(() => {
    const out = {};
    for (const w of workouts)
      for (const e of w.exercises) {
        const o = (out[e.exerciseId] ||= { n: 0, best: 0 });
        o.n++;
        for (const s of e.sets) if (s.w > o.best) o.best = s.w;
      }
    return out;
  }, [workouts]);

  const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const list = exercises.filter((e) => (!muscle || e.muscle === muscle) && (!q || norm(e.name).includes(norm(q))));

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Ejercicios</h1>
          <p className="muted">{exercises.length} en tu biblioteca</p>
        </div>
        <button className="icon-btn round accent" onClick={() => setAdding(true)} aria-label="Nuevo ejercicio">
          <Icon name="plus" size={18} />
        </button>
      </header>

      <div className="search">
        <Icon name="search" size={16} />
        <input placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="chips">
        <button className={!muscle ? 'on' : ''} onClick={() => setMuscle('')}>
          Todos
        </button>
        {Object.entries(MUSCLES).map(([k, v]) => (
          <button key={k} className={muscle === k ? 'on' : ''} onClick={() => setMuscle(k)}>
            {v}
          </button>
        ))}
      </div>

      <ul className="ex-list">
        {list.map((e) => (
          <li key={e.id}>
            <button onClick={() => setDetail(e.id)}>
              <span className="ex-thumb">
                <BodyFigure muscle={e.muscle} />
              </span>
              <span className="grow">
                <b>{e.name}</b>
                <small className="muted">
                  {MUSCLES[e.muscle]} · {EQUIPMENT[e.equipment]}
                  {e.custom ? ' · propio' : ''}
                </small>
              </span>
              {stats[e.id] && (
                <span className="ex-best">
                  <b>{stats[e.id].best > 0 ? `${fmtNum(stats[e.id].best)} kg` : '—'}</b>
                  <small className="muted">{stats[e.id].n}×</small>
                </span>
              )}
            </button>
          </li>
        ))}
        {!list.length && <li className="muted small pad">Nada coincide.</li>}
      </ul>

      {detail && <ExerciseDetail id={detail} onClose={() => setDetail(null)} />}
      {adding && <NewExercise onClose={() => setAdding(false)} />}
    </>
  );
}

function ExerciseDetail({ id, onClose }) {
  const ex = useStore((s) => s.exercises.find((e) => e.id === id));
  const workouts = useStore((s) => s.workouts);
  const routines = useStore((s) => s.routines);
  const deleteExercise = useStore((s) => s.deleteExercise);
  const hist = useMemo(() => exerciseHistory(workouts, id), [workouts, id]);
  if (!ex) return null;
  const inRoutines = routines.filter((r) => r.items.some((it) => it.exerciseId === id));
  const best = hist.length ? Math.max(...hist.map((h) => h.top)) : null;
  const best1rm = hist.length ? Math.max(...hist.map((h) => h.e1rm)) : null;

  return (
    <Sheet open onClose={onClose} title={ex.name}>
      <div className="tags">
        <span>{MUSCLES[ex.muscle]}</span>
        <span>{EQUIPMENT[ex.equipment]}</span>
        {inRoutines.map((r) => (
          <span key={r.id} className="tag-accent">
            {r.name}
          </span>
        ))}
      </div>
      <div className="stat-grid">
        <div className="stat">
          <small>Récord</small>
          <b>{best != null ? `${fmtNum(best)} kg` : '—'}</b>
        </div>
        <div className="stat">
          <small>1RM estimado</small>
          <b>{best1rm ? `${fmtNum(best1rm)} kg` : '—'}</b>
        </div>
      </div>
      <h3 className="sub">Peso máximo por sesión</h3>
      <LineChart points={hist.map((h) => ({ t: h.date, v: h.top }))} height={130} color="var(--blue)" />
      {hist.length > 0 && (
        <>
          <h3 className="sub">Últimas sesiones</h3>
          <ul className="plain-list">
            {hist
              .slice(-8)
              .reverse()
              .map((h) => (
                <li key={h.date}>
                  <span className="grow">{shortDate(h.date)}</span>
                  <span className="muted small">{h.sets.map((s) => `${fmtNum(s.w)}×${s.r}`).join(', ')}</span>
                </li>
              ))}
          </ul>
        </>
      )}
      {ex.custom && (
        <button
          className="btn danger block"
          onClick={() => {
            if (inRoutines.length) return alert('Quítalo primero de tus rutinas.');
            if (confirm(`¿Borrar "${ex.name}"?`)) {
              deleteExercise(id);
              onClose();
            }
          }}
        >
          <Icon name="trash" size={16} /> Borrar ejercicio
        </button>
      )}
    </Sheet>
  );
}

function NewExercise({ onClose }) {
  const addExercise = useStore((s) => s.addExercise);
  const [name, setName] = useState('');
  const [muscle, setMuscle] = useState('chest');
  const [equipment, setEquipment] = useState('barbell');
  const save = () => {
    if (!name.trim()) return;
    addExercise({ name: name.trim(), muscle, equipment });
    onClose();
  };
  return (
    <Sheet
      open
      onClose={onClose}
      title="Nuevo ejercicio"
      footer={
        <button className="btn block" onClick={save} disabled={!name.trim()}>
          Guardar
        </button>
      }
    >
      <div className="form">
        <label>
          Nombre
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Press Arnold" autoFocus />
        </label>
        <label>
          Músculo
          <select className="select" value={muscle} onChange={(e) => setMuscle(e.target.value)}>
            {Object.entries(MUSCLES).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Equipo
          <select className="select" value={equipment} onChange={(e) => setEquipment(e.target.value)}>
            {Object.entries(EQUIPMENT).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
    </Sheet>
  );
}
