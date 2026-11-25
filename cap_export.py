"""Executed on the workstation's data host by launch_refresh.py."""
def export_recent_caps(end):
    import polars as pl
    from datetime import timedelta
    from production_contract import ROOT
    from rq_source import query_csv
    keys = ['date', 'symbol']
    start = end - timedelta(days=21)
    cap_members = pl.scan_parquet(ROOT/'runtime/shadow/micro200/membership.parquet').filter(
        pl.col('date').is_between(pl.lit(str(start)), pl.lit(str(end))))
    master = pl.scan_parquet(ROOT/'source/security_master.parquet').select('symbol','de_listed_date')
    members = cap_members.join(master,on='symbol',validate='m:1').filter(
        pl.col('de_listed_date').is_null() | (pl.col('de_listed_date') > pl.col('date'))
    ).select(keys).collect()
    ids = sorted(set(members['symbol']))
    code = f"""import rqdatac as rq
rq.init()
rq.get_factor({ids!r}, ['market_cap_3'], start_date='{start}', end_date='{end}').reset_index().to_csv('__OUTPUT__',index=False)
print('MARGIN_CAP_OK')
"""
    caps = query_csv(code,'MARGIN_CAP_OK','margin_micro400_cap.csv',timeout=60).select(
        pl.col('date').cast(pl.String).str.slice(0,10),pl.col('order_book_id').alias('symbol'),'market_cap_3')
    # A still unpublished session has no marks. A partially returned session is an error.
    daily = members.filter(pl.col('date')<=caps['date'].max()).join(caps,on=keys,how='left',validate='1:1')
    if daily.is_empty() or not daily['market_cap_3'].is_finite().fill_null(False).all() or daily['market_cap_3'].min()<=0:
        raise ValueError('Incomplete micro400 closing capitalization')
    return daily.group_by('date').agg(pl.len(),pl.col('market_cap_3').mean()/1e8).sort('date').rows()
