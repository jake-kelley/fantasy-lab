function median(a){const b=[...a].sort((a,b)=>a-b),n=b.length;return n%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2;}
function aggregate(ranks,trim=true){
  if(!ranks.length||new Set(ranks.map(r=>r.source)).size!==ranks.length)throw Error('One vote per analyst required');
  const v=ranks.map(r=>r.rank),m=median(v),mad=median(v.map(x=>Math.abs(x-m))),threshold=Math.max(5,3*1.4826*mad);
  const excluded=trim&&v.length>=7?ranks.filter(r=>Math.abs(r.rank-m)>threshold).sort((a,b)=>Math.abs(b.rank-m)-Math.abs(a.rank-m)||a.source.localeCompare(b.source)).slice(0,Math.floor(v.length*.2)).map(r=>r.source):[];
  const kept=ranks.filter(r=>!excluded.includes(r.source));
  return {mean:kept.reduce((s,r)=>s+r.rank,0)/kept.length,raw_mean:v.reduce((a,b)=>a+b,0)/v.length,median:m,low:Math.min(...v),high:Math.max(...v),count:v.length,excluded};
}
if(typeof module!=='undefined')module.exports={aggregate};
if(typeof document!=='undefined'){
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data,historyData,selected=new Set(),displayed=[];
const fmt=n=>n==null?'—':Number(n).toFixed(2);
const credential=s=>s.accuracy_rank_2025?`2025 FP overall #${s.accuracy_rank_2025} · half-PPR competition`:'Recent comparable PPR accuracy unverified';
function activeSources(pos){return data.health.filter(h=>h.position===pos&&h.status==='available'&&selected.has(h.source)).map(h=>h.source);}
function render(){
  const pos=$('position').value,active=activeSources(pos),minimum=Math.max(3,Math.ceil(active.length*.6)),q=$('search').value.toLowerCase();
  const all=data.players.filter(p=>p.position===pos).map(p=>{const ranks=p.ranks.filter(r=>active.includes(r.source));return ranks.length?{...p,ranks,...aggregate(ranks,$('trim').checked)}:null;}).filter(Boolean).sort((a,b)=>a.mean-b.mean||a.name.localeCompare(b.name));
  let rank=0;all.forEach(p=>{p.limited=p.count<minimum;p.order=p.limited?null:++rank;});
  displayed=all.filter(p=>(!p.limited||$('limited').checked)&&`${p.name} ${p.team}`.toLowerCase().includes(q));
  $('board-title').textContent=`Week ${data.week} · ${pos==='DST'?'D/ST':pos} consensus`;
  $('coverage').textContent=`${active.length} selected sources available · Main board requires ${minimum} votes · Filtering needs 7 votes per player`;
  $('count').textContent=`${displayed.length} PLAYERS`;$('selected-count').textContent=`(${selected.size}/${data.sources.length})`;
  $('scoring-note').hidden=!['K','DST'].includes(pos);
  $('rows').innerHTML=displayed.map(p=>{const strength=p.order?1-(p.order-1)/Math.max(1,rank-1):0;const start=[239,247,240],end=[23,102,87],rgb=start.map((v,i)=>Math.round(v+(end[i]-v)*strength));return `<tr><td>${p.order??'—'}</td><td><button class="player-button" data-id="${esc(p.id)}">${esc(p.name)}</button><small>${esc(p.team)} · ${esc(p.matchup)}${p.limited?' · <span class="limited-tag">Limited coverage</span>':''}</small></td><td class="rank-shade" style="background:rgb(${rgb});color:${strength>.55?'#fff':'#20332f'}">${fmt(p.mean)}</td><td>${fmt(p.raw_mean)}</td><td>${p.low}–${p.high}</td><td>${p.count}/${active.length}</td><td>${p.excluded.length||'—'}</td></tr>`;}).join('')||'<tr><td colspan="7" class="empty">No players meet these filters. Select more available analysts or show limited coverage.</td></tr>';
  document.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>detail(b.dataset.id));
}
function detail(id){const p=displayed.find(p=>p.id===id);$('detail-content').innerHTML=`<h2>${esc(p.name)}</h2><p>Consensus ${fmt(p.mean)} · Raw average ${fmt(p.raw_mean)} · Median ${fmt(p.median)}</p><table><thead><tr><th>ANALYST</th><th>RANK</th><th>VOTE</th></tr></thead><tbody>${p.ranks.map(r=>{const s=data.sources.find(s=>s.id===r.source);return `<tr><td><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a><small>Published ${esc(r.published)} · feed local time</small></td><td>${r.rank}</td><td class="${p.excluded.includes(r.source)?'excluded':''}">${p.excluded.includes(r.source)?'Excluded outlier':'Included'}</td></tr>`;}).join('')}</tbody></table><p>Excluded votes remain visible. Filtering is symmetric and does not target any particular analyst.</p>`;$('detail').showModal();}
function renderHistory(){if(!historyData)return;const year=+$('history-year').value,pos=$('history-pos').value,mode=$('history-mode').value;const rows=historyData.summary.filter(r=>r.year===year&&r.position===pos);$('history-note').textContent=mode==='own_coverage'?'Different player pools and weeks: these numbers must not be used to declare a winning analyst.':'Same players and weeks for every analyst. Correlation is not percentage correct. Missing data reduces coverage; zero weeks means unverified.';$('history-rows').innerHTML=rows.map(r=>{const m=r[mode];return `<tr><td>${esc(r.name)}</td><td>${m.weeks}</td><td>${m.players}</td><td>${m.rho==null?'—':m.rho.toFixed(3)}</td><td>${fmt(m.top_points_per_pick)}</td><td>${fmt(m.hindsight_gap_per_pick)}</td></tr>`;}).join('');}
async function start(){
  const r=await fetch('data/consensus.json');if(!r.ok)throw Error('Consensus data unavailable');data=await r.json();selected=new Set(data.sources.map(s=>s.id));
  $('edition').textContent=`${data.season} · Week ${data.week}`;$('updated').textContent=`Updated ${new Date(data.generated_at).toLocaleString()}`;
  if(Date.now()-Date.parse(data.generated_at)>36*3600000){$('freshness').hidden=false;$('freshness').textContent='This board is more than 36 hours old. Check analyst pages for newer ranks and injury updates.';}
  $('source-selection').innerHTML=data.sources.map(s=>`<label><input type="checkbox" data-source="${s.id}" checked>${esc(s.name)}<small>${esc(credential(s))}</small></label>`).join('');
  document.querySelectorAll('[data-source]').forEach(c=>c.onchange=()=>{c.checked?selected.add(c.dataset.source):selected.delete(c.dataset.source);render();});
  $('analyst-cards').innerHTML=data.sources.map(s=>`<article><h3><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)} ↗</a></h3><p>${esc(credential(s))}<br><a href="${esc(s.accuracy_url)}">Published accuracy reference ↗</a></p><p>${data.health.filter(h=>h.source===s.id).map(h=>`${h.position}: ${h.status==='available'?h.count+' ranks':'unavailable'}`).join('<br>')}</p><small>${esc(s.family)}</small></article>`).join('');
  ['position','trim','limited'].forEach(id=>$(id).onchange=render);$('search').oninput=render;
  ['history-year','history-pos','history-mode'].forEach(id=>$(id).onchange=renderHistory);
  $('close-detail').onclick=()=>$('detail').close();
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==b.dataset.view);document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));});
  $('export').onclick=()=>{const values=[['rank','player','team','position','average_rank','raw_average','sources','excluded','limited_coverage'],...displayed.map(p=>[p.order??'',p.name,p.team,p.position,p.mean,p.raw_mean,p.count,p.excluded.join('|'),p.limited])];const csv=values.map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'})),a=document.createElement('a');a.href=url;a.download=`fieldwork-${data.season}-week${data.week}-${$('position').value}-ppr.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  render();
  try{const h=await fetch('data/historical-accuracy.json');if(!h.ok)throw Error('Archive audit unavailable');historyData=await h.json();$('history-method').innerHTML=[...historyData.method,...historyData.unavailable].map(t=>`<p>${esc(t)}</p>`).join('');renderHistory();}catch(e){$('history-note').textContent=e.message;}
}
start().catch(e=>{$('error').hidden=false;$('error').textContent=e.message;});
}
