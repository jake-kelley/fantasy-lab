"""Reproducible all-position development and retrospective comparison; no expert targets."""
import argparse
import csv
import json
import pickle
from pathlib import Path
import numpy as np
from .data import ROOT
from .model import POSITIONS, Estimator, dataset, prepare, score, distribution
from .dst_experiment import CompactDST
from .dst_factors import annotate, OpportunityDST
from .position_candidate import PositionCandidate


def load():
    path=ROOT/'output'/'tuning-dataset.pkl'
    if path.exists():
        with path.open('rb') as f: return pickle.load(f)
    def read(name):
        with (ROOT/'.cache'/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    players=sum([read(f'stats_player_week_{y}.csv') for y in [2024,2025,2026]],[])
    teams=sum([read(f'stats_team_week_{y}.csv') for y in [2024,2025,2026]],[])
    snaps=sum([read(f'snap_counts_{y}.csv') for y in [2024,2025,2026]],[])
    games=read('games.csv')
    rows,ti,_=prepare(players,teams,snaps,read('players.csv'),games)
    ds,_=dataset(rows,ti)
    annotate(ds,ti)
    path.parent.mkdir(exist_ok=True)
    with path.open('wb') as f:pickle.dump((ds,ti,games),f)
    return ds,ti,games


def make(pos, cfg):
    if cfg['family']=='current':return CompactDST(0) if pos=='DST' else Estimator()
    if cfg['family']=='blend':return BaselineBlend(pos,cfg['weight'])
    if cfg['family']=='role_blend':return BaselineBlend(pos,cfg['weight'],cfg['bandwidth'])
    if pos=='DST':return OpportunityDST(**{k:v for k,v in cfg.items() if k!='family'})
    return PositionCandidate(pos,**{k:v for k,v in cfg.items() if k!='family'})


class BaselineBlend:
    def __init__(self,pos,weight,bandwidth=None):self.pos,self.weight,self.bandwidth=pos,weight,bandwidth
    def fit(self,rows):
        self.model=Estimator().fit([r for r in rows if r['pos']==self.pos])
        return self
    def predict(self,rows):
        pred=self.model.predict(rows)
        for i,r in enumerate(rows):
            if r['pos']==self.pos:
                base=r['baseline'] if self.bandwidth is None else r[f'role_{self.bandwidth}']
                pred[i]=self.weight*pred[i]+(1-self.weight)*base
        return pred


def points(preds, residuals, pos):
    return np.array([float(distribution(p,residuals,pos)[0][2]) for p in preds]) if pos=='DST' else score(preds,pos)


def metrics(actual,predicted):
    delta=np.asarray(actual)-predicted
    return dict(n=len(delta),mae=float(np.mean(abs(delta))),rmse=float(np.sqrt(np.mean(delta**2))))


def run(phase):
    ds,_,games=load()
    from .market_context import annotate_market
    annotate_market(ds,games)
    from .role_history import annotate_roles
    annotate_roles(ds)
    extended=phase.startswith('extended-')
    selection_path=ROOT/'research'/('position-selection-extended.json' if extended else 'position-selection.json')
    if phase.endswith('select'):
        selection=dict(period=('2024 weeks 9-12 plus 2025 weeks 1-12; chronological expanding fits'
                               if extended else '2024 weeks 9-12; expanding training ends weeks 8 and 10'),
                       criterion='MAE',history=dict(decay=.9,season_weight=.35,pseudo_games=4),positions={})
        for pos in POSITIONS:
            rows=[r for r in ds if r['pos']==pos]
            configs=[dict(family='current')]
            for alpha in [30,100,300]:
                for retention in [0,.5,1]:
                    configs.append(dict(family='factors',alpha=alpha,retention=retention,
                                        **({'rates':True} if pos=='DST' else {'context':True})))
            # Ablation: count-based DST; or no new team context for the other positions.
            configs.append(dict(family='factors',alpha=100,retention=.5,
                                **({'rates':False} if pos=='DST' else {'context':False})))
            if extended and pos!='DST':
                configs.extend([dict(family='blend',weight=w) for w in [0,.25,.5,.75]])
            if extended and pos=='QB':
                configs.extend([dict(family='role_blend',weight=w,bandwidth=b)
                                for b in [.15,.35] for w in [0,.25,.5,.75]])
            if extended:
                for alpha in [30,100,300]:
                    for retention in [0,.5,1]:
                        configs.append(dict(family='factors',alpha=alpha,retention=retention,market=True,
                                            **({'rates':True} if pos=='DST' else {'context':True})))
            results=[]
            for cfg in configs:
                actual=[];predicted=[]
                folds=[(2024,8,10),(2024,10,12)]+([(2025,0,6),(2025,6,12)] if extended else [])
                for year,end,last in folds:
                    train=[r for r in rows if (r['season'],r['week'])<=(year,end) and
                           (r['season']>2024 or r['week']>=5)]
                    test=[r for r in rows if r['season']==year and end<r['week']<=last]
                    model=make(pos,cfg).fit(train)
                    residuals=np.array([r['y'] for r in train])-model.predict(train)
                    predicted.extend(points(model.predict(test),residuals,pos))
                    actual.extend(score(np.array([r['y'] for r in test]),pos))
                results.append(dict(config=cfg,**metrics(actual,np.array(predicted))))
            best=min(results,key=lambda r:r['mae'])
            selection['positions'][pos]=dict(selected=best['config'],results=results)
            print(pos,best,flush=True)
        selection_path.write_text(json.dumps(selection,indent=2)+'\n',encoding='utf-8')
    else:
        selection=json.loads(selection_path.read_text(encoding='utf-8'))
        result=dict(selection=selection,positions={})
        for pos in POSITIONS:
            rows=[r for r in ds if r['pos']==pos]
            train=[r for r in rows if r['season']==2024 and r['week']>=5]
            warm=[r for r in train if r['week']<=12]
            cal=[r for r in train if r['week']>=13]
            test=[r for r in rows if r['season']==2025 and (not extended or r['week']>=13)]
            actual=score(np.array([r['y'] for r in test]),pos)
            compare={}
            for label,cfg in [('current',dict(family='current')),('candidate',selection['positions'][pos]['selected'])]:
                model=make(pos,cfg).fit(warm)
                cp=model.predict(cal);residuals=np.array([r['y'] for r in cal])-cp
                errors=score(np.array([r['y'] for r in cal]),pos)-points(cp,residuals,pos)
                model.fit(train);pp=points(model.predict(test),residuals,pos)
                lo,hi=np.quantile(errors,[.1,.9])
                compare[label]=dict(**metrics(actual,pp),coverage=float(np.mean((actual>=pp+lo)&(actual<=pp+hi))))
            compare['baseline']=metrics(actual,np.array([r['baseline_scores'][2] for r in test]))
            result['positions'][pos]=compare
            print(pos,compare,flush=True)
        (ROOT/'research'/('position-evaluation-extended.json' if extended else 'position-evaluation.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['select','evaluate','extended-select','extended-evaluate'])
    run(parser.parse_args().phase)
