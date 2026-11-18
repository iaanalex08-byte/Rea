"""Combinaciones de filtros de volumen (A+C por volumen, sin BOS en contra, VWAP, volumen relativo, espacio) con varios brackets.
    python3 backtest/modelo_b/combos_volumen.py   -> backtest/resultados/modelo_b_volumen_combos.csv
"""
import sys; sys.path.insert(0,'backtest/modelo_b'); sys.path.insert(0,'backtest')
import numpy as np, pandas as pd
import perfil_volumen as pv, rejilla_filtro as rf
from estructura import cargar, velas, eventos
from variaciones import dias_ny, bos_contra
df=cargar(); F=dias_ny(df,10,12,20,3); bc=bos_contra(F,eventos(velas(df,3))); V=pv.rasgos_volumen(F)
F=[d for d in F if d['date'] in V]; y=np.array([d['date'][:4] for d in F]); f=pd.DataFrame([V[d['date']] for d in F])
base=f.A_vol.values&f.C_vol.values&np.array([not bc[d['date']] for d in F])
combos={'A+C vol + sin BOS':base,'+ VWAP':base&f['VWAP a favor'].values,'+ vol. relativo':base&f['Volumen relativo alto'].values,
 '+ VWAP + vol. relativo':base&f['VWAP a favor'].values&f['Volumen relativo alto'].values,'+ espacio':base&f['Espacio de 10 pts al siguiente nivel'].values,
 '+ VWAP + espacio':base&f['VWAP a favor'].values&f['Espacio de 10 pts al siguiente nivel'].values}
rows=[]
for bn,(sl,t1,t2,be) in {**pv.BRACKETS,'40/30/120 con BE':(40,30,120,True),'50/20/120 con BE':(50,20,120,True)}.items():
    U=np.array([rf.bracket(d,sl,t1,t2,be=be) for d in F])
    for cn,m in combos.items():
        r=pv.met(U[m],y[m]); mes=pd.Series(U[m]).groupby(pd.Series([d['date'][:7] for d,k in zip(F,m) if k])).sum()
        neg=pd.Series((U[m]<=0).astype(int)); r['racha']=int(neg.groupby((neg!=neg.shift()).cumsum()).sum().max()); r['meses+']=f"{(mes>0).sum()}/{len(mes)}"
        rows.append(dict(bracket=bn,combo=cn,**r))
T=pd.DataFrame(rows); pd.set_option('display.width',260)
print(T.to_string(index=False)); T.to_csv('backtest/resultados/modelo_b_volumen_combos.csv',index=False)
