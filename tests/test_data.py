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
 assert rows[0][0]==f.iloc[20]['date']
 assert rows[0][1]==20
 assert rows[0][2]==100
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
