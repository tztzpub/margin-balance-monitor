"""Self-contained financing/lending change-rate panel from the canonical Choice series."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data'
HTML=ROOT/'index.html'

def chart_data(path=OUT/'financing_accounts_daily.csv'):
    f=pd.read_csv(path,parse_dates=['date']).sort_values('date').set_index('date')
    columns=['financing_balance_yi','securities_lending_balance_yi']
    if f.index.duplicated().any() or f[columns].isna().any().any() or (f[columns]<=0).any().any():
        raise ValueError('Financing/lending series must contain unique dates and positive complete balances')
    changes=f[columns].pct_change(20,fill_method=None).dropna()*100
    return [[d.strftime('%Y-%m-%d'),round(float(a),6),round(float(b),6)] for d,a,b in changes.itertuples(name=None)]

CSS='''
main{max-width:1480px;padding:38px 48px 30px}header{padding:22px 0 20px}h1{font-size:32px}header p{justify-content:space-between;margin-top:8px}.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px 24px;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:14px 0;margin:0 0 24px}.ranges{display:flex;flex-wrap:wrap;gap:4px}.ranges button,.reset{font:500 12px var(--sans);border:1px solid transparent;color:var(--muted);background:transparent;padding:8px 11px;min-height:36px;border-radius:3px;cursor:pointer;transition:background .15s,color .15s}.ranges button:hover,.reset:hover{background:var(--wash);color:var(--ink)}.ranges button[aria-pressed=true]{background:var(--ink);color:#fff}.dates{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}.dates label{display:flex;align-items:center;gap:7px}.dates input{font:12px var(--sans);color:var(--ink);background:#fff;border:1px solid var(--rule);border-radius:3px;padding:7px 8px;min-width:0;min-height:36px;width:139px}.date-error{margin:-12px 0 12px;font-size:12px;color:#aa4939}.date-error:empty{display:none}.panel{margin:0 0 24px;padding:0 0 20px;border-bottom:1px solid var(--rule)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}.panel h2{margin:0;font-size:18px;display:flex;align-items:center;gap:10px}.swatch{display:inline-block;flex:none;width:24px;height:12px;background:var(--series)}.reading{display:flex;align-items:baseline;gap:14px;white-space:nowrap}.reading time{font-size:12px;color:var(--muted)}.reading strong{font-size:23px;line-height:1.3;letter-spacing:-.02em;font-weight:500;color:var(--series);min-width:96px;text-align:right}.plot{position:relative;height:290px;touch-action:pan-y}.plot svg{width:100%;height:100%;display:block;overflow:hidden;user-select:none}.plot text{font:11px var(--sans);fill:var(--muted)}.plot .series{stroke-width:1.7;stroke-linejoin:round;stroke-linecap:round}.plot .crosshair{pointer-events:none}.plot .axis-hit{cursor:ns-resize;touch-action:none}.plot:focus-visible{outline:2px solid var(--blue);outline-offset:3px}.plot .axis-hit:focus-visible{outline:none;stroke:var(--blue)}.panel-bottom{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:2px;gap:12px}.reset{font-size:11px;min-height:30px;padding:4px 8px}.axis-note{color:#7b8a95}.footer-note{font-size:11px;color:var(--muted);display:flex;justify-content:space-between;gap:8px 24px;flex-wrap:wrap;line-height:1.7;padding-top:0;margin-top:0;border:0}button:focus-visible,input:focus-visible{outline-offset:2px}@media(max-width:650px){main{padding:24px 16px 24px}header{padding:18px 0 16px}h1{font-size:27px}header p{font-size:11px;gap:3px 12px}.toolbar{padding:10px 0;gap:10px;margin-bottom:20px}.ranges{gap:3px}.ranges button{font-size:11px;padding:7px 10px;min-height:36px}.dates{width:100%;gap:8px;justify-content:space-between}.dates label{gap:5px}.dates input{width:126px;font-size:11px;padding:6px}.panel{margin-bottom:20px;padding-bottom:12px}.panel h2{font-size:16px;gap:8px}.reading{gap:8px}.reading time{font-size:10px}.reading strong{font-size:19px;min-width:78px}.plot{height:250px}.plot text{font-size:10px}.panel-bottom{font-size:10px}.axis-note{max-width:190px}.footer-note{font-size:10px;gap:5px}.panel-head{gap:8px}}@media(max-width:370px){.dates input{width:119px}.panel-head{align-items:flex-start}.reading{flex-direction:column;align-items:flex-end;gap:1px}.reading strong{font-size:19px}.plot{height:235px}}@media(max-width:340px){.dates label{flex-direction:column;align-items:flex-start;gap:3px;white-space:nowrap}.dates input{width:134px}}@media print{.toolbar,.panel-bottom{display:none}.plot{height:260px}.panel{break-inside:avoid}}
'''

JS=r'''
const DATA=JSON.parse(document.getElementById('series-data').textContent),NS='http://www.w3.org/2000/svg';
const first=DATA[0][0],last=DATA.at(-1)[0],stamp=d=>Date.parse(d+'T00:00:00Z'),iso=t=>new Date(t).toISOString().slice(0,10);
const from=document.getElementById('from'),to=document.getElementById('to'),error=document.getElementById('date-error');
let state={from:Math.max(stamp(first),stamp(last.slice(0,4)+'-01-01')),to:stamp(last),selected:last},views=[],drag=null,frame=null;
const panels=[{key:1,id:'financing',color:'#367b9f',range:null},{key:2,id:'lending',color:'#287b70',range:null}];
function el(tag,attrs={},text){const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
function pct(v){return (v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(2)+'%'}
function niceStep(span,count=5){const raw=span/count,p=10**Math.floor(Math.log10(raw)),n=raw/p;return (n<=1?1:n<=2?2:n<=2.5?2.5:n<=5?5:10)*p}
function extent(values){let lo=Math.min(0,...values),hi=Math.max(0,...values),pad=Math.max(.35,(hi-lo)*.08);lo-=pad;hi+=pad;return [lo,hi]}
function show(date){state.selected=date;for(const v of views){let i=v.rows.findIndex(r=>r[0]>=date);if(i<0)i=v.rows.length-1;const r=v.rows[i],x=v.x(stamp(r[0])),y=v.y(r[v.panel.key]);v.line.setAttribute('x1',x);v.line.setAttribute('x2',x);v.dot.setAttribute('cx',x);v.dot.setAttribute('cy',y);v.dot.style.display=y>=v.T&&y<=v.H-v.B?'':'none';v.host.querySelector('svg').setAttribute('aria-label',`${v.panel.key===1?'融资':'融券'}余额20日变化率，${r[0]}，${pct(r[v.panel.key])}`);document.querySelector(`#${v.panel.id} time`).textContent=r[0];document.querySelector(`#${v.panel.id} strong`).textContent=pct(r[v.panel.key]);}}
function xTicks(rows,width){const start=state.from,end=state.to,days=(end-start)/86400000,result=[];
 if(days>365*2){for(let year=+rows[0][0].slice(0,4);year<=+rows.at(-1)[0].slice(0,4);year++)for(const month of [0,5]){const t=Date.UTC(year,month,1);if(t>=start&&t<=end)result.push([t,`${year}-${month+1}`])}}
 else if(days>90){let d=new Date(start);d.setUTCDate(1);for(;+d<=end;d.setUTCMonth(d.getUTCMonth()+1)){if(+d>=start)result.push([+d,`${d.getUTCFullYear()}-${d.getUTCMonth()+1}`])}}
 else{const count=Math.max(2,Math.floor(width/90));for(let i=0;i<count;i++){const r=rows[Math.round(i*(rows.length-1)/(count-1))];result.push([stamp(r[0]),r[0].slice(5)])}}
 const stride=Math.max(1,Math.ceil(result.length*62/width));return result.map((r,i)=>[...r,i%stride===0]);}
function draw(panel,rows){const host=document.querySelector(`#${panel.id} .plot`),W=host.clientWidth,H=host.clientHeight,L=26,R=W<500?64:78,T=17,B=29,P=W-L-R;host.replaceChildren();
 let [lo,hi]=panel.range??extent(rows.map(r=>r[panel.key]));const start=state.from,end=state.to;const x=t=>L+(t-start)/Math.max(86400000,end-start)*P,y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
 const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','data-y-min':lo,'data-y-max':hi});host.appendChild(svg);
 const defs=el('defs'),clip=el('clipPath',{id:'clip-'+panel.id});clip.appendChild(el('rect',{x:L,y:T,width:P,height:H-T-B}));defs.appendChild(clip);svg.appendChild(defs);
 const step=niceStep(hi-lo),lastValue=rows.at(-1)[panel.key],latestY=y(lastValue),latestVisible=latestY>=T&&latestY<=H-B;
 for(let v=Math.ceil(lo/step)*step;v<=hi+step*1e-7;v+=step){const cy=y(v);svg.appendChild(el('line',{x1:L,x2:W-R,y1:cy,y2:cy,stroke:Math.abs(v)<1e-8?'#b8c5ce':'#e8edf1','stroke-width':Math.abs(v)<1e-8?1:.7}));if(!latestVisible||Math.abs(cy-latestY)>17)svg.appendChild(el('text',{x:W-R+10,y:cy+4},`${Math.abs(v)<1e-8?0:+v.toFixed(2)}%`))}
 for(const [t,label,visible]of xTicks(rows,P)){const cx=x(t);svg.appendChild(el('line',{x1:cx,x2:cx,y1:T,y2:H-B,stroke:'#e8edf1','stroke-width':.7,class:'x-grid'}));if(visible)svg.appendChild(el('text',{x:cx,y:H-8,'text-anchor':'middle',class:'x-label'},label))}
 const g=el('g',{'clip-path':`url(#clip-${panel.id})`});svg.appendChild(g);const path=rows.map((r,i)=>(i?'L':'M')+x(stamp(r[0])).toFixed(2)+','+y(r[panel.key]).toFixed(2)).join(' ');
 g.appendChild(el('path',{d:path,stroke:panel.color,fill:'none',class:'series'}));
 if(latestVisible){const b=el('g',{class:'latest-badge'});b.appendChild(el('rect',{x:W-R+4,y:latestY-11,width:R-7,height:22,rx:2,fill:panel.color}));b.appendChild(el('text',{x:W-R/2+1,y:latestY+4,'text-anchor':'middle',style:'fill:#fff;font-size:10px;font-weight:600'},pct(lastValue)));svg.appendChild(b)}
 const line=el('line',{y1:T,y2:H-B,stroke:'#8da1af','stroke-dasharray':'3 4',class:'crosshair'}),dot=el('circle',{r:3.5,fill:panel.color,stroke:'#fff','stroke-width':1.5,class:'crosshair'});g.append(line,dot);
 const axis=el('rect',{x:W-R,y:T,width:R,height:H-T-B,fill:'transparent',class:'axis-hit',tabindex:0,role:'button','aria-label':'纵轴：拖动缩放，Shift拖动平移；双击或Home恢复自动；加减键缩放'});svg.appendChild(axis);
 const view={panel,rows,host,svg,x,y,lo,hi,W,H,L,R,T,B,line,dot};views.push(view);
 function point(e){if(drag)return;const mx=e.clientX-host.getBoundingClientRect().left;if(mx>W-R||mx<L)return;const target=start+(mx-L)/P*(end-start);let l=0,r=rows.length-1;while(l<r){const m=(l+r)>>1;if(stamp(rows[m][0])<target)l=m+1;else r=m}if(l>0&&Math.abs(stamp(rows[l-1][0])-target)<Math.abs(stamp(rows[l][0])-target))l--;show(rows[l][0])}
 svg.addEventListener('pointermove',point);svg.addEventListener('pointerdown',point);svg.addEventListener('pointerleave',e=>{if(!drag&&e.pointerType==='mouse')show(rows.at(-1)[0])});
 axis.addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();drag={panel,id:e.pointerId,startY:e.clientY,lo,hi,pan:e.shiftKey,height:H-T-B};host.setPointerCapture(e.pointerId)});
 axis.addEventListener('dblclick',e=>{e.preventDefault();panel.range=null;render()});
 axis.addEventListener('wheel',e=>{e.preventDefault();const span=(hi-lo)*Math.exp(Math.max(-.5,Math.min(.5,e.deltaY*.002))),mid=(lo+hi)/2;panel.range=[mid-span/2,mid+span/2];render()},{passive:false});
 axis.addEventListener('keydown',e=>{let span=hi-lo,mid=(lo+hi)/2;if(e.key==='Home')panel.range=null;else if(['+','=','-','_'].includes(e.key)){span*=e.key==='+'||e.key==='='?.8:1.25;panel.range=[mid-span/2,mid+span/2]}else if(e.key==='ArrowUp'||e.key==='ArrowDown'){const shift=span*.1*(e.key==='ArrowUp'?1:-1);panel.range=[lo+shift,hi+shift]}else return;e.preventDefault();e.stopPropagation();render();host.querySelector('.axis-hit').focus()});
}
function render(){const rows=DATA.filter(r=>stamp(r[0])>=state.from&&stamp(r[0])<=state.to);if(!rows.length)return;views=[];panels.forEach(p=>draw(p,rows));show(state.selected>=rows[0][0]&&state.selected<=rows.at(-1)[0]?state.selected:rows.at(-1)[0]);document.querySelectorAll('.period').forEach(n=>n.textContent=`${rows[0][0]} — ${rows.at(-1)[0]}`)}
function apply(a,b,preset=''){const rows=DATA.filter(r=>stamp(r[0])>=a&&stamp(r[0])<=b);if(!Number.isFinite(a)||!Number.isFinite(b)||a>b||rows.length<2){error.textContent='请选择至少包含两个交易日的有效区间。';return false}error.textContent='';state.from=Math.max(stamp(first),a);state.to=Math.min(stamp(last),b);state.selected=rows.at(-1)[0];from.value=iso(state.from);to.value=iso(state.to);panels.forEach(p=>p.range=null);document.querySelectorAll('[data-range]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.range===preset)));render();return true}
for(const input of [from,to]){input.min=first;input.max=last;input.addEventListener('change',()=>apply(stamp(from.value),stamp(to.value)))}
document.querySelectorAll('[data-range]').forEach(button=>button.addEventListener('click',()=>{const key=button.dataset.range;let d=new Date(stamp(last));if(key==='all')d=new Date(stamp(first));else if(key==='2017')d=new Date('2017-01-01T00:00:00Z');else if(key==='ytd')d=new Date(Date.UTC(d.getUTCFullYear(),0,1));else if(key.endsWith('m'))d.setUTCMonth(d.getUTCMonth()-parseInt(key));else d.setUTCFullYear(d.getUTCFullYear()-parseInt(key));apply(+d,stamp(last),key)}));
for(const p of panels){document.querySelector(`#${p.id} .reset`).addEventListener('click',()=>{p.range=null;render()});document.querySelector(`#${p.id} .plot`).addEventListener('keydown',e=>{const rows=views[0].rows;let i=rows.findIndex(r=>r[0]===state.selected);if(e.key==='ArrowLeft')i--;else if(e.key==='ArrowRight')i++;else if(e.key==='Home')i=0;else if(e.key==='End')i=rows.length-1;else return;e.preventDefault();show(rows[Math.max(0,Math.min(rows.length-1,i))][0])})}
window.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId)return;e.preventDefault();const d=drag,delta=e.clientY-d.startY,mid=(d.lo+d.hi)/2;if(d.pan){const shift=delta/d.height*(d.hi-d.lo);d.panel.range=[d.lo+shift,d.hi+shift]}else{const span=Math.max(.1,Math.min(5000,(d.hi-d.lo)*Math.exp(delta*.008)));d.panel.range=[mid-span/2,mid+span/2]}if(!frame)frame=requestAnimationFrame(()=>{frame=null;render()})},{passive:false});
for(const event of ['pointerup','pointercancel'])window.addEventListener(event,e=>{if(drag?.id===e.pointerId){const host=document.querySelector(`#${drag.panel.id} .plot`);if(host.hasPointerCapture(e.pointerId))host.releasePointerCapture(e.pointerId);drag=null}});
let resize;new ResizeObserver(()=>{clearTimeout(resize);resize=setTimeout(render,60)}).observe(document.querySelector('main'));
apply(state.from,state.to,'ytd');
'''

def build(source=OUT/'financing_accounts_daily.csv',output=HTML):
    data=chart_data(source)
    shared=(ROOT/'assets/report.css').read_text()
    status=json.loads((ROOT/'data/status.json').read_text())
    checked=datetime.fromisoformat(status['checked_at_utc']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
    buttons=''.join(f'<button type="button" data-range="{v}" aria-pressed="false">{label}</button>' for v,label in [('1m','1个月'),('3m','3个月'),('6m','6个月'),('ytd','YTD'),('1y','1年'),('3y','3年'),('5y','5年'),('2017','2017至今'),('all','全部')])
    charts=''.join(f'''<section class="panel" id="{key}" style="--series:{color}"><div class="panel-head"><h2><span class="swatch" aria-hidden="true"></span>{title}</h2><div class="reading"><time></time><strong></strong></div></div><div class="plot" tabindex="0" role="group" aria-label="{title}曲线，左右方向键查看日期"></div><div class="panel-bottom"><span class="period"></span><button type="button" class="reset" aria-label="{title}恢复自动纵轴">自动纵轴 ↺</button></div></section>''' for key,title,color in [('financing','融资余额','#367b9f'),('lending','融券余额','#287b70')])
    html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>融资与融券 · 余额变化率</title><style>{shared}\n{CSS}</style></head><body><main><header><h1>融资与融券</h1><p><span>20个交易日余额变化率 · %</span><span>截至 {data[-1][0]}</span></p></header><div class="toolbar"><div class="ranges" role="group" aria-label="时间范围">{buttons}</div><div class="dates"><label>起始<input type="date" id="from" aria-label="起始日期"></label><label>结束<input type="date" id="to" aria-label="结束日期"></label></div></div><p id="date-error" class="date-error" role="alert"></p>{charts}<footer class="footer-note"><span>来源：东方财富 Choice · 全市场账户统计 · 最近核查 {checked}（北京）<br>变化率＝当日余额 ÷ 20个交易日前余额 − 1</span><span>悬停或轻触查看 · 左右键逐日查看 · 拖动右侧纵轴缩放</span></footer></main><script type="application/json" id="series-data">{json.dumps(data,separators=(',',':'),allow_nan=False)}</script><script>{JS}</script></body></html>'''
    Path(output).write_text(html)
    print(output,len(html.encode()),len(data))
if __name__=='__main__':build()
