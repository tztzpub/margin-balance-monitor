"""Causal rolling L1 log-price endpoint; append-only cache with revision invalidation."""
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd
from market import PRICE_FILE

CACHE=Path(__file__).parent/'data/trend_channels.json'
WINDOW=500
LAMBDA=200.
CONTRACT='rolling500_log_l1_lambda200_clarabel_v1'


def endpoint(prices):
    import clarabel
    from scipy import sparse as sp
    y=np.log(np.asarray(prices,dtype=float));n=len(y)
    if n<3 or not np.isfinite(y).all():raise ValueError('Invalid channel window')
    d=sp.diags([np.ones(n-2),-2*np.ones(n-2),np.ones(n-2)],[0,1,2],shape=(n-2,n),format='csc')
    ident=sp.eye(n-2,format='csc')
    p=sp.diags(np.r_[np.ones(n),np.zeros(n-2)],format='csc')
    a=sp.vstack([sp.hstack([d,-ident]),sp.hstack([-d,-ident])],format='csc')
    settings=clarabel.DefaultSettings();settings.verbose=False
    settings.tol_gap_abs=1e-9;settings.tol_gap_rel=1e-9;settings.tol_feas=1e-9
    r=clarabel.DefaultSolver(p,np.r_[-y,np.full(n-2,LAMBDA)],a,np.zeros(2*(n-2)),[clarabel.NonnegativeConeT(2*(n-2))],settings).solve()
    if str(r.status)!='Solved':raise RuntimeError(f'Trend channel solver: {r.status}')
    return float(np.exp(r.x[n-1]))


def signatures(dates,prices):
    h=hashlib.sha256();result=[]
    for date,price in zip(dates,prices):
        h.update(f'{date}:{float(price):.12g}\n'.encode());result.append(h.hexdigest())
    return result


def track(dates,prices,mids):
    result=[];active=None;previous=None
    for i,(date,price,mid) in enumerate(zip(dates,prices,mids)):
        if mid is None:continue
        if active is not None and price>=mid:active=None
        if previous is not None and price<mid*.9 and previous[0]>=previous[1]*.9 and active is None:active=i
        result.append([date,float(price),mid,dates[active] if active is not None else None,i-active if active is not None else None])
        previous=(price,mid)
    return result


def channel_data(path=PRICE_FILE,cache=CACHE,workers=4):
    frame=pd.read_csv(path,dtype={'id':str,'date':str})
    prior=json.loads(cache.read_text()) if cache.exists() else {}
    old=prior.get('series',{}) if prior.get('contract')==CONTRACT else {}
    output=[];saved={}
    for key,name,code in [('csi1000','中证1000','000852'),('microcap','微盘股指数','866006.RI')]:
        g=frame.loc[frame.id==key].sort_values('date');dates=g.date.tolist();prices=g.close.tolist()
        if len(dates)<WINDOW:raise ValueError(f'{key}: fewer than {WINDOW} closes')
        sig=signatures(dates,prices);before=old.get(key,{})
        count=0
        for a,b in zip(sig,before.get('signatures',[])):
            if a!=b:break
            count+=1
        mids=[None]*(WINDOW-1)+before.get('mids',[])[:max(0,count-WINDOW+1)]
        missing=list(range(len(mids),len(prices)))
        if missing:
            print(f'TREND {key}: calculating {len(missing)} endpoints through {dates[-1]}',flush=True)
            windows=(prices[i-WINDOW+1:i+1] for i in missing)
            with ProcessPoolExecutor(max_workers=workers) as pool:mids.extend(pool.map(endpoint,windows,chunksize=16))
        assert len(mids)==len(prices)
        saved[key]=dict(signatures=sig,mids=mids[WINDOW-1:])
        output.append(dict(id=key,name=name,code=code,rows=track(dates,prices,mids)))
    cache.parent.mkdir(exist_ok=True)
    tmp=cache.with_suffix('.tmp');tmp.write_text(json.dumps(dict(contract=CONTRACT,series=saved),separators=(',',':'),allow_nan=False));tmp.replace(cache)
    return output


if __name__=='__main__':
    for s in channel_data():print(s['name'],s['rows'][-1])
