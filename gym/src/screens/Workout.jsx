import { useEffect, useRef, useState } from 'react';
import { useStore, lastPerformance, bestWeight, suggestion } from '../store';
import { MUSCLES, EQUIPMENT } from '../data';
import { Icon, Stepper, useNow } from '../components/ui';
import { BodyFigure } from '../components/charts';
import ExercisePicker from '../components/ExercisePicker';
import { fmtClock, fmtNum, shortDate } from '../utils';

export default function Workout({ onFinished }) {
  const active = useStore((s) => s.active);
  const workouts = useStore((s) => s.workouts);
  const exercisesAll = useStore((s) => s.exercises);
  const restSeconds = useStore((s) => s.restSeconds);
  const st = useStore.getState();
  const now = useNow(500);
  const [pickerOpen, setPickerOpen] = useState(false);
  const buzzed = useRef(null);

  const exMap = Object.fromEntries(exercisesAll.map((e) => [e.id, e]));
  const { exercises, idx } = active;
  const cur = exercises[idx];
  const meta = cur ? exMap[cur.exerciseId] || { name: 'Ejercicio borrado', muscle: '', equipment: 'other' } : null;

  const elapsed = (active.pausedAt || now) - active.start - active.pausedTotal;
  const totalSets = exercises.reduce((a, e) => a + e.sets.length, 0);
  const doneSets = exercises.reduce((a, e) => a + e.sets.filter((s) => s.done).length, 0);
  const restLeft = active.restUntil ? active.restUntil - now : 0;
  const resting = restLeft > 0 && !active.pausedAt;

  // vibrar al terminar el descanso
  useEffect(() => {
    if (active.restUntil && restLeft <= 0 && buzzed.current !== active.restUntil) {
      buzzed.current = active.restUntil;
      navigator.vibrate?.([200, 100, 200]);
    }
  }, [restLeft, active.restUntil]);

  const last = cur ? lastPerformance(workouts, cur.exerciseId) : null;
  const best = cur ? bestWeight(workouts, cur.exerciseId) : null;
  const sug = cur ? suggestion(workouts, cur.exerciseId, cur.target) : null;
  const allDoneHere = cur && cur.sets.length > 0 && cur.sets.every((s) => s.done);

  const go = (i) => st.patchActive({ idx: Math.max(0, Math.min(exercises.length - 1, i)) });

  const finish = () => {
    if (doneSets === 0) {
      if (confirm('No has marcado ninguna serie. ¿Descartar el entreno?')) st.discardWorkout();
      return;
    }
    if (doneSets < totalSets && !confirm(`Llevas ${doneSets} de ${totalSets} series. ¿Terminar y guardar solo las completadas?`)) return;
    const wk = st.finishWorkout();
    if (wk) onFinished?.(wk);
  };

  const close = () => {
    if (doneSets === 0 || confirm('¿Descartar este entreno? Se pierden las series marcadas.')) st.discardWorkout();
  };

  const applySuggestion = () => {
    if (!sug) return;
    cur.sets.forEach((s, j) => !s.done && st.updateSet(idx, j, { w: sug.weight }));
  };

  return (
    <div className="workout" role="dialog" aria-label={`Entreno: ${active.name}`}>
      <header className="wk-head">
        <button className="icon-btn round" onClick={close} aria-label="Descartar entreno">
          <Icon name="close" size={18} />
        </button>
        <div className="wk-title">
          <b>{active.name}</b>
          <small>
            <span className={active.pausedAt ? 'paused' : ''}>{fmtClock(elapsed)}</span> · {doneSets}/{totalSets} series
          </small>
        </div>
        <button className="icon-btn round accent" onClick={finish} aria-label="Terminar entreno">
          <Icon name="check" size={18} stroke={3} />
        </button>
      </header>
      <div className="wk-progress">
        <i style={{ width: `${totalSets ? (doneSets / totalSets) * 100 : 0}%` }} />
      </div>

      <div className="wk-body">
        {cur ? (
          <>
            <div className="wk-nav">
              <button className="icon-btn" disabled={idx === 0} onClick={() => go(idx - 1)} aria-label="Ejercicio anterior">
                <Icon name="left" size={16} />
              </button>
              <span className="muted small">
                Ejercicio {idx + 1} / {exercises.length}
              </span>
              <div className="pager">
                {exercises.map((e, i) => (
                  <button
                    key={i}
                    className={`${i === idx ? 'on' : ''} ${e.sets.length && e.sets.every((s) => s.done) ? 'done' : ''}`}
                    onClick={() => go(i)}
                    aria-label={`Ir al ejercicio ${i + 1}`}
                  />
                ))}
              </div>
              <button className="icon-btn" disabled={idx === exercises.length - 1} onClick={() => go(idx + 1)} aria-label="Siguiente ejercicio">
                <Icon name="right" size={16} />
              </button>
            </div>

            <div className="figure-card">
              <BodyFigure muscle={meta.muscle} />
              <div className="figure-label">{MUSCLES[meta.muscle] || ''}</div>
              <button className="overlay-btn left" onClick={() => st.patchActive({ minimized: true })}>
                <Icon name="min" size={12} /> Minimizar
              </button>
              <button className="overlay-btn right" onClick={st.togglePause}>
                <Icon name={active.pausedAt ? 'play' : 'pause'} size={12} /> {active.pausedAt ? 'Reanudar' : 'Pausar'}
              </button>
            </div>

            <div className="ex-title">
              <h2>{meta.name}</h2>
              <button
                className="icon-btn"
                aria-label="Quitar ejercicio del entreno"
                onClick={() => confirm(`¿Quitar "${meta.name}" de este entreno?`) && st.removeExerciseFromActive(idx)}
              >
                <Icon name="trash" size={16} />
              </button>
            </div>
            <div className="tags">
              <span>{MUSCLES[meta.muscle]}</span>
              <span>{EQUIPMENT[meta.equipment]}</span>
              {best != null && best > 0 && <span>Mejor: {fmtNum(best)} kg</span>}
              {cur.target ? <span>Objetivo: {cur.target} reps</span> : null}
            </div>
            <p className="last-time">
              {last ? (
                <>
                  Última vez ({shortDate(last.date)}): {last.sets.map((s) => `${fmtNum(s.w)}×${s.r}`).join(', ')}
                </>
              ) : (
                'Primera vez con este ejercicio'
              )}
            </p>
            {sug && sug.kind === 'up' && (
              <button className="suggest" onClick={applySuggestion}>
                <Icon name="bolt" size={14} /> La última vez completaste todas las reps — prueba {fmtNum(sug.weight)} kg
              </button>
            )}

            <div className="sets">
              <div className="sets-head">
                <span>Serie</span>
                <span>Peso (kg)</span>
                <span>Reps</span>
                <span />
              </div>
              {cur.sets.map((s, j) => (
                <div key={j} className={`set-row ${s.done ? 'done' : ''}`}>
                  <span className="set-n">{j + 1}</span>
                  <Stepper value={s.w} step={2.5} onChange={(w) => st.updateSet(idx, j, { w })} label={`peso serie ${j + 1}`} />
                  <Stepper value={s.r} step={1} onChange={(r) => st.updateSet(idx, j, { r })} label={`reps serie ${j + 1}`} decimals={0} />
                  <button className={`set-check ${s.done ? 'on' : ''}`} onClick={() => st.toggleSet(idx, j)} aria-label={s.done ? `Desmarcar serie ${j + 1}` : `Marcar serie ${j + 1} como hecha`}>
                    <Icon name="check" size={16} stroke={3} />
                  </button>
                </div>
              ))}
              <div className="btn-row">
                <button className="btn ghost sm" onClick={() => st.addSet(idx)}>
                  <Icon name="plus" size={14} /> Serie
                </button>
                {cur.sets.length > 0 && (
                  <button className="btn ghost sm" onClick={() => st.removeSet(idx, cur.sets.length - 1)}>
                    <Icon name="minus" size={14} /> Quitar última
                  </button>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="empty tall">
            <p>Entreno libre: agrega tu primer ejercicio.</p>
          </div>
        )}

        <button className="btn ghost block" onClick={() => setPickerOpen(true)}>
          <Icon name="plus" size={16} /> Agregar ejercicio
        </button>
      </div>

      <footer className="wk-foot">
        {resting ? (
          <div className="rest">
            <Icon name="timer" size={18} />
            <span className="grow">
              <small className="muted">Descanso</small>
              <b>{fmtClock(restLeft)}</b>
            </span>
            <span className="rest-bar">
              <i style={{ width: `${Math.min(100, (restLeft / (restSeconds * 1000)) * 100)}%` }} />
            </span>
            <button className="btn ghost sm" onClick={() => st.patchActive({ restUntil: active.restUntil + 15000 })}>
              +15 s
            </button>
            <button className="btn sm" onClick={() => st.patchActive({ restUntil: null })}>
              Saltar
            </button>
          </div>
        ) : allDoneHere && idx < exercises.length - 1 ? (
          <button className="btn block" onClick={() => go(idx + 1)}>
            Siguiente: {exMap[exercises[idx + 1].exerciseId]?.name} <Icon name="right" size={16} />
          </button>
        ) : doneSets === totalSets && totalSets > 0 ? (
          <button className="btn block" onClick={finish}>
            <Icon name="check" size={16} stroke={3} /> Terminar entreno
          </button>
        ) : (
          <button className="btn block ghost" onClick={st.togglePause}>
            <Icon name={active.pausedAt ? 'play' : 'pause'} size={16} /> {active.pausedAt ? 'Reanudar' : 'Pausar'} · {fmtClock(elapsed)}
          </button>
        )}
      </footer>

      <ExercisePicker open={pickerOpen} onClose={() => setPickerOpen(false)} onPick={st.addExerciseToActive} exclude={exercises.map((e) => e.exerciseId)} />
    </div>
  );
}
