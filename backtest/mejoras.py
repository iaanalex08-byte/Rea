import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd, mas_dinero as M, optimizar as O
from dataclasses import replace
C=M.load_contracts('datos'); ch=M.choose_contracts(C); prep=M.prepare(C)
p=M.Params(); _,sig=M.run(prep,ch,p); pth=O.paths(prep,sig,p)
IS=O.IS_END
# ---- features por señal
rows=[]
dcache={}
for k,P in prep.items():
    days=sorted(P['days']); full=[d for d in days if len(P['days'][d])>=300]
    rng=pd.Series({d:P['days'][d].h.max()-P['days'][d].l.min() for d in full})
    cls=pd.Series({d:P['days'][d].c.iloc[-1] for d in full})
    dcache[k]=(rng,cls)
for r in sig.itertuples():
    P=prep[r.contrato]; rng,cls=dcache[r.contrato]
    prev=rng[rng.index<r.fecha]; pc=cls[cls.index<r.fecha]
    today=P['days'][r.fecha]; o930=today.o.iloc[0]
    m1=P['m1']; on=m1[(m1.index>=r.t.normalize()-pd.Timedelta(hours=6))&(m1.index<r.t.normalize()+pd.Timedelta(hours=9,minutes=30))]
    rows.append({'rng_ayer':prev.iloc[-1] if len(prev) else np.nan,
                 'atr14':prev.iloc[-14:].mean() if len(prev)>=14 else np.nan,
                 'rng_noche':(on.h.max()-on.l.min()) if len(on) else np.nan,
                 'gap':r.dir*(o930-pc.iloc[-1]) if len(pc) else np.nan,
                 'dist_ema':abs(r.entrada-r.ema),
                 'tend':r.dir*np.sign(pc.iloc[-1]-pc.iloc[-20:].mean()) if len(pc)>=20 else 0,
                 'mov_mañana':r.dir*(r.entrada-o930),
                 'dow':pd.Timestamp(r.fecha).dayofweek})
F=pd.DataFrame(rows,index=sig.index); sig=pd.concat([sig,F],axis=1)
base=(sig.A&sig.C&sig.BOS&sig.VWAP).values
def br(i,sl,t1,t2,lock):
    cf,ca,adv,last=pth[i]; n=len(cf)
    i_sl=np.searchsorted(ca,sl); i1=np.searchsorted(cf,t1)
    if i_sl<=i1: return -2*sl if i_sl<n else 2*last
    i2=np.searchsorted(cf,t2)
    if lock is None:
        return t1+t2 if i2<i_sl and i2<n else (t1-sl if i_sl<n else t1+last)
    hit=np.nonzero(adv[i1+1:]>=-lock)[0]; ib=i1+1+hit[0] if len(hit) else n
    if i2==i1 or i2<ib: return t1+t2 if i2<n else t1+last
    return t1+lock if ib<n else t1+last
def ev(mask,sl=35,t1=30,t2=120,lock=0,paths=None):
    global pth
    old=pth
    if paths is not None: pth=paths
    idx=np.nonzero(mask)[0]; tk=np.array([br(i,sl,t1,t2,lock) for i in idx],float); pth=old
    t=pd.DataFrame({'fecha':sig.fecha.values[idx],'usd_8mes':4*tk*1.25-8*2.49})
    s=O.summary(t); a=M.stats(t); return {'ops':a['n'],'PF':round(a['pf'],2),'neto':round(a['net']),'caida':round(a['mdd']),'IS':s['IS_pf'],'OOS':s['OOS_pf']}
out=[]
out.append(('BASE 35/30/120 BE',ev(base)))
print('== 1. bracket alrededor de 35/30/120 (BE)')
g=[]
for sl in (25,30,35,40,45):
  for t1 in (20,25,30,35,40):
    for t2 in (80,100,120,160):
      r=ev(base,sl,t1,t2); g.append({'sl':sl,'tp1':t1,'tp2':t2,**r})
g=pd.DataFrame(g); g['min']=g[['IS','OOS']].min(axis=1)
print(g.sort_values('min',ascending=False).head(10).to_string(index=False))
print('vecinos de 35/30/120:'); print(g[(g.sl.between(30,40))&(g.tp1.between(25,35))&(g.tp2.between(100,160))][['sl','tp1','tp2','PF','IS','OOS']].to_string(index=False))
print('== 2. tras TP1 asegurar X ticks (None = sin BE)')
for lock in (None,0,5,10,15,20): print(lock, ev(base,lock=lock))
print('== 3. salida temprana')
for ca in ('12:00','13:00','14:00','15:00'):
    pp=replace(p,close_at=ca); print(ca, ev(base,paths=O.paths(prep,sig,pp)))
print('== 4. filtros por terciles (umbral de 2018-22)')
isd=sig.fecha<=IS
for f in ['rng_ayer','atr14','rng_noche','gap','dist_ema','mov_mañana']:
    q=sig.loc[base&isd,f].quantile([1/3,2/3]).values
    lo=sig[f]<=q[0]; mid=(sig[f]>q[0])&(sig[f]<=q[1]); hi=sig[f]>q[1]
    print(f, 'cortes',np.round(q,2)); 
    for nm,m in (('bajo',lo),('medio',mid),('alto',hi),('sin bajo',~lo),('sin alto',~hi)): print('   ',nm, ev(base&m.values))
print('== 5. tendencia diaria (20 días)')
for v,nm in ((1,'a favor'),(-1,'en contra')): print(nm, ev(base&(sig.tend==v).values))
print('== 6. dirección y día')
for v,nm in ((1,'compras'),(-1,'ventas')): print(nm, ev(base&(sig.dir==v).values))
for dw in range(5): print('dia',dw, ev(base&(sig.dow==dw).values))
print(out)
sig.to_pickle(S+'/sig_feat.pkl') if (S:=sys.argv[1]) else None
