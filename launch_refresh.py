"""Supply official microcap observations, then trigger the existing Pages job."""
import json
import subprocess


def main():
    # Reuse the production dashboard's authenticated RiceQuant cache. Credentials
    # and SSH access remain on the workstation, never in the public repository.
    export = """import pandas as pd,json,sys
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,"/mnt/data/experiments/behavioral_alpha_strategy/scripts")
from rq_source import query_csv
p=pd.read_parquet('/mnt/data/experiments/behavioral_alpha_strategy/state/display_benchmarks/microcap_daily.parquet').sort_values('date').tail(500)
payload={'code':'866006.RI','rows':[[str(d)[:10],float(c)] for d,c in p[['date','close']].itertuples(index=False,name=None)]}
now=datetime.now(ZoneInfo('Asia/Shanghai'))
end=now.date() if now.hour>=15 else now.date()-timedelta(days=1)
start=end-timedelta(days=45)
code=f"import rqdatac;rqdatac.init();df=rqdatac.get_price(['932000.INDX','000985.XSHG'],'{start}','{end}',frequency='1d',fields=['close'],adjust_type='none',expect_df=True).reset_index();df.to_csv('__OUTPUT__',index=False);print('MARGIN_INDEX_OK')"
f=query_csv(code,'MARGIN_INDEX_OK','margin_index.csv',timeout=60).to_pandas()
payload['indices']={key:{'code':code,'rows':[[str(d)[:10],float(c)] for d,c in f.loc[f.order_book_id==code,['date','close']].itertuples(index=False,name=None)]} for key,code in [('csi2000','932000.INDX'),('all','000985.XSHG')]}
print(json.dumps(payload,separators=(',',':')))
"""
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',
        'ali-gpu','/opt/aiext/bin/python3 -'],input=export,text=True,
        capture_output=True,check=True,timeout=80)
    payload=json.loads(result.stdout)
    if payload['code']!='866006.RI' or not payload['rows']:
        raise ValueError('Missing official microcap export')
    subprocess.run(['gh','workflow','run','update.yml','--repo',
        'tztzpub/margin-balance-monitor','--json'],
        input=json.dumps({'microcap':json.dumps(payload,separators=(',',':'))}),
        text=True,check=True,timeout=30)


if __name__=='__main__':main()
