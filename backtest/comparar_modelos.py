import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd, mas_dinero as M, optimizar as O
from dataclasses import replace
C=M.load_contracts('datos'); ch=M.choose_contracts(C); prep=M.prepare(C)
MX='America/Mexico_City'
cache={}
def get(entry,tz):
    k=(entry,tz)
    if k not in cache:
        p=replace(M.Params(),entry=entry,entry_tz=tz); _,sig=M.run(prep,ch,p); cache[k]=(sig,O.paths(prep,sig,p))
    return cache[k]
def trades(entry,tz,filt,sl,tp1,tp2,be,two_stops=False):
    sig,pth=get(entry,tz)
    mask=np.ones(len(sig),bool)
    for f in filt: mask&=sig[f].values
    days=list(sig.fecha); pos={d:i for i,d in enumerate(days)}
    rows=[]; hist=[]
    for i in np.nonzero(mask)[0]:
        d=days[i]
        if two_stops and len(hist)>=2 and hist[-1][1]=='Stop' and hist[-2][1]=='Stop' and pos[d]-pos[hist[-1][0]]<=2:
            hist.append((d,'skip')); continue
        tk,out=O.bracket(pth[i],sl,tp1,tp2,be); hist.append((d,out))
        rows.append({'fecha':d,'ticks':tk,'salida':out,'usd_8mes':4*tk*1.25-8*2.49})
    return pd.DataFrame(rows)
V={
 'M2 tal cual (9:12 CDMX, A+C, 35/30/120 BE)':('09:12',MX,['A','C'],35,30,120,True,False),
 'M2 + regla 2 stops':('09:12',MX,['A','C'],35,30,120,True,True),
 'M2 a las 10:12 NY todo el año':('10:12',M.NY,['A','C'],35,30,120,True,False),
 'M2 bracket anterior 45/30/60 BE':('09:12',MX,['A','C'],45,30,60,True,False),
 'M2 + BOS':('09:12',MX,['A','C','BOS'],35,30,120,True,False),
 'M2 + BOS + VWAP':('09:12',MX,['A','C','BOS','VWAP'],35,30,120,True,False),
 'M2 10:12 NY + BOS + VWAP':('10:12',M.NY,['A','C','BOS','VWAP'],35,30,120,True,False),
 'Mas dinero (10:12 NY, 4 filtros, 30/40/160)':('10:12',M.NY,['A','C','BOS','VWAP'],30,40,160,False,False),
}
res=[]; yrs={}
for name,v in V.items():
    t=trades(*v); s=O.summary(t); a=M.stats(t)
    res.append({'version':name,'ops':a['n'],'gana%':round(100*a['wr'],1),'PF':round(a['pf'],2),'neto':round(a['net']),'caida':round(a['mdd']),'racha':a['racha'],**{k:s[k] for k in ['IS_pf','OOS_pf']}})
    yrs[name[:28]]=t.groupby(pd.to_datetime(t.fecha).dt.year).apply(lambda g: round(M.stats(g)['pf'],2))
    if name.startswith('M2 tal cual'): t.to_csv('operaciones_modelo_b_ac.csv',index=False)
print(pd.DataFrame(res).to_string(index=False))
print(pd.DataFrame(yrs).T.to_string())

def lucid(usd,target=3000,dd=2000):
    res=[]
    for s in range(len(usd)):
        bal=peak=0; out=None
        for k in range(s,len(usd)):
            bal+=usd[k]; peak=max(peak,bal)
            if bal>=target: out=('p',k-s+1); break
            if bal<=min(peak-dd,0): out=('q',k-s+1); break
        if out: res.append(out)
    r=pd.DataFrame(res,columns=['r','n']); return round(100*(r.r=='p').mean(),1), int(r[r.r=='p'].n.median())
print()
for name in ['M2 tal cual (9:12 CDMX, A+C, 35/30/120 BE)','M2 10:12 NY + BOS + VWAP','Mas dinero (10:12 NY, 4 filtros, 30/40/160)']:
    t=trades(*V[name])
    for n in (4,6,8):
        usd=(n/2)*t.ticks.values*1.25-n*2.49
        print(f'{name[:30]:30s} {n} MES pasa/ops', lucid(usd))
