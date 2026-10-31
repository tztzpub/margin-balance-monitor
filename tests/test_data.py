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


def test_bias_uses_previous_close_twice_not_today(tmp_path):
 from market import bias_data,SERIES
 dates=pd.bdate_range('2025-01-01',periods=70).strftime('%Y-%m-%d')
 frame=pd.DataFrame([(s['id'],d,float(i+100)) for s in SERIES for i,d in enumerate(dates)],columns=['id','date','close'])
 path=tmp_path/'prices.csv';frame.to_csv(path,index=False)
 before=bias_data(path)[0]['rows']
 assert before[0][0]==dates[59]
 assert before[0][1]==pytest.approx((158/((sum(range(100,159))+158)/60)-1)*100,abs=1e-6)
 assert before[0][4]==dates[58]
 frame.loc[frame.date==dates[-1],'close']=999999
 frame.to_csv(path,index=False)
 assert bias_data(path)[0]['rows'][-1]==before[-1]


def test_market_missing_day_cannot_silently_shorten_window(tmp_path):
 from market import validate_prices,SERIES
 dates=pd.bdate_range('2025-01-01',periods=70).strftime('%Y-%m-%d')
 frame=pd.DataFrame([(s['id'],d,100.) for s in SERIES for d in dates],columns=['id','date','close'])
 validate_prices(frame)
 with pytest.raises(ValueError,match='trading sessions'):validate_prices(frame.loc[~((frame.id=='star')&(frame.date==dates[20]))])


def test_october_30_bias_reproduces_supplied_numbers():
 from market import bias_data
 expected={'all':-11.11,'star':-21.32,'chinext':-21.81,'csi300':-9.2,'csi500':-13.98,'csi1000':-13.14,'csi2000':-11.16}
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
