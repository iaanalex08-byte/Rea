"""Análisis estadístico del Modelo B · Gap (2018–2026): escribe dashboard/analisis.json."""
import json, os, sys
import numpy as np, pandas as pd
from scipy import stats as st
import mas_dinero as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard')
rng = np.random.default_rng(42)

def pf(u): l = -u[u < 0].sum(); return float(u[u > 0].sum() / l) if l else float('inf')
def dd(u):
    eq = np.cumsum(u); return float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
def streaks(u):
    w = l = mw = ml = 0
    for x in u:
        if x > 0: w += 1; l = 0
        else: l += 1; w = 0
        mw, ml = max(mw, w), max(ml, l)
    return mw, ml

C = M.load_contracts(sys.argv[1] if len(sys.argv) > 1 else 'datos'); ch = M.choose_contracts(C); prep = M.prepare(C)
t, sig = M.run(prep, ch, M.MODELO_GAP)
t = t[pd.to_datetime(t.fecha).dt.year >= 2018].reset_index(drop=True)
t['fecha'] = pd.to_datetime(t.fecha); t['anio'] = t.fecha.dt.year
t['u'] = 4 * t.ticks * 1.25 - 8 * 2.49          # 8 MES
R = 8 * 35 * 1.25 + 8 * 2.49                      # riesgo por operación (stop completo) con 8 MES
u = t.u.values

# contexto de mercado por día operado y por año (de los datos de ES)
ctx = []
for d, k in ch.items():
    if pd.Timestamp(d).year < 2018: continue
    day = prep[k]['days'].get(d)
    if day is None or len(day) < 300: continue
    ctx.append({'fecha': pd.Timestamp(d), 'rango': day.h.max() - day.l.min(), 'open': day.o.iloc[0], 'close': day.c.iloc[-1]})
ctx = pd.DataFrame(ctx); ctx['anio'] = ctx.fecha.dt.year
ctx['tendencia'] = (ctx.close - ctx.open).abs() / ctx.rango      # 1 = día de tendencia limpia, 0 = rotación

res = {}
wins, losses = u[u > 0], u[u <= 0]
res['general'] = {
    'ops': int(len(u)), 'winrate': round(100 * (u > 0).mean(), 1), 'pf': round(pf(u), 2), 'neto': round(u.sum()),
    'ganancia_media': round(wins.mean(), 2), 'perdida_media': round(losses.mean(), 2), 'payoff': round(wins.mean() / -losses.mean(), 2),
    'esperanza_usd': round(u.mean(), 2), 'esperanza_R': round(u.mean() / R, 3), 'riesgo_R_usd': round(R, 2),
    'caida_max': round(dd(u)), 'racha_ganadora': streaks(u)[0], 'racha_perdedora': streaks(u)[1],
    'winrate_equilibrio': round(100 * -losses.mean() / (wins.mean() - losses.mean()), 1),
    'ops_por_anio': round(len(u) / (t.fecha.max() - t.fecha.min()).days * 365.25, 1),
}
# ventaja estadística
tt = st.ttest_1samp(u, 0, alternative='greater')
bt = st.binomtest(int((u > 0).sum()), len(u), res['general']['winrate_equilibrio'] / 100, alternative='greater')
boot_pf = [pf(rng.choice(u, len(u))) for _ in range(5000)]
boot_mu = [rng.choice(u, len(u)).mean() for _ in range(5000)]
res['edge'] = {'t': round(float(tt.statistic), 2), 'p_t': float(f'{tt.pvalue:.2g}'), 'p_binom': float(f'{bt.pvalue:.2g}'),
               'sqn': round(float(np.sqrt(len(u)) * u.mean() / u.std(ddof=1)), 2),
               'pf_ic90': [round(float(np.percentile(boot_pf, 5)), 2), round(float(np.percentile(boot_pf, 95)), 2)],
               'esperanza_ic90': [round(float(np.percentile(boot_mu, 5)), 1), round(float(np.percentile(boot_mu, 95)), 1)],
               'prob_pf_mayor_1': round(100 * float(np.mean(np.array(boot_pf) > 1)), 1)}

# por año y por periodo + explicación
anual = []
for y, g in t.groupby('anio'):
    v = g.u.values; c = ctx[ctx.anio == y]
    anual.append({'anio': int(y), 'ops': len(v), 'winrate': round(100 * (v > 0).mean(), 1), 'pf': round(pf(v), 2), 'neto': round(v.sum()),
                  'ganancia_media': round(v[v > 0].mean(), 1), 'perdida_media': round(v[v <= 0].mean(), 1),
                  'pct_tp2': round(100 * (g.salida == 'TP1 + TP2').mean(), 1), 'pct_stop': round(100 * (g.salida == 'Stop').mean(), 1),
                  'pct_be': round(100 * (g.salida == 'TP1 + BE').mean(), 1),
                  'rango_medio': round(c.rango.mean(), 1), 'tendencia': round(c.tendencia.mean(), 3),
                  'sp_anual': round(100 * (c.close.iloc[-1] / c.open.iloc[0] - 1), 1), 'caida_max': round(dd(v))})
A = pd.DataFrame(anual)
res['anual'] = anual
res['correlaciones_pf'] = {k: round(float(A.pf.corr(A[k])), 2) for k in ['winrate', 'pct_tp2', 'pct_stop', 'rango_medio', 'tendencia', 'sp_anual', 'ops']}
per = {'2018–2022': t[t.anio <= 2022], '2023–2026': t[t.anio >= 2023]}
for h in (1, 2):
    per[f'{"1er" if h == 1 else "2º"} semestre'] = t[(t.fecha.dt.month <= 6) == (h == 1)]
for q in (1, 2, 3, 4):
    per[f'T{q}'] = t[t.fecha.dt.quarter == q]
res['periodos'] = [{'periodo': k, 'ops': len(g), 'winrate': round(100 * (g.u > 0).mean(), 1), 'pf': round(pf(g.u.values), 2), 'neto': round(g.u.sum())} for k, g in per.items()]

# patrones
DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
def grp(key, labels=None):
    out = []
    for k, g in t.groupby(key):
        out.append({'grupo': labels[k] if labels else str(k), 'ops': len(g), 'winrate': round(100 * (g.u > 0).mean(), 1), 'pf': round(pf(g.u.values), 2),
                    'neto': round(g.u.sum()), 'media': round(g.u.mean(), 1)})
    return out
res['por_dia'] = grp(t.fecha.dt.dayofweek, DIAS)
res['por_mes'] = grp(t.fecha.dt.month - 1, MESES)
res['por_direccion'] = grp(t.dir.map({1: 'Compra', -1: 'Venta'}))
res['por_salida'] = [{'salida': k, 'ops': len(g), 'pct': round(100 * len(g) / len(t), 1), 'media': round(g.u.mean(), 1)} for k, g in t.groupby('salida')]
t['gap_b'] = pd.cut(t.gap, [-8, 0, 8, 20, 1e9], labels=['0 a −8 (leve en contra)', '0 a +8', '+8 a +20', 'más de +20'])
res['por_gap'] = grp(t.gap_b.astype(str))
rng_d = sig.set_index('fecha')
# rango del día anterior como volatilidad
t['vol'] = [prep[c]['days'][max(x for x in prep[c]['days'] if x < f.date() and len(prep[c]['days'][x]) >= 300)].pipe(lambda d: d.h.max() - d.l.min()) for c, f in zip(t.contrato, t.fecha)]
t['vol_b'] = pd.qcut(t.vol, 3, labels=['Ayer tranquilo', 'Ayer normal', 'Ayer volátil'])
res['por_volatilidad'] = grp(t.vol_b.astype(str))

# Monte Carlo: 10,000 años de 56 operaciones remuestreadas
n_y = int(round(res['general']['ops_por_anio']))
sims = rng.choice(u, (10000, n_y))
eq = sims.cumsum(1); mdd = (eq - np.maximum.accumulate(np.c_[np.zeros(10000), eq], 1)[:, 1:]).min(1)
fin = eq[:, -1]
res['montecarlo'] = {'ops_anio': n_y, 'sims': 10000,
    'neto_p5': round(float(np.percentile(fin, 5))), 'neto_p50': round(float(np.percentile(fin, 50))), 'neto_p95': round(float(np.percentile(fin, 95))),
    'prob_anio_perdedor': round(100 * float((fin < 0).mean()), 1),
    'dd_p50': round(float(np.percentile(mdd, 50))), 'dd_p95': round(float(np.percentile(mdd, 5))), 'dd_p99': round(float(np.percentile(mdd, 1))),
    'racha_perd_p95': int(np.percentile([streaks(s)[1] for s in sims[:2000]], 95)),
    'hist': [{'desde': float(a), 'hasta': float(b), 'n': int(c)} for c, a, b in zip(*np.histogram(fin, 24)[0:1], np.histogram(fin, 24)[1][:-1], np.histogram(fin, 24)[1][1:])]}
# forecast: abanico de 12 meses (percentiles del saldo por operación)
fan = []
for k in range(n_y):
    col = eq[:, k]
    fan.append({'op': k + 1, 'p5': round(float(np.percentile(col, 5))), 'p25': round(float(np.percentile(col, 25))), 'p50': round(float(np.percentile(col, 50))),
                'p75': round(float(np.percentile(col, 75))), 'p95': round(float(np.percentile(col, 95)))})
res['forecast'] = fan

# sizing: por cada tamaño, neto esperado/año y caída al 95 %; Kelly
p, b = (u > 0).mean(), wins.mean() / -losses.mean()
kelly = p - (1 - p) / b
per_mes = u / 8
siz = []
for n in (2, 4, 6, 8, 10, 12):
    s2 = rng.choice(per_mes * n, (5000, n_y)); e2 = s2.cumsum(1)
    m2 = (e2 - np.maximum.accumulate(np.c_[np.zeros(5000), e2], 1)[:, 1:]).min(1)
    siz.append({'mes': n, 'riesgo_op': round(n * 35 * 1.25 + n * 2.49), 'neto_anio_p50': round(float(np.median(e2[:, -1]))),
                'dd_p95': round(float(np.percentile(m2, 5))), 'prob_dd_2000': round(100 * float((m2 <= -2000).mean()), 1),
                'riesgo_pct_50k': round(100 * (n * 35 * 1.25 + n * 2.49) / 50000, 2)})
res['sizing'] = {'kelly': round(100 * kelly, 1), 'medio_kelly': round(50 * kelly, 1), 'tabla': siz}

# curva de capital mensual
t['mes'] = t.fecha.dt.to_period('M').astype(str)
mm = t.groupby('mes').u.sum()
res['mensual'] = {'meses': len(mm), 'positivos': int((mm > 0).sum()), 'mejor': [mm.idxmax(), round(mm.max())], 'peor': [mm.idxmin(), round(mm.min())]}
res['curva'] = [{'fecha': f.strftime('%Y-%m-%d'), 'saldo': round(s, 2)} for f, s in zip(t.fecha, np.cumsum(u))]
# rachas detalladas
res['rachas'] = {'ganadora': streaks(u)[0], 'perdedora': streaks(u)[1]}

json.dump(res, open(os.path.join(OUT, 'analisis.json'), 'w'), ensure_ascii=False, indent=0, default=float)
pr = {k: v for k, v in res.items() if k not in ('curva', 'forecast')}
print(json.dumps(pr, ensure_ascii=False, indent=0, default=float)[:9000])
