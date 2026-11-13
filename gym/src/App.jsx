import { useEffect, useState } from 'react';
import { useStore } from './store';
import { Icon } from './components/ui';
import Home from './screens/Home';
import Plan from './screens/Plan';
import Stats from './screens/Stats';
import Exercises from './screens/Exercises';
import Workout from './screens/Workout';
import StartSheet from './screens/StartSheet';
import Summary from './screens/Summary';

const TABS = [
  { id: 'home', label: 'Inicio', icon: 'home' },
  { id: 'plan', label: 'Plan', icon: 'plan' },
  { id: 'start', label: 'Empezar', icon: 'dumbbell' },
  { id: 'stats', label: 'Stats', icon: 'stats' },
  { id: 'exercises', label: 'Ejercicios', icon: 'list' },
];

const readHash = () => {
  const h = location.hash.replace('#/', '');
  return TABS.some((t) => t.id === h && h !== 'start') ? h : 'home';
};

export default function App() {
  const [tab, setTab] = useState(readHash);
  const [startOpen, setStartOpen] = useState(false);
  const [summary, setSummary] = useState(null);
  const active = useStore((s) => s.active);
  const patchActive = useStore((s) => s.patchActive);

  useEffect(() => {
    const on = () => setTab(readHash());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);

  const go = (id) => {
    if (id === 'start') {
      if (active) patchActive({ minimized: false });
      else setStartOpen(true);
      return;
    }
    location.hash = `#/${id}`;
    setTab(id);
    window.scrollTo(0, 0);
  };

  const showWorkout = active && !active.minimized;

  return (
    <div className="app">
      <main className="screen">
        {tab === 'home' && <Home go={go} openStart={() => setStartOpen(true)} />}
        {tab === 'plan' && <Plan />}
        {tab === 'stats' && <Stats />}
        {tab === 'exercises' && <Exercises />}
      </main>

      <nav className="tabbar" aria-label="Secciones">
        {TABS.map((t) =>
          t.id === 'start' ? (
            <button key={t.id} className={`tab-start ${active ? 'resume' : ''}`} onClick={() => go('start')} aria-label={active ? 'Reanudar entreno' : 'Empezar entreno'}>
              <span className="tab-start-btn">
                <Icon name={active ? 'play' : 'dumbbell'} size={24} stroke={2.4} fill={active ? 'currentColor' : 'none'} />
              </span>
              <span className="tab-label">{active ? 'Reanudar' : t.label}</span>
            </button>
          ) : (
            <button key={t.id} className={`tab ${tab === t.id ? 'on' : ''}`} onClick={() => go(t.id)} aria-current={tab === t.id ? 'page' : undefined}>
              <Icon name={t.icon} size={21} />
              <span className="tab-label">{t.label}</span>
            </button>
          )
        )}
      </nav>

      {showWorkout && <Workout onFinished={setSummary} />}
      <Summary workout={summary} onClose={() => setSummary(null)} />
      <StartSheet open={startOpen} onClose={() => setStartOpen(false)} />
    </div>
  );
}
