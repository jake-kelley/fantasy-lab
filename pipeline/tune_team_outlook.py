"""Freeze team-total weights using 2024 and early-2025 development folds only."""
import json
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .data import ROOT
from .tune_positions import load
from .team_outlook import historical


def main():
    ds,_,_=load();rows,*_=historical(ds);chosen={};audit={}
    for pos in ['RB','WR','TE']:
        selected=[r for r in rows if r['pos']==pos];results=[]
        for alpha in [30,100,300]:
            actual=[];pred=[];base=[]
            for year,end,last in [(2024,8,10),(2024,10,12),(2025,0,6),(2025,6,12)]:
                train=[r for r in selected if (r['season'],r['week'])<=(year,end) and
                       (r['season']>2024 or r['week']>=5)]
                test=[r for r in selected if r['season']==year and end<r['week']<=last]
                m=make_pipeline(StandardScaler(),Ridge(alpha=alpha))
                m.fit(np.array([r['group_x'] for r in train]),[r['group_y'] for r in train])
                pred.extend(np.maximum(0,m.predict(np.array([r['group_x'] for r in test]))))
                actual.extend([r['group_y'] for r in test]);base.extend([r['group_baseline'] for r in test])
            for weight in [0,.25,.5,.75,1]:
                p=weight*np.array(pred)+(1-weight)*np.array(base)
                results.append(dict(alpha=alpha,weight=weight,mae=float(np.mean(abs(np.array(actual)-p)))))
        best=min(results,key=lambda x:x['mae']);chosen[pos]={k:best[k] for k in ['alpha','weight']};audit[pos]=results
        print(pos,best)
    (ROOT/'research'/'team-selection.json').write_text(json.dumps(chosen,indent=2))
    (ROOT/'research'/'team-selection-audit.json').write_text(json.dumps(audit,indent=2))


if __name__=='__main__':main()
