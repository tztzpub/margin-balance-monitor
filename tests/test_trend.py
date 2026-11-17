import json
import numpy as np
import pandas as pd
import trend


def test_log_linear_prices_have_no_trend_penalty():
    p=np.exp(np.linspace(5,5.3,500))
    assert abs(trend.endpoint(p)/p[-1]-1)<1e-5


def test_independent_episode_and_recovery():
    rows=trend.track(list('abcdef'),[100,89,91,88,100,89],[100]*6)
    assert rows[1][3:] == ['b',0]
    assert rows[3][3:] == ['b',2]
    assert rows[4][3:] == [None,None]
    assert rows[5][3:] == ['f',0]


def test_cache_unchanged_append_and_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(trend,'WINDOW',3)
    class Pool:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def map(self,fn,windows,**kw):return map(fn,windows)
    monkeypatch.setattr(trend,'ProcessPoolExecutor',Pool)
    calls=[]
    def solve(prices):calls.append(list(prices));return float(np.mean(prices))
    monkeypatch.setattr(trend,'endpoint',solve)
    path=tmp_path/'prices.csv';cache=tmp_path/'cache.json'
    def save(n,rev=False):
        pd.DataFrame([dict(id=key,date=f'2026-01-{i+1:02}',close=(90 if rev and i==2 else 100+i)) for key in ['csi1000','microcap'] for i in range(n)]).to_csv(path,index=False)
    save(5);original=trend.channel_data(path,cache);assert len(calls)==6
    trend.channel_data(path,cache);assert len(calls)==6
    save(6);new=trend.channel_data(path,cache);assert len(calls)==8
    assert original[0]['rows']==new[0]['rows'][:-1]
    save(6,True);trend.channel_data(path,cache);assert len(calls)==16
    assert json.loads(cache.read_text())['contract']==trend.CONTRACT
