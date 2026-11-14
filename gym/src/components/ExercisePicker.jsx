import { useState } from 'react';
import { useStore } from '../store';
import { MUSCLES, EQUIPMENT } from '../data';
import { Sheet, Icon } from './ui';

export default function ExercisePicker({ open, onClose, onPick, exclude = [] }) {
  const exercises = useStore((s) => s.exercises);
  const [q, setQ] = useState('');
  const [muscle, setMuscle] = useState('');
  const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const list = exercises.filter(
    (e) => !exclude.includes(e.id) && (!muscle || e.muscle === muscle) && (!q || norm(e.name).includes(norm(q)))
  );
  return (
    <Sheet open={open} onClose={onClose} title="Agregar ejercicio">
      <div className="search">
        <Icon name="search" size={16} />
        <input placeholder="Buscar ejercicio" value={q} onChange={(e) => setQ(e.target.value)} />
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
      <ul className="plain-list pick-list">
        {list.map((e) => (
          <li key={e.id}>
            <button
              onClick={() => {
                onPick(e.id);
                onClose();
              }}
            >
              <span className="grow">
                <b>{e.name}</b>
                <small className="muted">
                  {MUSCLES[e.muscle]} · {EQUIPMENT[e.equipment]}
                </small>
              </span>
              <Icon name="plus" size={18} />
            </button>
          </li>
        ))}
        {!list.length && <li className="muted small">Nada coincide. Puedes crear ejercicios en la pestaña Ejercicios.</li>}
      </ul>
    </Sheet>
  );
}
