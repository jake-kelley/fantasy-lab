"""Independent PPR team-position totals; not sums of speculative depth-chart forecasts."""
from collections import defaultdict
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .data import number, normalize_team
from .model import score
from .data import ROOT
import json


def average(history, year):
    recent=history[-12:]
    if not recent:return 0.
    weights=[.8**(len(recent)-1-i)*(.35 if s<year else 1) for i,(s,_) in enumerate(recent)]
    return float(np.average([v for _,v in recent],weights=weights))


def historical(ds):
    groups=defaultdict(list)
    for r in ds:
        if r['pos'] in ['RB','WR','TE']:groups[(r['season'],r['week'],r['team'],r['pos'])].append(r)
    history=defaultdict(list);allowed=defaultdict(list);adjusted=defaultdict(list);rows=[]
    by_week=defaultdict(list)
    for key,rr in groups.items():by_week[key[:2]].append((key,rr))
    for key in sorted(by_week):
        pending=[]
        for (_,_,team,pos),rr in by_week[key]:
            r=dict(rr[0]);h=history[(team,pos)];baseline=average(h,r['season'])
            opposition=(r['opponent_team'],pos)
            r['group_x']=np.r_[baseline,(h[-1][1] if h else 0)-baseline,
                                average(allowed[opposition],r['season']),
                                average(adjusted[opposition],r['season']),r['factor_x']]
            r['group_y']=sum(float(score(x['y'],pos)) for x in rr)
            r['group_baseline']=baseline;rows.append(r);pending.append(r)
        for r in pending:
            history[(r['team'],r['pos'])].append((r['season'],r['group_y']))
            allowed[(r['opponent_team'],r['pos'])].append((r['season'],r['group_y']))
            adjusted[(r['opponent_team'],r['pos'])].append((r['season'],r['group_y']-r['group_baseline']))
    return rows,history,allowed,adjusted


def build(ds, factor_state, games, season, weeks):
    rows,history,allowed,adjusted=historical(ds)
    report={};out=[]
    for pos in ['RB','WR','TE']:
        selected=[r for r in rows if r['pos']==pos]
        train=[r for r in selected if r['season']==2024 and r['week']>=5]
        test=[r for r in selected if r['season']==2025 and r['week']>=13]
        def fit(rr,alpha):
            m=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
            return m.fit(np.array([r['group_x'] for r in rr]),[r['group_y'] for r in rr])
        # Frozen choices generated explicitly by tune_team_outlook, never selected on live data.
        cfg=json.loads((ROOT/'research'/'team-selection.json').read_text())[pos]
        model=fit(train,cfg['alpha']);weight=cfg['weight']
        pred=weight*np.maximum(0,model.predict(np.array([r['group_x'] for r in test])))+(1-weight)*np.array([r['group_baseline'] for r in test])
        actual=np.array([r['group_y'] for r in test]);baseline=np.array([r['group_baseline'] for r in test])
        report[pos]=dict(n=len(test),mae=float(np.mean(abs(pred-actual))),
                         baseline_mae=float(np.mean(abs(baseline-actual))))
        model=fit([r for r in selected if r['season'] in [2024,2025] and
                   (r['season']>2024 or r['week']>=5)],cfg['alpha'])
        for g in games:
            if int(g['season'])!=season or int(g['week']) not in weeks or g['game_type']!='REG':continue
            if g.get('home_score') and g.get('away_score'):continue
            for home in [True,False]:
                team=normalize_team(g['home_team'] if home else g['away_team'])
                opp=normalize_team(g['away_team'] if home else g['home_team'])
                r=dict(team=team,opponent_team=opp,pos=pos,season=season,home=float(home),
                       roof_indoor=float(g.get('roof') in ['dome','closed']),
                       rest=number(g,'home_rest' if home else 'away_rest',7))
                h=history[(team,pos)];b=average(h,season)
                x=np.r_[b,(h[-1][1] if h else 0)-b,average(allowed[(opp,pos)],season),
                         average(adjusted[(opp,pos)],season),factor_state.row(r)]
                neutral=x.copy()
                # Neutralize opponent defense, opponent offense and opponent residuals.
                ix=[2,3]+list(range(4+9,4+21))+list(range(4+23,4+25))
                neutral[ix]=model[0].mean_[ix]
                p,n=weight*np.maximum(0,model.predict(np.array([x,neutral])))+(1-weight)*b
                out.append(dict(team=team,pos=pos,week=int(g['week']),opponent=opp,
                                projection=round(float(p),2),neutral_opponent=round(float(n),2),
                                matchup_bonus=round(float(p-n),2),rolling_baseline=round(b,2)))
    return dict(scoring='PPR',unit='All players at one position on one team',
                method='Independent team-total Ridge/baseline blend; bonus versus training-mean opponent context, same team/venue/rest.',
                caveat='Experimental team-total model, distinct from individual projections and Subvertadown baseline definition.',
                evaluation_period='2025 weeks 13-18, coefficients fitted on 2024',
                validation=report,forecasts=out)
