"""Fetch the complete public Choice account series; fail before replacing good data."""
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from market import fetch_prices,PRICE_FILE

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data/financing_accounts_daily.csv'
URL='https://datacenter-web.eastmoney.com/api/data/v1/get'
FIELDS={'FIN_BALANCE':'financing_balance_yi','FIN_BUY_AMT':'financing_buy_yi','LOAN_BALANCE':'securities_lending_balance_yi'}

def validate(frame,previous=None):
    if frame.empty or frame['date'].duplicated().any():raise ValueError('Empty or duplicate account observations')
    pd.to_datetime(frame['date'],format='%Y-%m-%d',errors='raise')
    numbers=frame[list(FIELDS.values())]
    if numbers.isna().any().any() or not numbers.map(lambda x: math.isfinite(x)).all().all():raise ValueError('Missing or nonfinite account balances')
    if (frame[['financing_balance_yi','securities_lending_balance_yi']]<=0).any().any() or (frame['financing_buy_yi']<0).any():raise ValueError('Invalid account balances or purchase amount')
    if previous is not None and not set(previous['date'])<=set(frame['date']):raise ValueError('Source response would remove previously published history')

def fetch(session):
    records=[];page=1;expected=None
    while True:
        response=session.get(URL,params=dict(reportName='RPTA_WEB_MARGIN_DAILYTRADE',columns='ALL',pageSize=500,pageNumber=page,sortColumns='STATISTICS_DATE',sortTypes=-1),timeout=(10,40))
        response.raise_for_status();payload=response.json()
        if not payload.get('success') or not payload.get('result'):raise ValueError(f'Eastmoney API rejected page {page}: {payload}')
        result=payload['result']
        if expected is None:expected=int(result['count'])
        if int(result['count'])!=expected:raise ValueError('Source changed while paginating; retry the refresh')
        if not result['data']:raise ValueError('Unexpected empty page')
        records.extend(result['data'])
        if page>=int(result['pages']):break
        page+=1
    if len(records)!=expected:raise ValueError('Incomplete source pagination')
    f=pd.DataFrame(records);f['date']=f['STATISTICS_DATE'].str[:10]
    return f[['date',*FIELDS]].rename(columns=FIELDS).sort_values('date').reset_index(drop=True)

def main():
    session=requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; MarginBalanceMonitor/1.0)','Referer':'https://data.eastmoney.com/'})
    retry=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])
    session.mount('https://',HTTPAdapter(max_retries=retry))
    previous_prices=pd.read_csv(PRICE_FILE,dtype={'id':str,'date':str}) if PRICE_FILE.exists() else None
    with session:
        f=fetch(session)
        prices=fetch_prices(session,previous_prices)
    if prices.date.max()<f.date.max():raise ValueError('Market quotes lag the margin data publication date')
    previous=pd.read_csv(DATA) if DATA.exists() else None
    validate(f,previous)
    temporary=PRICE_FILE.with_suffix('.tmp');prices.to_csv(temporary,index=False);temporary.replace(PRICE_FILE)
    temporary=DATA.with_suffix('.tmp');f.to_csv(temporary,index=False);temporary.replace(DATA)
    status=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),source_last_date=f['date'].max(),record_count=len(f),market_last_date=prices.date.max(),market_dates=prices.groupby('id')['date'].max().to_dict())
    status_path=ROOT/'data/status.json';temporary=status_path.with_suffix('.tmp');temporary.write_text(json.dumps(status,indent=2)+'\n');temporary.replace(status_path)
    print(json.dumps(status))
if __name__=='__main__':main()
