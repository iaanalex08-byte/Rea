import { useId, useMemo, useState } from 'react';
import { MONTH_SHORT, addDays, startOfDay, startOfWeek, dayKey, shortDate, fmtNum } from '../utils';

/* ---------- línea con área, meta opcional y punto activo ---------- */
export function LineChart({ points, goal, height = 140, unit = 'kg', color = 'var(--accent)' }) {
  const gid = useId().replace(/:/g, '');
  const [hover, setHover] = useState(null);
  const W = 320;
  const H = height;
  const pad = { l: 26, r: 10, t: 10, b: 20 };

  const geo = useMemo(() => {
    if (points.length < 1) return null;
    const ts = points.map((p) => p.t);
    const vs = points.map((p) => p.v);
    if (goal != null) vs.push(goal);
    let t0 = Math.min(...ts);
    let t1 = Math.max(...ts);
    if (t0 === t1) {
      t0 -= 86400000;
      t1 += 86400000;
    }
    let v0 = Math.min(...vs);
    let v1 = Math.max(...vs);
    const span = Math.max(1, v1 - v0);
    v0 -= span * 0.12;
    v1 += span * 0.12;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0)) * (W - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - v0) / (v1 - v0)) * (H - pad.t - pad.b);
    const pts = points.map((p) => [x(p.t), y(p.v)]);
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
    const area = `${line}L${pts[pts.length - 1][0].toFixed(1)},${H - pad.b}L${pts[0][0].toFixed(1)},${H - pad.b}Z`;
    // marcas del eje Y
    const ticks = [];
    const stepRaw = (v1 - v0) / 3;
    const mag = 10 ** Math.floor(Math.log10(stepRaw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= stepRaw) || stepRaw;
    for (let v = Math.ceil(v0 / step) * step; v <= v1; v += step) ticks.push(v);
    // marcas del eje X: meses
    const months = [];
    const d = new Date(t0);
    d.setDate(1);
    d.setHours(0, 0, 0, 0);
    d.setMonth(d.getMonth() + 1);
    const totalMonths = (t1 - t0) / (30 * 86400000);
    const every = totalMonths > 14 ? 3 : totalMonths > 7 ? 2 : 1;
    let i = 0;
    while (d.getTime() <= t1) {
      if (i++ % every === 0) months.push({ x: x(d.getTime()), label: MONTH_SHORT[d.getMonth()] });
      d.setMonth(d.getMonth() + 1);
    }
    return { x, y, pts, line, area, ticks, months };
  }, [points, goal, H]);

  if (!geo) return <div className="chart-empty" style={{ height }}>Sin datos todavía</div>;

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    for (let i = 1; i < geo.pts.length; i++)
      if (Math.abs(geo.pts[i][0] - px) < Math.abs(geo.pts[best][0] - px)) best = i;
    setHover(best);
  };
  const hp = hover != null ? geo.pts[hover] : geo.pts[geo.pts.length - 1];
  const hv = hover != null ? points[hover] : points[points.length - 1];

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ height }}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label={`Gráfica: último valor ${fmtNum(points[points.length - 1].v)} ${unit}`}
      >
        <defs>
          <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.35" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {geo.ticks.map((v) => (
          <g key={v}>
            <line x1={26} x2={W - 10} y1={geo.y(v)} y2={geo.y(v)} className="grid" />
            <text x={22} y={geo.y(v) + 3} className="axis" textAnchor="end">
              {fmtNum(v, 1)}
            </text>
          </g>
        ))}
        {geo.months.map((m) => (
          <text key={m.x} x={m.x} y={H - 5} className="axis" textAnchor="middle">
            {m.label}
          </text>
        ))}
        {goal != null && (
          <>
            <line x1={26} x2={W - 10} y1={geo.y(goal)} y2={geo.y(goal)} className="goal-line" />
            <text x={W - 12} y={geo.y(goal) - 4} className="goal-label" textAnchor="end">
              {fmtNum(goal)}
            </text>
          </>
        )}
        <path d={geo.area} fill={`url(#${gid})`} />
        <path d={geo.line} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {hover != null && <line x1={hp[0]} x2={hp[0]} y1={10} y2={H - 20} className="cursor" />}
      </svg>
      <div
        className="chart-dot"
        style={{ left: `${(hp[0] / W) * 100}%`, top: `${(hp[1] / H) * 100}%`, background: color }}
      />
      {hover != null && (
        <div className="chart-tip" style={{ left: `${Math.min(80, Math.max(20, (hp[0] / W) * 100))}%` }}>
          <b>
            {fmtNum(hv.v)} {unit}
          </b>{' '}
          · {shortDate(hv.t)}
        </div>
      )}
    </div>
  );
}

/* ---------- mapa de actividad (últimas ~52 semanas) ---------- */
export function Heatmap({ workouts, weeks = 52 }) {
  const { cols, monthLabels, max } = useMemo(() => {
    const byDay = {};
    for (const w of workouts) {
      const k = dayKey(w.start);
      byDay[k] = (byDay[k] || 0) + (w.end - w.start) / 60000;
    }
    const first = addDays(startOfWeek(new Date()), -7 * (weeks - 1));
    const today = startOfDay(new Date()).getTime();
    const cols = [];
    const monthLabels = [];
    let lastMonth = -1;
    for (let c = 0; c < weeks; c++) {
      const col = [];
      for (let r = 0; r < 7; r++) {
        const d = addDays(first, c * 7 + r);
        const k = dayKey(d);
        col.push({ k, mins: byDay[k] || 0, future: d.getTime() > today, d });
      }
      const m = col[0].d.getMonth();
      if (m !== lastMonth) {
        if (c > 0 || col[0].d.getDate() <= 7) monthLabels.push({ c, label: MONTH_SHORT[m] });
        lastMonth = m;
      }
      cols.push(col);
    }
    const max = Math.max(60, ...Object.values(byDay));
    return { cols, monthLabels, max };
  }, [workouts, weeks]);

  const level = (m) => (m <= 0 ? 0 : m < max * 0.33 ? 1 : m < max * 0.66 ? 2 : 3);
  const cell = 100 / weeks;

  return (
    <div className="heatmap">
      <div className="heat-months">
        {monthLabels.map((m) => (
          <span key={m.c} style={{ left: `${m.c * cell}%` }}>
            {m.label}
          </span>
        ))}
      </div>
      <div className="heat-grid" style={{ gridTemplateColumns: `repeat(${weeks}, 1fr)` }}>
        {cols.map((col, c) => (
          <div key={c} className="heat-col">
            {col.map((x) => (
              <div
                key={x.k}
                className={`heat-cell l${x.future ? 'f' : level(x.mins)}`}
                title={x.future ? '' : `${shortDate(x.d)}: ${x.mins ? Math.round(x.mins) + ' min' : 'descanso'}`}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="heat-legend">
        Menos tiempo
        <i className="heat-cell l0" />
        <i className="heat-cell l1" />
        <i className="heat-cell l2" />
        <i className="heat-cell l3" />
        Más tiempo
      </div>
    </div>
  );
}

/* ---------- figura con el grupo muscular resaltado ---------- */
const REGIONS = {
  shoulders: ['M38 44c-8 1-12 6-13 13l10 2 6-13z', 'M82 44c8 1 12 6 13 13l-10 2-6-13z'],
  chest: ['M42 46h17v19c-7 1-13-1-17-6z', 'M61 46h17l0 13c-4 5-10 7-17 6z'],
  biceps: ['M25 59l10 2-2 20-9-2z', 'M95 59l-10 2 2 20 9-2z'],
  triceps: ['M24 79l9 2-3 19-8-3z', 'M96 79l-9 2 3 19 8-3z'],
  core: ['M44 67h32l-2 33H46z'],
  legs: ['M45 112h14l-2 46H47z', 'M61 112h14l-2 46H63z', 'M48 162h8l-1 30h-6z', 'M64 162h8l-1 30h-6z'],
  glutes: ['M44 100h32l1 14H43z'],
  back: ['M42 46h36l-2 22H44z'],
  cardio: ['M60 52c-3-4-10-4-10 2 0 5 10 11 10 11s10-6 10-11c0-6-7-6-10-2z'],
};
export function BodyFigure({ muscle }) {
  const base =
    'M60 8a10 10 0 1 1 0 20 10 10 0 0 1 0-20zM50 30h20l2 12 8 2c9 1 14 7 15 15l3 40-8 3-5-40-4 0-1 42 2 46-1 34h-9l-2-34-1-40-1 40-2 34h-9l-1-34 2-46-1-42h-4l-5 40-8-3 3-40c1-8 6-14 15-15l8-2z';
  return (
    <svg viewBox="0 0 120 200" className="body-fig" aria-hidden="true">
      <path d={base} className="body-base" />
      {(REGIONS[muscle] || []).map((d, i) => (
        <path key={i} d={d} className="body-hl" />
      ))}
    </svg>
  );
}
