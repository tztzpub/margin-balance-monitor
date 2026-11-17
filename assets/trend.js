(()=>{
 const series=JSON.parse(document.getElementById('trend-data').textContent);
 const number=v=>v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 const percent=v=>(v>=0?'+':'−')+Math.abs(v*100).toFixed(2)+'%';
 let range=[state.from,state.to];const views=[];
 for(const s of series){
  const card=document.getElementById('trend-'+s.id),last=s.rows.at(-1),mid=last[2];
  card.querySelector('time').textContent='截至 '+last[0];
  const values=[number(last[1]),number(mid),percent(last[1]/mid-1),percent(last[1]/(mid*.9)-1)];
  card.querySelectorAll('.trend-stats b').forEach((n,i)=>n.textContent=values[i]);
  const where=last[1]<mid*.9?'下轨以下':last[1]<mid?'下轨与中轨之间':last[1]<=mid*1.1?'中轨与上轨之间':'上轨以上';
  card.querySelector('.trend-state').textContent=where+(last[3]?` · ${last[3]}跌破以来${last[4]}个交易日，尚未回到动态中轨`:' · 当前无未恢复的跌破轮次');
  views.push({s,card,host:card.querySelector('.trend-plot'),selected:last[0]});
 }
 function draw(v){
  const {s,host,card}=v,rows=s.rows.filter(r=>stamp(r[0])>=range[0]&&stamp(r[0])<=range[1]);v.rows=rows;
  host.replaceChildren();
  if(rows.length<2){host.innerHTML='<div class="trend-empty">所选区间尚无足够通道数据（需500个交易日预热）</div>';card.querySelector('.trend-detail').textContent='';return}
  const W=host.clientWidth,H=host.clientHeight,L=W<450?46:55,R=14,T=16,B=32;
  const lows=rows.map(r=>r[2]*.9),highs=rows.map(r=>r[2]*1.1),all=[...rows.map(r=>r[1]),...lows,...highs];
  let lo=Math.min(...all),hi=Math.max(...all);const pad=(hi-lo)*.08;lo-=pad;hi+=pad;
  const x=i=>L+i/(rows.length-1)*(W-L-R),y=z=>T+(hi-z)/(hi-lo)*(H-T-B);
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':s.name+'指数与动态中轨及上下轨'});host.append(svg);
  const step=niceStep(hi-lo,4);
  for(let z=Math.ceil(lo/step)*step;z<hi;z+=step){svg.append(el('line',{x1:L,x2:W-R,y1:y(z),y2:y(z),stroke:'#dce3e8','stroke-width':.6}),el('text',{x:L-7,y:y(z)+4,'text-anchor':'end'},Math.round(z).toLocaleString('en-US')))}
  const path=values=>values.map((z,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(z).toFixed(2)).join('');
  const band=path(highs)+lows.map((_,k)=>{const i=lows.length-1-k;return 'L'+x(i).toFixed(2)+','+y(lows[i]).toFixed(2)}).join('')+'Z';svg.append(el('path',{d:band,fill:'#829568','fill-opacity':.12}));
  for(const [values,color,dash,width] of [[highs,'#869671','',1],[lows,'#869671','',1],[rows.map(r=>r[2]),'#617b45','6 4',1.6],[rows.map(r=>r[1]),'#28658a','',1.8]])svg.append(el('path',{d:path(values),fill:'none',stroke:color,'stroke-width':width,'stroke-dasharray':dash}));
  const n=W<450?3:4;
  for(let k=0;k<=n;k++){const i=Math.round(k/n*(rows.length-1));svg.append(el('text',{x:x(i),y:H-8,'text-anchor':k===0?'start':k===n?'end':'middle'},rows.length<=65?rows[i][0].slice(5):rows[i][0].slice(0,7)))}
  const line=el('line',{x1:0,x2:0,y1:T,y2:H-B,stroke:'#9aa7ad','stroke-dasharray':'2 3'}),dot=el('circle',{r:3,fill:'#28658a',stroke:'#fff','stroke-width':1});svg.append(line,dot);
  v.pick=i=>{
   i=Math.max(0,Math.min(rows.length-1,i));v.selected=rows[i][0];v.index=i;const r=rows[i];line.setAttribute('x1',x(i));line.setAttribute('x2',x(i));dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(r[1]));
   const detail=card.querySelector('.trend-detail');detail.replaceChildren();const strong=document.createElement('strong');strong.textContent=r[0]+'　';detail.append(strong,document.createTextNode(`收盘 ${number(r[1])} · 中轨 ${number(r[2])} · 下轨 ${number(r[2]*.9)} · 上轨 ${number(r[2]*1.1)} · 相对中轨 ${percent(r[1]/r[2]-1)}`));
  };
  v.pick(Math.max(0,rows.findLastIndex(r=>r[0]<=v.selected)));
  host.onpointermove=e=>{if(e.pointerType==='touch'&&e.buttons===0)return;const rect=host.getBoundingClientRect();v.pick(Math.round((e.clientX-rect.left-L)/(W-L-R)*(rows.length-1)))};
  host.onpointerdown=e=>{host.focus({preventScroll:true});host.onpointermove(e)};
  host.onpointerleave=()=>v.pick(rows.length-1);
  host.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();v.pick(e.key==='Home'?0:e.key==='End'?rows.length-1:v.index+(e.key==='ArrowLeft'?-1:1))}};
 }
 window.renderTrendChannels=(from,to)=>{range=[from,to];views.forEach(draw)};
 window.renderTrendChannels(...range);
})();
