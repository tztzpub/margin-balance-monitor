"""Supply official microcap observations, then trigger the existing Pages job."""
import json
import subprocess


def main():
    # Reuse the production dashboard's authenticated RiceQuant cache. Credentials
    # and SSH access remain on the workstation, never in the public repository.
    export = """import pandas as pd,json
p=pd.read_parquet('/mnt/data/experiments/behavioral_alpha_strategy/state/display_benchmarks/microcap_daily.parquet').sort_values('date').tail(500)
print(json.dumps({'code':'866006.RI','rows':[[str(d)[:10],float(c)] for d,c in p[['date','close']].itertuples(index=False,name=None)]},separators=(',',':')))
"""
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',
        'ali-gpu','/opt/aiext/bin/python3 -'],input=export,text=True,
        capture_output=True,check=True,timeout=45)
    payload=json.loads(result.stdout)
    if payload['code']!='866006.RI' or not payload['rows']:
        raise ValueError('Missing official microcap export')
    subprocess.run(['gh','workflow','run','update.yml','--repo',
        'tztzpub/margin-balance-monitor','--json'],
        input=json.dumps({'microcap':json.dumps(payload,separators=(',',':'))}),
        text=True,check=True,timeout=30)


if __name__=='__main__':main()
