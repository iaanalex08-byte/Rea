import pandas as pd, json, sys
TICK={"NQ":0.25,"ES":0.25}; PV={"NQ":2.0,"ES":5.0}  # micros MNQ / MES
BUF=4; COMM=1.0  # 4 ticks buffer, $1 round-trip per micro
def run(sym, iv):
    d=pd.read_csv(f"{sym}_{iv}.csv",index_col=0)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("America/New_York")
    step=5 if iv=="5m" else 60
    tk=TICK[sym]; out=[]
    for day,g in d.groupby(d.index.date):
        if pd.Timestamp(day).weekday()>=5: continue
        mins=g.index.hour*60+g.index.minute
        box=g[(mins>=360)&(mins<540)]
        sess=g[(mins>=540)&(mins<960)]
        if len(box)<(30 if iv=="5m" else 3) or len(sess)<(60 if iv=="5m" else 6): continue
        bh,bl=box.High.max(),box.Low.min()
        rec={"date":str(day),"bh":bh,"bl":bl,"status":"sin barrido"}
        dir=0; ext=None; pend=None; pos=None
        rows=list(sess.itertuples())
        for i,b in enumerate(rows):
            t=b.Index.hour*60+b.Index.minute
            last = (t+step>=960) or i==len(rows)-1
            if pos:
                s=pos
                if s["dir"]==-1:
                    if b.High>=s["sl"]: s["sl_hit"]=True; break
                    s["mfe"]=max(s["mfe"],(s["lvl"]-b.Low)/s["risk"])
                    if last: s["end"]=(s["fill"]-b.Close)/s["risk"]; break
                else:
                    if b.Low<=s["sl"]: s["sl_hit"]=True; break
                    s["mfe"]=max(s["mfe"],(b.High-s["lvl"])/s["risk"])
                    if last: s["end"]=(b.Close-s["fill"])/s["risk"]; break
                continue
            if pend:
                lvl,sl=pend; risk=abs(lvl-sl)
                trig = b.Low<=lvl if dir==-1 else b.High>=lvl
                if trig:
                    if dir==-1: fill=min(b.Open,lvl)-tk
                    else: fill=max(b.Open,lvl)+tk
                    pos={"dir":dir,"lvl":lvl,"sl":sl,"risk":risk,"fill":fill,"mfe":0.0,"sl_hit":False,"end":None,
                         "entry_time":b.Index.strftime("%H:%M"),"ext":ext}
                    rec["status"]="operado"
                    if (dir==-1 and b.High>=sl) or (dir==1 and b.Low<=sl):
                        pos["sl_hit"]=True; break
                    pos["mfe"]=((lvl-b.Low) if dir==-1 else (b.High-lvl))/risk
                    if last:
                        pos["end"]=((fill-b.Close) if dir==-1 else (b.Close-fill))/risk; break
                    continue
                pend=None
            if dir==0:
                if t<660:
                    up,dn=b.High>bh,b.Low<bl
                    if up and dn: rec["status"]="barre ambos"; break
                    if up: dir,ext=-1,b.High
                    elif dn: dir,ext=1,b.Low
                    if dir: rec["sweep_time"]=b.Index.strftime("%H:%M"); rec["status"]="sin entrada"
                else: break
            else:
                if dir==-1:
                    ext=max(ext,b.High)
                    if b.Low<bl: rec["status"]="anulado (barre el otro lado)"; break
                else:
                    ext=min(ext,b.Low)
                    if b.High>bh: rec["status"]="anulado (barre el otro lado)"; break
            if dir:
                if t>=660: break
                lvl=round(((ext+bl)/2 if dir==-1 else (ext+bh)/2)/tk)*tk
                sl=ext+BUF*tk if dir==-1 else ext-BUF*tk
                pend=(lvl,sl)
        if pos:
            p=pos; r=p["risk"]
            rec.update(dir="venta" if p["dir"]==-1 else "compra", entry_time=p["entry_time"],
              lvl=p["lvl"], sl=p["sl"], ext=p["ext"], risk_pts=round(r,2),
              fill_off=round(((p["fill"]-p["lvl"]) if p["dir"]==1 else (p["lvl"]-p["fill"]))/r*-1,4),
              mfe=round(p["mfe"],4), sl_hit=p["sl_hit"], end=None if p["end"] is None else round(p["end"],4),
              slipR=round(tk/r,4), commR=round(COMM/(r*PV[sym]),4))
            if not p["sl_hit"] and p["end"] is None: rec["end"]=0.0
        out.append(rec)
    return out
res={}
for s in ["NQ","ES"]:
    for iv in ["5m","1h"]:
        res[f"{s}_{iv}"]=run(s,iv)
json.dump(res,open("results.json","w"))
# quick summary
def summ(tr,X):
    R=[]
    for t in tr:
        if t["status"]!="operado": continue
        if t["mfe"]>=X: r=X+t["fill_off"]
        elif t["sl_hit"]: r=-1+t["fill_off"]-t["slipR"]
        else: r=t["end"]
        R.append(r-t["commR"])
    w=sum(1 for r in R if r>0)
    return len(R), w/len(R) if R else 0, sum(R)
for k,v in res.items():
    st={}
    for t in v: st[t["status"]]=st.get(t["status"],0)+1
    print(k,len(v),st)
    for X in [0.25,0.5,1,2]:
        n,wr,tot=summ(v,X); print(f"   {X}R n={n} win={wr:.0%} totR={tot:.1f}")
