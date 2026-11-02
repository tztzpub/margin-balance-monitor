"""Public daily closing prices and contemporaneous 60-session BIAS."""
from pathlib import Path
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT=Path(__file__).resolve().parent
PRICE_FILE=ROOT/'data/market_closes.csv'
# Exact source identifiers; ETF series use unadjusted exchange prices.
SERIES=[
    dict(id='all',name='中证全指',code='000985',secid='1.000985',color='#233c51'),
    dict(id='star',name='科创50ETF华夏',code='588000',secid='1.588000',color='#a34c66'),
    dict(id='chinext',name='创业板ETF易方达',code='159915',secid='0.159915',color='#9a6b00'),
    dict(id='csi300',name='沪深300',code='000300',secid='1.000300',color='#367b9f'),
    dict(id='csi500',name='中证500',code='000905',secid='1.000905',color='#287b70'),
    dict(id='csi1000',name='中证1000',code='000852',secid='1.000852',color='#765a9b'),
    dict(id='csi2000',name='中证2000',code='932000',secid='2.932000',color='#c16c3a'),
    dict(id='etf159919',name='沪深300ETF嘉实',code='159919',secid='0.159919',color='#537eaa',default=False),
    dict(id='etf510500',name='中证500ETF南方',code='510500',secid='1.510500',color='#549a86',default=False),
    dict(id='etf510300',name='沪深300ETF华泰柏瑞',code='510300',secid='1.510300',color='#5370aa',default=False),
    dict(id='etf512100',name='中证1000ETF南方',code='512100',secid='1.512100',color='#927bb2',default=False),
    dict(id='etf563220',name='A500ETF富国',code='563220',secid='1.563220',color='#a87950',default=False),
    dict(id='etf159949',name='创业板50ETF华安',code='159949',secid='0.159949',color='#b18d28',default=False),
    dict(id='etf159353',name='中证A500ETF景顺',code='159353',secid='0.159353',color='#8c684c',default=False),
    dict(id='etf510330',name='沪深300ETF华夏',code='510330',secid='1.510330',color='#6f9ba8',default=False),
    dict(id='etf159977',name='创业板ETF天弘',code='159977',secid='0.159977',color='#9c854a',default=False),
    dict(id='etf510050',name='上证50ETF华夏',code='510050',secid='1.510050',color='#9b697b',default=False),
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
    # Confirmed fund-share conversion suspensions; never fill fabricated closes.
    # 159919: https://pdf.dfcfw.com/pdf/H2_AN201211280005620515_1.pdf
    # and https://www.cindasc.com/osoa/views/a/20190111/37173.html
    # 510500: https://pdf.dfcfw.com/pdf/H2_AN201504030009077187_1.pdf
    # 512100: https://www.finet.hk/newscenter/news_content/63159b2b53243c06f120c1ae
    confirmed_no_trade={'chinext':{'2021-02-08'},
        'etf159919':{'2012-11-30','2019-01-11'},
        'etf510500':{'2015-04-13','2015-04-14'},'etf512100':{'2022-09-02'}}
    for key,g in frame.groupby('id'):
        dates=set(g.date);lo,hi=min(dates),max(dates)
        expected_dates={d for d in calendar if lo<=d<=hi}-confirmed_no_trade.get(key,set())
        if dates!=expected_dates:raise ValueError(f'{key}: missing or unexpected trading sessions; missing={sorted(expected_dates-dates)}, extra={sorted(dates-expected_dates)}')
        # Official CSI publication can lag Tencent. Preserve its true endpoint;
        # never hold back other published closes or fill forward a stale index.
        if key not in ('all','csi2000') and hi!=max(calendar):
            raise ValueError(f'{key}: source is stale relative to CSI300')
    if previous is not None:
        old=set(zip(previous.id,previous.date));new=set(zip(frame.id,frame.date))
        if not old<=new:raise ValueError('Price refresh would remove published history')

def fetch_prices(session,previous=None):
    now=datetime.now(ZoneInfo('Asia/Shanghai'))
    end=now.date() if now.hour>=15 else now.date()-timedelta(days=1)
    # Existing history is immutable; refresh the recent overlap from the same source.
    first_year=2012 if previous is None else max(2012,int(previous.date.max()[:4])-1)
    tasks=[]
    for spec in SERIES:
        if spec['id'] in ('csi2000','all'):continue
        ticker=('sh' if spec['secid'].startswith('1.') else 'sz')+spec['code']
        series_first=first_year if previous is not None and spec['id'] in set(previous.id) else 2012
        for year in range(series_first,end.year+1):tasks.append((spec,ticker,year))
    def tencent(task):
        spec,ticker,year=task
        response=session.get('https://ifzq.gtimg.cn/appstock/app/fqkline/get',params={
            'param':f'{ticker},day,{year}-01-01,{min(str(end),str(year)+"-12-31")},640,'},timeout=(10,25))
        response.raise_for_status();payload=response.json()
        if payload.get('code')!=0:raise ValueError(f'Tencent rejected {ticker}: {payload}')
        bars=payload.get('data',{}).get(ticker,{}).get('day',[])
        return [(spec['id'],r[0],float(r[2])) for r in bars if r[0].startswith(str(year)) and r[0]<=str(end)]
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
            omitted=expected-{row[1] for row in csi}
            if omitted:
                # Retain already verified closes from this same source. The final
                # validation still rejects gaps for sessions never downloaded.
                print(f'{key}: retaining published CSI closes omitted by response: {sorted(omitted)}')
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
        # Each completed session uses its own close and the 60 closes ending there.
        average=g.close.rolling(60,min_periods=60).mean()
        bias=(g.close/average-1)*100
        start_date=g.date.shift(59)
        rows=[[d,round(float(b),6),round(float(c),8),round(float(m),8),p,a]
              for d,b,c,m,p,a in zip(g.date,bias,g.close,average,g.date,start_date) if pd.notna(b)]
        result.append({**spec,'rows':rows})
    return result
