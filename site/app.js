'use strict';
const $ = id => document.getElementById(id);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => Number.isFinite(n) ? n.toFixed(1) : '—';
let data, position = 'QB', view = 'projections', visible = [];
let pointBounds = [0, 1];
function shade(strength, favorable=true){
  const t=Math.max(0,Math.min(1,strength));
  const light=favorable?[239,247,240]:[252,240,236], dark=favorable?[23,102,87]:[151,53,43];
  const rgb=light.map((v,i)=>Math.round(v+(dark[i]-v)*t));
  const linear=rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});
  const luminance=.2126*linear[0]+.7152*linear[1]+.0722*linear[2];
  return `background-color:rgb(${rgb.join(',')});color:${luminance>.179?'#000':'#fff'}`;
}
function pointStyle(f){
  const v=f?.mean?.[scoring()];
  if(!Number.isFinite(v)) return '';
  const [low,high]=pointBounds;
  return shade(high===low ? .5 : (v-low)/(high-low));
}
const forecast = (p,w=Number($('week').value)) => p.forecasts.find(f=>f.week===w);
const scoring = () => Number($('scoring').value);
const eligible = (p,f) => {
  if (!f || f.bye || f.played) return false;
  if ($('deep').checked) return true;
  if (p.pos==='DST') return true;
  if (p.history_games < 1 || !p.last_played) return false;
  const days = (new Date(data.observations_through)-new Date(p.last_played))/86400000;
  if (days>35) return false;
  if (p.pos==='K') return f.usage.fg_att+f.usage.pat_att > 0;
  if (p.pos==='QB') return f.usage.attempts>7 || f.latest_snap_pct>.5;
  return f.latest_snap_pct>=.15 || f.usage.targets+f.usage.carries>=2;
};
function status(p,f){
  if(f.unavailable) return `<span class="status out">${esc(p.status)} · conditional</span>`;
  if(f.low_history) return '<span class="status warn">Limited history</span>';
  if(!['Active','ACT'].includes(p.status)) return `<span class="status warn">${esc(p.status)}</span>`;
  return '<span class="status">Active</span>';
}
function nextCell(p,w){
  const f=forecast(p,w);
  if(!f) return '—';
  if(f.bye) return '<span class="matchup">BYE</span>';
  if(f.played) return '<span class="matchup">PLAYED</span>';
  return `${fmt(f.mean[scoring()])}<span class="matchup">${f.home?'vs':'@'} ${esc(f.opponent)}</span>`;
}
function filtered(){
  const q=$('search').value.trim().toLowerCase();
  return data.players.filter(p=>(position==='FLEX'?['RB','WR','TE'].includes(p.pos):p.pos===position)
    && (!q || `${p.name} ${p.team}`.toLowerCase().includes(q)) && eligible(p,forecast(p)))
    .sort((a,b)=>forecast(b).mean[scoring()]-forecast(a).mean[scoring()]);
}
function render(){
  if(!data) return;
  const week=Number($('week').value), s=scoring();
  visible=filtered();
  // Search never rescales colors. One scale spans all three forecast weeks.
  const values=data.players.filter(p=>position==='FLEX'?['RB','WR','TE'].includes(p.pos):p.pos===position)
    .flatMap(p=>p.forecasts.filter(f=>eligible(p,f)).map(f=>f.mean[s])).filter(Number.isFinite);
  pointBounds=values.length?[Math.min(...values),Math.max(...values)]:[0,1];
  $('board-title').textContent=`Week ${week} · ${position==='DST'?'Defense / special teams':position} outlook`;
  $('count').textContent=`${visible.length} OPTIONS`;
  $('score-note').textContent=position==='DST'?'D/ST v0.2: compact inputs; league-average turnover/TD/block/safety estimates. Scoreboard points allowed; platform scoring may differ.':
    ['DL','LB','DB'].includes(position)?'IDP uses the displayed Fieldwork scoring preset. Position assignments follow roster data and may differ from your league.':
    position==='K'?'Kicker scoring: 3/4/5 by distance, +1 PAT, −1 missed FG/PAT. Blocked attempts are not deducted.':
    'Compare the model with the rolling baseline. The 2025 test did not show an offensive-position MAE advantage for this model.';
  let tier=0, leader=Infinity;
  $('rows').innerHTML=visible.map((p,i)=>{
    const f=forecast(p), mean=f.mean[s];
    let separator='';
    if(leader-mean>2){tier++;leader=mean;separator=`<tr class="tier"><td colspan="8">TIER ${tier} · WITHIN 2 POINTS OF LEADER · DISPLAY GROUP ONLY</td></tr>`;}
    const width=Math.min(100,Math.max(5,(f.p90[s]-f.p10[s])*2));
    return separator+`<tr><td>${i+1}</td><td><button class="player-button" data-player="${esc(p.id)}">${esc(p.name)}</button><span class="matchup">${esc(p.team)} · ${esc(p.pos)} &nbsp; ${f.home?'vs':'@'} ${esc(f.opponent)}</span></td><td class="points projection-color" style="${pointStyle(f)}">${fmt(mean)}</td><td>${fmt(f.baseline[s])}</td><td class="range">${fmt(f.p10[s])} — ${fmt(f.p90[s])}<div class="range-bar"><i style="width:${width}%"></i></div></td><td class="projection-color" style="${pointStyle(forecast(p,week+1))}">${nextCell(p,week+1)}</td><td class="projection-color" style="${pointStyle(forecast(p,week+2))}">${nextCell(p,week+2)}</td><td>${status(p,f)}</td></tr>`;
  }).join('') || '<tr><td colspan="8" class="empty">No matching players. Try another position, or include deep bench / limited history.</td></tr>';
  renderMatchups(); renderValidation();
}
function renderMatchups(){
  const positions=['QB','RB','WR','TE','K','DST','DL','LB','DB'];
  const teams=new Map();
  for(const p of data.players){
    const f=forecast(p);if(!f || f.bye || f.played) continue;
    if(!teams.has(p.team)) teams.set(p.team,{opp:f.opponent,home:f.home,values:{}});
    teams.get(p.team).values[p.pos]=f.matchup_residual;
  }
  $('heatmap').innerHTML=[...teams].sort(([a],[b])=>a.localeCompare(b)).map(([team,x])=>
    `<tr><td>${esc(team)}</td><td>${x.home?'vs':'@'} ${esc(x.opp)}</td>${positions.map(pos=>{
      const v=x.values[pos];if(v===undefined) return '<td>—</td>';
      const extent=Math.max(1,...[...teams.values()].map(t=>Math.abs(t.values[pos]??0)));
      return `<td style="${shade(Math.abs(v)/extent,v>=0)}">${v>0?'+':''}${fmt(v)}</td>`;
    }).join('')}</tr>`).join('');
}
function renderValidation(){
  const entries=Object.entries(data.validation), wins=entries.filter(([,v])=>v.beats_baseline_mae).length;
  const pos=position==='FLEX'?'WR':position, current=data.validation[pos];
  $('validation-cards').innerHTML=`<div class="metric"><span class="eyebrow">LOWER MAE THAN BASELINE</span><strong>${wins} / ${entries.length}</strong><p>Position groups, using the fixed 2025 test.</p></div><div class="metric"><span class="eyebrow">${esc(pos)} MODEL ERROR</span><strong>${current.mae.toFixed(2)}</strong><p>Mean absolute error, in fantasy points.</p></div><div class="metric"><span class="eyebrow">${esc(pos)} RANGE COVERAGE</span><strong>${(current.interval_coverage*100).toFixed(0)}%</strong><p>Observed coverage; nominal target is 80%.</p></div>`;
  $('validation-rows').innerHTML=entries.map(([p,v])=>`<tr><td>${esc(p)}</td><td>${v.n.toLocaleString()}</td><td class="${v.beats_baseline_mae?'good':'bad'}">${v.mae.toFixed(2)}</td><td>${v.baseline_mae.toFixed(2)}</td><td>${v.rmse.toFixed(2)}</td><td>${v.baseline_rmse.toFixed(2)}</td><td>${(v.interval_coverage*100).toFixed(1)}%</td></tr>`).join('');
  $('weekly-title').textContent=`${pos} · week-by-week error`;
  const max=Math.max(...current.weekly.flatMap(w=>[w.mae,w.baseline_mae]),1);
  $('weekly').innerHTML=current.weekly.map(w=>`<div class="week-bar" title="Week ${w.week}: model ${w.mae}, baseline ${w.baseline_mae}"><i style="height:${w.mae/max*100}%"></i><i style="height:${w.baseline_mae/max*100}%"></i><span>${w.week}</span></div>`).join('');
}
function showPlayer(id){
  const p=data.players.find(x=>x.id===id), f=forecast(p), s=scoring();
  const usage=Object.entries(f.usage).filter(([,v])=>v!==0);
  $('detail-content').innerHTML=`<h2>${esc(p.name)}</h2><p>${esc(p.team)} · ${esc(p.pos)} · Week ${f.week} ${f.home?'vs':'@'} ${esc(f.opponent)} · ${esc(f.date)}</p>${status(p,f)}<div class="metric-grid"><div class="metric"><span class="eyebrow">MODEL</span><strong>${fmt(f.mean[s])}</strong></div><div class="metric"><span class="eyebrow">BASELINE</span><strong>${fmt(f.baseline[s])}</strong></div><div class="metric"><span class="eyebrow">HISTORY</span><strong>${p.history_games}</strong></div></div><p>Estimated 80% outcome range: ${fmt(f.p10[s])} to ${fmt(f.p90[s])}. These are conditional-on-playing estimates. ${f.low_history?'Limited history: treat this as a provisional statistical estimate.':''}</p><h3>Projected scoring components</h3><div class="stat-list">${Object.entries(f.stats).map(([k,v])=>`<div><span>${esc(k.replaceAll('_',' '))}</span><b>${fmt(v)}</b></div>`).join('')}</div><h3>Prior workload</h3><p>Recency-weighted history, not next week’s projected usage. Last observed game: ${esc(p.last_played||'none')}. Latest relevant snap share: ${(f.latest_snap_pct*100).toFixed(0)}%.</p><div class="stat-list">${usage.map(([k,v])=>`<div><span>${esc(k.replaceAll('_',' '))}</span><b>${fmt(v)}</b></div>`).join('')||'<div>No prior workload recorded.</div>'}</div><h3>Matchup context</h3><p>Opponents at this position scored ${fmt(f.matchup_residual)} PPR points above their prior rolling baselines on average across up to six recent matchups. This is group-level descriptive context, not an individual boost. ${p.pos==='DST'?'D/ST v0.2 excludes this residual from its model inputs.':''}</p>`;
  $('detail').showModal();
}
function downloadCSV(){
  const s=scoring(), lines=[['player','team','position','week','opponent','status','model_mean','baseline','p10','p90']];
  for(const p of visible){const f=forecast(p);lines.push([p.name,p.team,p.pos,f.week,f.opponent,p.status,f.mean[s],f.baseline[s],f.p10[s],f.p90[s]]);}
  const csv=lines.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download=`fieldwork-week-${$('week').value}-${position}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{
  view=b.dataset.view;document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==view);
  document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelector('.controls').hidden=view==='method';document.querySelector('.positions').hidden=view==='method'||view==='matchups';
}));
document.querySelectorAll('[data-pos]').forEach(b=>b.addEventListener('click',()=>{
  position=b.dataset.pos;document.querySelectorAll('[data-pos]').forEach(x=>x.classList.toggle('active',x===b));render();
}));
['week','scoring','deep'].forEach(id=>$(id).addEventListener('change',render));$('search').addEventListener('input',render);
$('rows').addEventListener('click',e=>{const b=e.target.closest('[data-player]');if(b)showPlayer(b.dataset.player);});
$('export').addEventListener('click',downloadCSV);$('close-detail').addEventListener('click',()=>$('detail').close());
fetch('data/projections.json').then(r=>{if(!r.ok)throw Error(`Projection bundle unavailable (${r.status}). Run the pipeline or check the latest Actions build.`);return r.json();}).then(d=>{
  data=d;$('week').innerHTML=d.weeks.map(w=>`<option value="${w}">Week ${w}</option>`).join('');
  $('through').textContent=new Date(d.observations_through+'T12:00:00').toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
  $('updated').textContent='Built '+new Date(d.generated_at).toLocaleString();$('version').textContent=d.version;
  $('limitations').innerHTML=d.limitations.map(x=>`<li>${esc(x)}</li>`).join('');
  $('sources').innerHTML=d.sources.map(x=>`<details><summary>${esc(x.name)}</summary><a href="${esc(x.url)}">Original data ↗</a><br>Fetched ${esc(x.fetched_at)} · ${x.bytes.toLocaleString()} bytes<br><code>SHA-256 ${esc(x.sha256)}</code></details>`).join('');
  const age=(Date.now()-new Date(d.generated_at))/86400000;
  if(age>2){$('error').hidden=false;$('error').textContent=`This bundle is ${Math.floor(age)} days old. Check the latest successful update before making lineup decisions.`;}
  render();
}).catch(e=>{$('error').hidden=false;$('error').textContent=e.message;$('through').textContent='Unavailable';$('updated').textContent='No projection data loaded';});
