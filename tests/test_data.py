import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import chart_data
from refresh import validate,fetch

def sample():
 return pd.DataFrame({'date':pd.bdate_range('2025-01-01',periods=25).strftime('%Y-%m-%d'),'financing_balance_yi':range(100,125),'securities_lending_balance_yi':range(20,45),'financing_buy_yi':[0.]*25})

def test_twenty_observations_and_no_range_rebasing(tmp_path):
 f=sample();path=tmp_path/'input.csv';f.to_csv(path,index=False);rows=chart_data(path)
 assert len(rows)==5
 assert rows[0][4:]==[120,40,100,20]
 assert rows[-1][4:]==[124,44,104,24]
 assert rows[0][0]==f.iloc[20]['date']
 assert rows[0][1]==20
 assert rows[0][2]==100
 assert rows[0][3]==f.iloc[0]['date']
 assert rows[-1][3]==f.iloc[4]['date']
 assert rows[-1][1]==pytest.approx((124/104-1)*100,abs=1e-6)

def test_missing_history_and_invalid_data_fail():
 f=sample();validate(f)
 with pytest.raises(ValueError):validate(f.iloc[1:],f)
 with pytest.raises(ValueError):validate(pd.concat([f,f.iloc[:1]]))
 for v in [None,float('inf'),-1]:
  bad=f.astype({'financing_balance_yi':float});bad.loc[0,'financing_balance_yi']=v
  with pytest.raises(ValueError):validate(bad)

def test_pagination_rejects_incomplete_response():
 class Response:
  def raise_for_status(self):pass
  def json(self):return {'success':True,'result':{'count':2,'pages':1,'data':[{'STATISTICS_DATE':'2025-01-01','FIN_BALANCE':1,'FIN_BUY_AMT':1,'LOAN_BALANCE':1}]}}
 class Session:
  def get(self,*args,**kwargs):return Response()
 with pytest.raises(ValueError,match='Incomplete'):fetch(Session())


def test_bias_uses_today_close_and_sixty_sessions_without_future_data(tmp_path):
 from market import bias_data,SERIES
 dates=pd.bdate_range('2025-01-01',periods=70).strftime('%Y-%m-%d')
 frame=pd.DataFrame([(s['id'],d,float(i+100)) for s in SERIES for i,d in enumerate(dates)],columns=['id','date','close'])
 path=tmp_path/'prices.csv';frame.to_csv(path,index=False)
 before=bias_data(path)[0]['rows']
 assert before[0][0]==dates[59]
 assert before[0][1]==pytest.approx((159/(sum(range(100,160))/60)-1)*100,abs=1e-6)
 assert before[0][4]==dates[59]
 assert before[0][5]==dates[0]
 frame.loc[frame.date==dates[-1],'close']=999999
 frame.to_csv(path,index=False)
 after=bias_data(path)[0]['rows']
 assert after[:-1]==before[:-1]
 assert after[-1][1]!=before[-1][1]
 assert after[-1][2]==999999
 assert after[-1][3]==pytest.approx((sum(range(110,169))+999999)/60,abs=1e-8)


def test_market_missing_day_cannot_silently_shorten_window(tmp_path):
 from market import validate_prices,SERIES
 dates=pd.bdate_range('2025-01-01',periods=70).strftime('%Y-%m-%d')
 frame=pd.DataFrame([(s['id'],d,100.) for s in SERIES for d in dates],columns=['id','date','close'])
 validate_prices(frame)
 with pytest.raises(ValueError,match='trading sessions'):validate_prices(frame.loc[~((frame.id=='star')&(frame.date==dates[20]))])


def test_october_30_bias_uses_actual_completed_close():
 from market import bias_data
 expected={'all':-13.15,'star':-25.23,'chinext':-24.86,'csi300':-10.45,'csi500':-16.44,'csi1000':-16.06,'csi2000':-14.15}
 for series in bias_data():
  if series['id'] in expected:
   row=next(r for r in series['rows'] if r[0]=='2026-10-30')
   assert round(row[1],2)==expected[series['id']]


def test_market_refresh_rejects_missing_source_overlap():
 from market import fetch_prices,SERIES
 previous=pd.DataFrame([(s['id'],'2026-10-30',100.) for s in SERIES],columns=['id','date','close'])
 class Response:
  def raise_for_status(self):pass
  def json(self):return {'code':0,'data':{}}
 class Session:
  def get(self,*args,**kwargs):return Response()
 with pytest.raises(ValueError,match='omitted published sessions'):fetch_prices(Session(),previous)


def test_new_etfs_backfill_while_existing_series_refresh_recently(monkeypatch):
 import market
 from datetime import datetime
 class Clock:
  @staticmethod
  def now(tz):return datetime(2026,11,2,13,0,tzinfo=tz)
 monkeypatch.setattr(market,'datetime',Clock)
 previous=pd.DataFrame([('csi300','2026-10-30',100.)],columns=['id','date','close'])
 requests=[]
 class Response:
  def raise_for_status(self):pass
  def json(self):return {'code':0,'data':{}}
 class Session:
  def get(self,url,params,**kwargs):
   requests.append(params['param'])
   return Response()
 with pytest.raises(ValueError,match='omitted published sessions'):
  market.fetch_prices(Session(),previous)
 assert all(',2026-11-02,' not in x for x in requests)
 assert any(',2026-11-01,' in x for x in requests)
 assert any(x.startswith('sz159919,day,2012-01-01,') for x in requests)
 assert any(x.startswith('sh000300,day,2025-01-01,') for x in requests)
 assert not any(x.startswith('sh000300,day,2012-01-01,') for x in requests)


def test_requested_etfs_are_distinct_instruments():
 from market import SERIES
 expected={'159919','510500','510300','512100','563220','159915','159949','159353','588000','510330','159977','510050'}
 assert expected <= {s['code'] for s in SERIES}
 assert len(SERIES)==len({s['id'] for s in SERIES})==len({s['code'] for s in SERIES})


def test_official_index_publication_lag_does_not_block_new_market_closes(tmp_path):
 from market import SERIES,validate_prices,bias_data
 dates=pd.bdate_range('2025-01-01',periods=70).strftime('%Y-%m-%d')
 frame=pd.DataFrame([(s['id'],d,100.) for s in SERIES for d in dates],columns=['id','date','close'])
 previous=frame[frame.date<dates[-1]]
 lagged=frame[~((frame.id=='all')&(frame.date==dates[-1]))]
 validate_prices(lagged,previous)
 path=tmp_path/'prices.csv';lagged.to_csv(path,index=False)
 values={x['id']:x['rows'] for x in bias_data(path)}
 assert values['all'][-1][0]==dates[-2]
 assert values['csi300'][-1][0]==dates[-1]
 broken=lagged[~((lagged.id=='all')&(lagged.date==dates[-3]))]
 with pytest.raises(ValueError,match='missing or unexpected'):validate_prices(broken)


def test_csi_refresh_retains_verified_history_but_rejects_new_gaps(monkeypatch):
 import market
 from datetime import datetime
 class Clock:
  @staticmethod
  def now(tz):return datetime(2026,11,2,23,0,tzinfo=tz)
 monkeypatch.setattr(market,'datetime',Clock)
 previous=pd.DataFrame([(s['id'],d,100.) for s in market.SERIES for d in ['2026-10-29','2026-10-30']],columns=['id','date','close'])
 class Response:
  def __init__(self,payload):self.payload=payload
  def raise_for_status(self):pass
  def json(self):return self.payload
 class Session:
  def get(self,url,params,**kwargs):
   if 'indexCode' in params:
    code=params['indexCode']
    return Response({'code':200,'data':[{'indexCode':code,'tradeDate':d,'close':101.} for d in ['2026-10-29','2026-11-02']]})
   ticker,_,start,*_=params['param'].split(',')
   bars=[[d,'100','101'] for d in ['2026-10-29','2026-10-30','2026-11-02']] if start.startswith('2026') else []
   return Response({'code':0,'data':{ticker:{'day':bars}}})
 result=market.fetch_prices(Session(),previous)
 assert result.loc[(result.id=='csi2000')&(result.date=='2026-10-30'),'close'].item()==100.
 assert result.loc[(result.id=='all')&(result.date=='2026-11-02'),'close'].item()==101.
 missing=previous[~((previous.id=='csi2000')&(previous.date=='2026-10-30'))]
 with pytest.raises(ValueError,match='missing or unexpected'):
  market.fetch_prices(Session(),missing)


def test_exchange_status_keeps_distinct_dates_and_converts_yuan():
 from refresh import fetch_exchange_status
 class Response:
  def __init__(self,code):self.code=code
  def raise_for_status(self):pass
  def json(self):return {'success':True,'result':{'data':[{'SCDM':self.code,'DIM_DATE':'2026-10-30' if self.code=='001' else '2026-11-02','RZYE':1192247511122,'RQYE':18150205360}]}}
 class Session:
  def get(self,url,params,**kwargs):return Response(params['filter'][6:9])
 result=fetch_exchange_status(Session())
 assert result['001']['date']=='2026-10-30'
 assert result['007']['date']=='2026-11-02'
 assert result['007']['financing_balance_yi']==pytest.approx(11922.47511122)


def test_microcap_official_identity_overlap_and_completed_sessions():
 from market import microcap_prices
 import json
 from datetime import date
 old=pd.DataFrame([('microcap','2026-11-09',14804.3563)],columns=['id','date','close'])
 def payload(rows,code='866006.RI'):return json.dumps({'code':code,'rows':rows})
 fresh=microcap_prices(payload([['2026-11-09',14804.3563],['2026-11-10',15207.1622]]),old,date(2026,11,10))
 assert fresh.date.tolist()==['2026-11-09','2026-11-10']
 assert microcap_prices('',old,date(2026,11,10)).equals(old)
 for rows,code,match in [([['2026-11-10',1]],'wrong','identity'),
                         ([['2026-11-11',1]],'866006.RI','incomplete'),
                         ([['2026-11-09',1]],'866006.RI','revision'),
                         ([['2026-11-10',-1]],'866006.RI','Invalid'),
                         ([['2026-11-10',1],['2026-11-10',1]],'866006.RI','duplicate')]:
  with pytest.raises(ValueError,match=match):microcap_prices(payload(rows,code),old,date(2026,11,10))


def test_microcap_actual_sixty_day_bias_and_source_lag():
 from market import bias_data,PRICE_FILE,validate_prices
 f=pd.read_csv(PRICE_FILE);g=f[f.id=='microcap'].sort_values('date')
 s=next(s for s in bias_data() if s['id']=='microcap')
 assert s['code']=='866006.RI'
 assert s['rows'][0][0]==g.iloc[59].date
 assert s['rows'][-1][1]==pytest.approx((g.iloc[-1].close/g.tail(60).close.mean()-1)*100,abs=1e-6)
 lagged=f[~((f.id=='microcap')&(f.date==g.iloc[-1].date))]
 validate_prices(lagged)
 with pytest.raises(ValueError,match='missing or unexpected'):
  validate_prices(f[~((f.id=='microcap')&(f.date==g.iloc[-3].date))])


def test_workstation_dispatch_supplies_official_data_without_shell_interpolation(monkeypatch):
 import launch_refresh,json
 from types import SimpleNamespace
 calls=[]
 def run(args,**kwargs):
  calls.append((args,kwargs))
  return SimpleNamespace(stdout=json.dumps({'code':'866006.RI','rows':[['2026-11-10',15207.1622]]}))
 monkeypatch.setattr(launch_refresh.subprocess,'run',run)
 launch_refresh.main()
 assert calls[0][0][0]=='ssh'
 assert calls[1][0][:3]==['gh','workflow','run']
 payload=json.loads(json.loads(calls[1][1]['input'])['microcap'])
 assert payload['code']=='866006.RI'
 assert payload['rows']==[['2026-11-10',15207.1622]]
 assert all(c[1]['check'] for c in calls)
