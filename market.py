"""Public daily prices and the agreed previous-close-filled 60-session BIAS."""
from pathlib import Path
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT=Path(__file__).resolve().parent
PRICE_FILE=ROOT/'data/market_closes.csv'
# Exact source identifiers; ETF series use unadjusted exchange prices.
SERIES=[
    dict(id='all',name='中证全指',code='000985',secid='1.000985',color='#233c51'),
    dict(id='star',name='科创50ETF',code='588000',secid='1.588000',color='#a34c66'),
    dict(id='chinext',name='创业板ETF',code='159915',secid='0.159915',color='#9a6b00'),
    dict(id='csi300',name='沪深300',code='000300',secid='1.000300',color='#367b9f'),
    dict(id='csi500',name='中证500',code='000905',secid='1.000905',color='#287b70'),
    dict(id='csi1000',name='中证1000',code='000852',secid='1.000852',color='#765a9b'),
    dict(id='csi2000',name='中证2000',code='932000',secid='2.932000',color='#c16c3a'),
]

def validate_prices(frame,previous=None):
    if frame.empty or frame.duplicated(['id','date']).any():
        raise ValueError('Empty or duplicate market prices')
    pd.to_datetime(frame['date'],format='%Y-%m-%d',errors='raise')
    if not frame['close'].map(lambda v:pd.notna(v) and math.isfinite(v) and v>0).all():
        raise ValueError('Market prices must be finite and positive')
    expected={s['id'] for s in SERIES}
    if set(frame['id'])!=expected:raise ValueError('Market series identities do not match configuration')
    calendar=set(frame.loc[frame.id=='csi300','date'])
    # 159915 was suspended for its holders' meeting on 2021-02-08 (exchange notice).
    confirmed_no_trade={'chinext':{'2021-02-08'}}
    for key,g in frame.groupby('id'):
        dates=set(g.date);lo,hi=min(dates),max(dates)
        if dates!={d for d in calendar if lo<=d<=hi}-confirmed_no_trade.get(key,set()):raise ValueError(f'{key}: missing or unexpected trading sessions')
        if hi!=max(calendar):raise ValueError(f'{key}: source is stale relative to CSI300')
    if previous is not None:
        old=set(zip(previous.id,previous.date));new=set(zip(frame.id,frame.date))
        if not old<=new:raise ValueError('Price refresh would remove published history')

def fetch_prices(session,previous=None):
    end=datetime.now(ZoneInfo('Asia/Shanghai')).date()
    # Existing history is immutable; refresh the recent overlap from the same source.
    first_year=2012 if previous is None else max(2012,int(previous.date.max()[:4])-1)
    tasks=[]
    for spec in SERIES:
        if spec['id'] in ('csi2000','all'):continue
        ticker=('sh' if spec['secid'].startswith('1.') else 'sz')+spec['code']
        for year in range(first_year,end.year+1):tasks.append((spec,ticker,year))
    def tencent(task):
        spec,ticker,year=task
        response=session.get('https://ifzq.gtimg.cn/appstock/app/fqkline/get',params={
            'param':f'{ticker},day,{year}-01-01,{min(str(end),str(year)+"-12-31")},640,'},timeout=(10,25))
        response.raise_for_status();payload=response.json()
        if payload.get('code')!=0:raise ValueError(f'Tencent rejected {ticker}: {payload}')
        bars=payload.get('data',{}).get(ticker,{}).get('day',[])
        return [(spec['id'],r[0],float(r[2])) for r in bars if r[0].startswith(str(year))]
    with ThreadPoolExecutor(max_workers=4) as pool:parts=list(pool.map(tencent,tasks))
    frame=pd.DataFrame([row for part in parts for row in part],columns=['id','date','close'])
    if previous is not None:
        overlap=previous.loc[(previous.date>=f'{first_year}-01-01') & ~previous.id.isin(['csi2000','all'])]
        if not set(zip(overlap.id,overlap.date))<=set(zip(frame.id,frame.date)):
            raise ValueError('Tencent refresh omitted published sessions in the requested overlap')
    if previous is not None:
        frame=pd.concat([previous.loc[~previous.id.isin(['csi2000','all'])],frame]).drop_duplicates(['id','date'],keep='last')
    calendar=set(frame.loc[frame.id=='csi300','date'])
    for key,code in [('csi2000','932000'),('all','000985')]:
        response=session.get('https://www.csindex.com.cn/csindex-home/perf/index-perf',params={
            'indexCode':code,'startDate':f'{first_year}0101','endDate':end.strftime('%Y%m%d')},timeout=(10,40))
        response.raise_for_status();payload=response.json()
        if str(payload.get('code'))!='200' or not payload.get('data'):raise ValueError(f'CSI source rejected: {payload}')
        csi=[]
        for r in payload['data']:
            if r['indexCode']!=code:raise ValueError('Incorrect CSI index identity')
            date=pd.Timestamp(r['tradeDate']).strftime('%Y-%m-%d')
            # Official API may carry non-trading-date snapshots; use the exchange calendar.
            if date in calendar:csi.append((key,date,float(r['close'])))
        if previous is not None:
            expected=set(previous.loc[(previous.id==key) & (previous.date>=f'{first_year}-01-01'),'date'])
            if not expected<={row[1] for row in csi}:raise ValueError(f'{key}: CSI refresh omitted published sessions')
        frame=pd.concat([frame,pd.DataFrame(csi,columns=['id','date','close'])])
    if previous is not None:frame=pd.concat([previous,frame]).drop_duplicates(['id','date'],keep='last')
    frame=frame.sort_values(['id','date']).reset_index(drop=True)
    validate_prices(frame,previous)
    return frame

def bias_data(path=PRICE_FILE):
    frame=pd.read_csv(path,dtype={'id':str,'date':str});validate_prices(frame)
    result=[]
    for spec in SERIES:
        g=frame.loc[frame.id==spec['id']].sort_values('date')
        # At date t, the window consists of t-59..t-1 plus a second copy of t-1.
        # Today's actual close is deliberately never part of today's calculation.
        previous=g.close.shift(1)
        average=(g.close.shift(1).rolling(59,min_periods=59).sum()+previous)/60
        bias=(previous/average-1)*100
        prev_date=g.date.shift(1);start_date=g.date.shift(59)
        rows=[[d,round(float(b),6),round(float(c),8),round(float(m),8),p,a]
              for d,b,c,m,p,a in zip(g.date,bias,previous,average,prev_date,start_date) if pd.notna(b)]
        result.append({**spec,'rows':rows})
    return result
