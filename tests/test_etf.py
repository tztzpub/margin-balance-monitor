from pathlib import Path
from playwright.sync_api import sync_playwright


def test_minute_math_uses_same_clock_no_lunch_no_incomplete_minute():
    script=(Path(__file__).resolve().parents[1]/'assets/etf.js').read_text().split('ETFMonitor.mount(')[0]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page();page.add_script_tag(content=script)
        result=page.evaluate('''()=>{
          function day(date,mult){const data=[];for(let m=570;m<=690;m++)data.push(String(Math.floor(m/60)).padStart(2,'0')+String(m%60).padStart(2,'0')+' 1 1 '+((m-569)*100*mult));return ETFMonitor.parseDay({date,data});}
          const h=day('20261030',1);h.points.set(900,24000);
          const t=day('20261102',3);
          const s=ETFMonitor.summarize([h,t],'20261102','1000');
          const lunch=new Map([[680,100],[695,200],[775,300],[790,400]]);
          return {ratio:s.ratio,best:s.best,yesterday:s.yesterday,n:s.n,lunch:ETFMonitor.windowAmount(lunch,695),lunch2:ETFMonitor.windowAmount(lunch,790)};
        }''')
        assert result['ratio']==3
        assert result['best']['ratio']==3
        assert result['best']['minute']<600
        assert result['yesterday']==24000 and result['n']==1
        assert result['lunch'] is None and result['lunch2'] is None
        assert page.evaluate('''()=>{try{ETFMonitor.parseDay({date:'20261102',data:['0930 1 1 100','0931 1 1 99']});return false}catch{return true}}''')
        assert page.evaluate('''()=>{try{ETFMonitor.quote(['51','基金','BAD'],'159919');return false}catch{return true}}''')
        browser.close()
