import { useRef, useState } from 'react';
import { useStore } from '../store';
import { Sheet, Icon, Stepper } from '../components/ui';
import { dayKey } from '../utils';

export default function Settings({ open, onClose }) {
  const weeklyGoal = useStore((s) => s.weeklyGoal);
  const restSeconds = useStore((s) => s.restSeconds);
  const setWeeklyGoal = useStore((s) => s.setWeeklyGoal);
  const setRestSeconds = useStore((s) => s.setRestSeconds);
  const fileRef = useRef(null);
  const [msg, setMsg] = useState('');

  const exportData = () => {
    const s = useStore.getState();
    const data = {
      app: 'gym',
      version: 1,
      exportedAt: new Date().toISOString(),
      exercises: s.exercises,
      routines: s.routines,
      workouts: s.workouts,
      weights: s.weights,
      goalWeight: s.goalWeight,
      weeklyGoal: s.weeklyGoal,
      restSeconds: s.restSeconds,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `gym-respaldo-${dayKey(new Date())}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setMsg('Respaldo descargado.');
  };

  const importData = async (file) => {
    try {
      const data = JSON.parse(await file.text());
      if (!Array.isArray(data.workouts) || !Array.isArray(data.routines)) throw new Error('formato');
      if (!confirm('Esto reemplaza tus datos actuales con los del respaldo. ¿Continuar?')) return;
      useStore.getState().importData(data);
      setMsg(`Importado: ${data.workouts.length} entrenos, ${data.weights?.length || 0} pesos.`);
    } catch {
      setMsg('No se pudo leer el archivo. ¿Es un respaldo de esta app?');
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Ajustes y datos">
      <div className="setting">
        <span className="grow">
          <b>Meta semanal</b>
          <small className="muted">Entrenos por semana</small>
        </span>
        <Stepper value={weeklyGoal} onChange={(v) => setWeeklyGoal(Math.max(1, Math.min(7, v)))} label="entrenos por semana" decimals={0} />
      </div>
      <div className="setting">
        <span className="grow">
          <b>Descanso entre series</b>
          <small className="muted">Segundos</small>
        </span>
        <Stepper value={restSeconds} step={15} onChange={(v) => setRestSeconds(Math.max(0, v))} label="segundos de descanso" decimals={0} />
      </div>

      <h3 className="sub">Tus datos</h3>
      <p className="muted small">
        Todo se guarda en este dispositivo. Descarga un respaldo para moverlo a otro teléfono o guardarlo.
      </p>
      <div className="btn-row">
        <button className="btn ghost" onClick={exportData}>
          <Icon name="download" size={16} /> Exportar
        </button>
        <button className="btn ghost" onClick={() => fileRef.current?.click()}>
          <Icon name="upload" size={16} /> Importar
        </button>
        <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={(e) => e.target.files[0] && importData(e.target.files[0])} />
      </div>
      <div className="btn-row">
        <button
          className="btn ghost"
          onClick={() => {
            if (confirm('Esto reemplaza tu historial y pesos con datos de ejemplo. ¿Continuar?')) {
              useStore.getState().loadDemo();
              setMsg('Datos de ejemplo cargados.');
            }
          }}
        >
          Datos de ejemplo
        </button>
        <button
          className="btn danger"
          onClick={() => {
            if (confirm('¿Borrar todos los datos? No se puede deshacer.')) {
              useStore.getState().resetAll();
              setMsg('Datos borrados.');
            }
          }}
        >
          <Icon name="trash" size={16} /> Borrar todo
        </button>
      </div>
      {msg && <p className="note">{msg}</p>}
    </Sheet>
  );
}
