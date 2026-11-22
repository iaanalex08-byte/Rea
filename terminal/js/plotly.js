// Lazy-loads the 3D-capable Plotly bundle only when a view needs it.
let loading;
export function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  loading ??= new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/plotly.js-gl3d-dist-min@2.35.2/plotly-gl3d.min.js';
    s.onload = () => res(window.Plotly);
    s.onerror = () => { loading = null; s.remove(); rej(new Error('No se pudo cargar Plotly')); };
    document.head.append(s);
  });
  return loading;
}

export const AXIS = { gridcolor: '#1f2731', zerolinecolor: '#2a3440', color: '#a7b0bb', tickfont: { size: 10 } };
export const LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, system-ui, sans-serif', color: '#a7b0bb', size: 11 },
  margin: { l: 48, r: 12, t: 8, b: 40 },
  legend: { orientation: 'h', y: -0.2, font: { size: 11 } },
  hoverlabel: { bgcolor: '#131921', bordercolor: '#2a3440', font: { family: 'JetBrains Mono, monospace', size: 11 } },
};
export const CONFIG = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ['toImage', 'sendDataToCloud', 'lasso2d', 'select2d'] };
