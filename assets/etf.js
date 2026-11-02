// Public Tencent minute data; every amount is reported turnover, never price × volume.
const ETFMonitor=(()=>{
const minute=t=>Number(t.slice(0,2))*60+Number(t.slice(2,4));
const session=m=>m>=570&&m<=690?0:m>=780&&m<=900?1:-1;
function parseDay(day){
 const points=new Map();let last=-1;
 for(const line of day.data){const p=line.trim().split(/\s+/),m=minute(p[0]),a=Number(p[3]);
  if(session(m)<0)continue;
  if(!Number.isFinite(a)||a<0||a<last)throw Error('分钟成交额无效');
  points.set(m,a);last=a;
 }
 return {date:day.date,points};
}
function windowAmount(points,m){
 if(session(m)<0||session(m)!==session(m-15)||!points.has(m)||!points.has(m-15))return null;
 return points.get(m)-points.get(m-15);
}
function summarize(days,today,time){
 const current=days.find(d=>d.date===today),history=days.filter(d=>d.date<today).sort((a,b)=>a.date.localeCompare(b.date)).slice(-4);
 const complete=history.filter(d=>d.points.has(900));
 const out={n:complete.length,yesterday:complete.at(-1)?.points.get(900),average:complete.length?complete.reduce((a,d)=>a+d.points.get(900),0)/complete.length:null,ratio:null,best:null,duration:0};
 if(!current||!complete.length)return out;
 const cutoff=minute(time);const moments=[...current.points.keys()].filter(m=>m<cutoff||cutoff>=900&&m===900).sort((a,b)=>a-b);
 const latest=moments.at(-1);
 if(complete.every(d=>d.points.has(latest))){const base=complete.reduce((a,d)=>a+d.points.get(latest),0)/complete.length;out.ratio=base>0?current.points.get(latest)/base:null;}
 let run=0,prior=-2;
 for(const m of moments){const amount=windowAmount(current.points,m),bases=complete.map(d=>windowAmount(d.points,m));
  if(amount===null||bases.some(x=>x===null)){run=0;continue;}
  const base=bases.reduce((a,b)=>a+b,0)/bases.length,ratio=base>0?amount/base:null;
  if(ratio!==null&&(!out.best||ratio>out.best.ratio))out.best={minute:m,ratio,amount};
  run=ratio>=2?(m===prior+1?run+1:1):0;out.duration=Math.max(out.duration,run);prior=m;
 }
 return out;
}
function quote(fields,code){
 if(!fields||fields[2]!==code||!/^\d{14}$/.test(fields[30]))throw Error('行情代码或时间无效');
 const price=Number(fields[3]),previous=Number(fields[4]),parts=fields[35].split('/'),amount=Number(parts[2]);
 if(!(price>0&&previous>0&&Number.isFinite(amount)&&amount>=0))throw Error('行情价格或成交额无效');
 return {price,change:(price/previous-1)*100,amount,stamp:fields[30]};
}
const fmt=(v,d=2)=>v==null||!Number.isFinite(v)?'—':v.toFixed(d),money=v=>v==null?'—':fmt(v/1e8),clock=m=>String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
async function json(url){const r=await fetch(url,{signal:AbortSignal.timeout(12000),cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const p=await r.json();if(p.code!==0)throw Error(p.msg||'行情接口错误');return p.data;}
function mount(specs){
 const host=document.querySelector('#etf-monitor'),tbody=host.querySelector('tbody'),status=host.querySelector('.etf-status');
 const records=specs.map(s=>({...s,ticker:(s.secid.startsWith('1.')?'sh':'sz')+s.code,q:null,history:[],historyDate:null,stats:null,error:null}));
 let running=false,sortKey='ratio',descending=true,paused=false;
 function render(){
  const value=(r,k)=>k==='code'?r.code:k==='price'||k==='change'||k==='amount'?r.q?.[k]:k==='best'?r.stats?.best?.ratio:k==='duration'?r.stats?.duration:r.stats?.[k];
  const sorted=[...records].sort((a,b)=>{const x=value(a,sortKey),y=value(b,sortKey);if(x==null)return y==null?0:1;if(y==null)return -1;return (typeof x==='string'?x.localeCompare(y):x-y)*(descending?-1:1)});
  const now=Date.now();
  tbody.innerHTML=sorted.map(r=>{const q=r.q,s=r.stats||{},stamp=q?.stamp,t=stamp?stamp.slice(8,10)+':'+stamp.slice(10,12)+':'+stamp.slice(12,14):'—';
   const date=stamp?stamp.slice(0,4)+'-'+stamp.slice(4,6)+'-'+stamp.slice(6,8):'';
   const age=stamp?(now-Date.parse(date+'T'+t+'+08:00'))/1000:Infinity;
   const beijing=new Date(now+8*3600000),m=beijing.getUTCHours()*60+beijing.getUTCMinutes(),weekday=beijing.getUTCDay();
   const trading=weekday>0&&weekday<6&&session(m)>=0;
   const old=trading&&age>120,label=r.error?'连接异常':!q?'连接中':old?'行情延迟':m>690&&m<780?'午间休市':!trading?'非交易时段':'更新中';
   return `<tr data-code="${r.code}"><td>${r.name}</td><td class="code">${r.code}</td><td>${fmt(q?.price,3)}</td><td class="${q?.change>0?'rise':'fall'}">${q? (q.change>0?'+':'')+fmt(q.change)+'%':'—'}</td><td>${money(q?.amount)}</td><td>${money(s.yesterday)}</td><td title="${s.n||0}个完整交易日">${money(s.average)}</td><td class="${s.ratio>=2?'hot':''}">${s.ratio==null?'—':fmt(s.ratio)+'×'}</td><td class="${s.best?.ratio>=2?'hot':''}">${s.best?`<small>${clock(s.best.minute)}</small> ${fmt(s.best.ratio)}×`:'—'}</td><td>${s.duration? s.duration+'分':'—'}</td><td class="quote-time" title="${date} 北京时间">${t}</td><td><span class="state ${old||r.error?'warning':''}" title="${r.error?'实时请求失败，保留上次行情；下轮自动重试':''}">${label}</span></td></tr>`;
  }).join('');
 }
 async function update(r){
  try{
   const raw=(await json('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code='+r.ticker+'&_='+Date.now()))[r.ticker];
   const q=quote(raw.qt?.[r.ticker],r.code),date=q.stamp.slice(0,8);
   if(r.q&&q.stamp<r.q.stamp)throw Error('行情时间倒退');
   r.q=q;
   if(r.historyDate!==date){const history=(await json('https://web.ifzq.gtimg.cn/appstock/app/day/query?code='+r.ticker+'&_='+Date.now()))[r.ticker];r.history=history.data.map(parseDay).filter(d=>d.date<date);r.historyDate=date;}
   const current=parseDay({date:raw.data.date,data:raw.data.data});
   if(current.date!==date)throw Error('分时日期不一致');
   r.stats=summarize([...r.history,current],date,q.stamp.slice(8,12));r.error=null;
  }catch(e){r.error=e.message;console.warn('ETF '+r.code,e.message);}
 }
 async function refresh(){
  if(running||paused||document.hidden)return;running=true;status.textContent='正在更新';
  let index=0;
  await Promise.all(Array.from({length:4},async()=>{while(index<records.length){await update(records[index++]);render();}}));
  running=false;const failed=records.filter(r=>r.error).length;
  const latest=records.map(r=>r.q?.stamp||'').sort().at(-1);
  const date=latest?latest.slice(0,4)+'-'+latest.slice(4,6)+'-'+latest.slice(6,8)+' · ':'';
  status.textContent=failed?`${failed}只连接异常 · 自动重试`:date+'每15秒刷新 · 北京时间';
 }
 host.querySelectorAll('th button').forEach(b=>b.addEventListener('click',()=>{descending=sortKey===b.dataset.sort?!descending:true;sortKey=b.dataset.sort;host.querySelectorAll('th').forEach(th=>th.removeAttribute('aria-sort'));b.closest('th').setAttribute('aria-sort',descending?'descending':'ascending');render();}));
 host.querySelector('.etf-refresh').addEventListener('click',refresh);
 host.querySelector('.etf-pause').addEventListener('click',e=>{paused=!paused;e.target.textContent=paused?'继续刷新':'暂停刷新';status.textContent=paused?'自动刷新已暂停':'正在更新';if(!paused)refresh();});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
 render();refresh();setInterval(refresh,15000);
}
return {parseDay,windowAmount,summarize,quote,mount};})();
ETFMonitor.mount(JSON.parse(document.getElementById('etf-specs').textContent));
