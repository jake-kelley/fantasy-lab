"""Read-only agreement audit. Expert screenshots are never fitted as targets."""
import json
import unicodedata
import numpy as np
import requests
from scipy.stats import spearmanr
from .data import ROOT


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value).lower() if c.isalnum())


def compare(data,snapshot):
    result={}
    for pos in ['QB','K','DST']:
        lookup={norm(p['team'] if pos=='DST' else p['name']):f['mean'][2]
                for p in data['players'] if p['pos']==pos for f in p['forecasts'] if f['week']==2}
        # Same surname/team; nflverse uses Andy while screenshot uses Andres.
        if 'andyborregales' in lookup:lookup['andresborregales']=lookup['andyborregales']
        pairs=[dict(name=n,fieldwork=lookup[norm(n)],subvertadown=v)
               for n,v in snapshot['values'][pos] if norm(n) in lookup]
        a=[p['fieldwork'] for p in pairs];b=[p['subvertadown'] for p in pairs]
        result[pos]=dict(n=len(pairs),rank_correlation=float(spearmanr(a,b).statistic),
                         mean_absolute_difference=float(np.mean(abs(np.array(a)-b))),rows=pairs)
    if data.get('team_outlook'):
        for pos in ['RB','WR']:
            lookup={r['team']:r for r in data['team_outlook']['forecasts'] if r['pos']==pos and r['week']==2}
            pairs=[dict(team=t,fieldwork=lookup[t]['projection'],subvertadown=b+m,
                        fieldwork_bonus=lookup[t]['matchup_bonus'],subvertadown_bonus=m)
                   for t,b,m in snapshot['values'][pos]]
            a=[p['fieldwork'] for p in pairs];b=[p['subvertadown'] for p in pairs]
            result[pos]=dict(n=len(pairs),rank_correlation=float(spearmanr(a,b).statistic),
                             mean_absolute_difference=float(np.mean(abs(np.array(a)-b))),
                             bonus_rank_correlation=float(spearmanr([p['fieldwork_bonus'] for p in pairs],
                                                                   [p['subvertadown_bonus'] for p in pairs]).statistic),rows=pairs)
    return result


if __name__=='__main__':
    snapshot=json.loads((ROOT/'research'/'subvertadown-week2-snapshot.json').read_text())
    current=requests.get('https://jake-kelley.github.io/fantasy-lab/data/projections.json',timeout=30)
    current.raise_for_status();current=current.json()
    candidate=json.loads((ROOT/'site'/'data'/'projections.json').read_text(encoding='utf-8'))
    result=dict(note='Agreement, not accuracy. Different scoring and baseline definitions. Expert values never used in fitting.',
                published_version=current['version'],candidate_version=candidate['version'],
                published=compare(current,snapshot),candidate=compare(candidate,snapshot))
    (ROOT/'research'/'snapshot-comparison.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({side:{p:{k:v for k,v in r.items() if k!='rows'} for p,r in result[side].items()}
                      for side in ['published','candidate']},indent=2))
