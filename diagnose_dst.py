import csv,json
from pathlib import Path
from pipeline.model import *
root=Path('.');cache=root/'.cache'
def read(name):return list(csv.DictReader((cache/name).open(encoding='utf-8-sig')))
games=read('games.csv'); teams=sum([read(f'stats_team_week_{y}.csv') for y in [2024,2025,2026]],[])
rows,ti,_=prepare([],teams,[],[],games)
ds,state=dataset(rows,ti)
train=[r for r in ds if r['season'] in [2024,2025] and (r['season']>2024 or r['week']>=5)]
m=Estimator().fit(train)
warm=[r for r in ds if r['season']==2024 and 5<=r['week']<=12];cal=[r for r in ds if r['season']==2024 and r['week']>=13]
wm=Estimator().fit(warm);res=np.array([r['y'] for r in cal])-wm.predict(cal)
pipe,inds=m.models['DST']; scaler=pipe[0];reg=pipe[1]
n=len(KEYS+USAGE); names=['avg:'+k for k in KEYS+USAGE]+['latest_minus_avg:'+k for k in KEYS+USAGE]+['team:'+k for k in TEAM]+['opp:'+k for k in TEAM]+['history_count','season_count','gap','team_changed','home','indoor','rest','week','matchup','matchup_count']
weights=np.array([0 if k=='points_allowed' else 6 if k in ['def_tds','special_teams_tds'] else 1 if k=='def_sacks' else 2 for k in DEF])
report={}
for team in ['JAX','TB','SF','ARI','HOU']:
 g=next(g for g in games if int(g['season'])==2026 and int(g['week'])==2 and team in [normalize_team(g['home_team']),normalize_team(g['away_team'])]);home=team==normalize_team(g['home_team']);opp=normalize_team(g['away_team'] if home else g['home_team'])
 r=dict(player_id='DST:'+team,pos='DST',team=team,opponent_team=opp,season=2026,week=2,date=g['gameday'],home=float(home),roof_indoor=float(g['roof'] in ['dome','closed']),rest=number(g,'home_rest' if home else 'away_rest',7))
 r['x'],_,r['matchup']=state.row(r); pred=m.predict([r])[0]; mean=distribution(pred,res,'DST')[0][2]
 contrib=reg.coef_*scaler.transform([r['x']])[0]; linear=weights@contrib; pa=contrib[-1]
 detail={'mean':float(mean),'opponent':opp,'stats':dict(zip(DEF,pred[inds].tolist())),'baseline':r['baseline_scores'].tolist(),'matchup':r['matchup'],'intercept':dict(zip(DEF,reg.intercept_.tolist())),'top_nonPA_contributions':sorted(zip(names,linear.tolist()),key=lambda x:-abs(x[1]))[:15],'top_PA_contributions':sorted(zip(names,pa.tolist()),key=lambda x:-abs(x[1]))[:12]}
 groups={'own_history':slice(0,n),'latest_change':slice(n,2*n),'own_team':slice(2*n,2*n+len(TEAM)),'opponent':slice(2*n+len(TEAM),2*n+2*len(TEAM)),'matchup':slice(-2,None)}
 detail['neutralize_group']={}
 for label,sl in groups.items():
  rr=dict(r);rr['x']=r['x'].copy();rr['x'][sl]=scaler.mean_[sl];detail['neutralize_group'][label]=float(distribution(m.predict([rr])[0],res,'DST')[0][2])
 hist=state.players['DST:'+team]; detail['last_game']={k:hist[-1].get(k) for k in ['date','opponent_team']+DEF};detail['opponent_recent']=[{k:h.get(k) for k in ['season']+TEAM} for h in state.teams[opp][-2:]]
 rr=dict(r);rr['x']=r['x'].copy();rr['x'][-2]=0;detail['zero_matchup']=float(distribution(m.predict([rr])[0],res,'DST')[0][2])
 report[team]=detail
Path('output').mkdir(exist_ok=True);Path('output/dst-diagnostic.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report['JAX'],indent=2));print('SUMMARY',[(t,round(v['mean'],2),v['neutralize_group']) for t,v in report.items()])
