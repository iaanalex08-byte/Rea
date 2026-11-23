import sys; sys.path.insert(0,'.'); sys.argv=[sys.argv[0],'']
exec(open('mejoras.py').read().split("out=[]")[0])
import itertools
sig['gap_pts']=sig.gap
print('== umbral del gap (en contra de la operación, puntos)')
for th in (-2,-4,-6,-8,-10,-12,-16,-20):
    m=base&~(sig.gap<=th).values; print(th, ev(m), '| con 35/35/120', ev(m,35,35,120))
print('== gap en contra también sin filtros BOS/VWAP (señal pura A+C)')
ac=(sig.A&sig.C).values
for nm,m in (('A+C',ac),('A+C sin gap en contra',ac&~(sig.gap<=-8).values)): print(nm, ev(m))
print('== señal EMA sola, por gap')
allm=np.ones(len(sig),bool)
for nm,m in (('todos',allm),('gap a favor/neutral',~(sig.gap<=-8).values),('gap en contra',(sig.gap<=-8).values)): print(nm, ev(m))
print('== combinaciones')
gp=~(sig.gap<=-8).values; on=~(sig.rng_noche>36.67).values
for nm,m,b in (('base',base,(35,30,120)),('gap',base&gp,(35,30,120)),('gap+TP1 35',base&gp,(35,35,120)),('gap+noche',base&gp&on,(35,30,120)),('gap+noche+TP1 35',base&gp&on,(35,35,120))):
    print(nm, ev(m,*b))
    idx=np.nonzero(m)[0]; tk=np.array([br(i,*b,0) for i in idx],float); y=pd.Series(4*tk*1.25-8*2.49,index=pd.to_datetime(sig.fecha.values[idx]).year)
    print('   por año PF:', {yy:round(g[g>0].sum()/-g[g<0].sum(),2) for yy,g in y.groupby(level=0) if (g<0).any()})
    for n in (4,6,8):
        usd=(n/2)*tk*1.25-n*2.49; res=[]
        for s in range(len(usd)):
            bal=pk=0
            for k in range(s,len(usd)):
                bal+=usd[k]; pk=max(pk,bal)
                if bal>=3000: res.append(('p',k-s+1)); break
                if bal<=min(pk-2000,0): res.append(('q',k-s+1)); break
        r=pd.DataFrame(res,columns=['r','n']); print(f'   Lucid {n} MES pasa {100*(r.r=="p").mean():.0f}% en ~{int(r[r.r=="p"].n.median())} ops')
