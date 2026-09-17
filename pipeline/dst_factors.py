"""Opponent-adjusted team histories and a pass-play opportunity D/ST candidate.

Pass plays here are official attempts + sacks (not charted dropbacks).
All team updates happen after the entire week's features have been emitted.
"""
from collections import defaultdict
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .data import number
from .model import KEYS, DEF

METRICS = ['pass_plays', 'plays', 'sack_rate', 'interception_rate', 'fumble_rate',
           'epa_per_play', 'yards_per_play', 'points', 'qb_hit_rate']


def offense(raw, defense, points):
    passes = number(raw, 'attempts')+number(raw, 'sacks_suffered')
    plays = passes+number(raw, 'carries')
    return np.array([passes, plays, number(raw, 'sacks_suffered')/max(passes,1),
                     number(raw, 'passing_interceptions')/max(passes,1),
                     number(defense, 'fumble_recovery_opp')/max(plays,1),
                     (number(raw,'passing_epa')+number(raw,'rushing_epa'))/max(plays,1),
                     (number(raw,'passing_yards')+number(raw,'rushing_yards'))/max(plays,1),
                     points, number(defense,'def_qb_hits')/max(passes,1)])


class FactorHistory:
    def __init__(self, decay=.9, season_weight=.35):
        self.decay, self.season_weight = decay, season_weight
        self.off = defaultdict(list)
        self.defense = defaultdict(list)
        self.league = []
        self.league_sum = np.zeros(len(METRICS))
        self.adjustments = defaultdict(list)

    def average(self, history, year, shrink=True):
        prior = self.league_sum/len(self.league) if self.league else np.zeros(len(METRICS))
        recent=history[-16:]
        weights=np.array([self.decay**(len(recent)-1-i)*(self.season_weight if s<year else 1)
                          for i,(s,_) in enumerate(recent)])
        if not len(recent): return prior
        # Four pseudo-games at the available historical league mean.
        mass=4 if shrink else 0
        return (sum(w*v for w,(_,v) in zip(weights,recent))+mass*prior)/(sum(weights)+mass)

    def row(self, r):
        defending=r['pos'] in ['DST','DL','LB','DB']
        own=self.average((self.defense if defending else self.off)[r['team']],r['season'])
        opp=self.average((self.off if defending else self.defense)[r['opponent_team']],r['season'])
        # Include the other side's offense once, not duplicate offensive inputs.
        own_off=self.average(self.off[r['team'] if defending else r['opponent_team']],r['season'])
        adjustments=[]
        for team in [r['team'],r['opponent_team']]:
            h=self.adjustments[team][-8:]
            weights=[self.decay**(len(h)-1-i)*(self.season_weight if s<r['season'] else 1)
                     for i,(s,_) in enumerate(h)]
            adjustments.extend((sum(w*v for w,(_,v) in zip(weights,h))/(sum(weights)+4)
                                if h else np.zeros(2)).tolist())
        return np.r_[own,opp,own_off[[1,5,7]],adjustments,
                     r['home'],r['roof_indoor'],min(r['rest'],21)/7]

    def update(self, batch, team_index):
        pending=[]
        by_game_team={(r['game_id'],r['team']):r for r in batch}
        for r in batch:
            other=by_game_team[(r['game_id'],r['opponent_team'])]
            own_raw=team_index[(r['game_id'],r['team'])]
            opp_raw=team_index[(r['game_id'],r['opponent_team'])]
            o=offense(own_raw,opp_raw,number(other,'points_allowed'))
            d=offense(opp_raw,own_raw,number(r,'points_allowed'))
            # Opponent-adjusted points: allowed minus offense's previous expectation;
            # scored minus opposing defense's previous expectation. No same-week updates.
            delta=np.array([d[7]-self.average(self.off[r['opponent_team']],r['season'])[7],
                            o[7]-self.average(self.defense[r['opponent_team']],r['season'])[7]])
            pending.append((r,o,d,delta))
        for r,o,d,delta in pending:
            self.off[r['team']].append((r['season'],o))
            self.defense[r['team']].append((r['season'],d))
            self.adjustments[r['team']].append((r['season'],delta))
            self.league.append((r['season'],o))
            self.league_sum += o
            r['opportunity_target']=np.r_[d[[0,1,2,3,4,7]]]


def annotate(rows, team_index, decay=.9, season_weight=.35):
    state=FactorHistory(decay,season_weight)
    weeks=defaultdict(list)
    for r in rows: weeks[(r['season'],r['week'])].append(r)
    for key in sorted(weeks):
        batch=weeks[key]
        for r in batch: r['factor_x']=state.row(r)
        state.update([r for r in batch if r['pos']=='DST'],team_index)
    return state


class OpportunityDST:
    def __init__(self, alpha=100, retention=.5, rates=True, market=False):
        self.alpha,self.retention,self.rates,self.market=alpha,retention,rates,market

    def x(self,r):return np.r_[r['factor_x'],r['market_x']] if self.market else r['factor_x']

    def fit(self, rows):
        rows=[r for r in rows if r['pos']=='DST']
        if self.market:
            self.fallback=OpportunityDST(self.alpha,self.retention,self.rates).fit(rows)
            rows=[r for r in rows if np.isfinite(r['market_x']).all()]
        y=np.array([r['y'] for r in rows])
        self.prior=y.mean(axis=0)
        targets=np.array([r['opportunity_target'] for r in rows])
        self.rate_prior=np.array([sum(targets[:,i]*targets[:,exposure])/sum(targets[:,exposure])
                                  for i,exposure in [(2,0),(3,0),(4,1)]])
        self.indices=[KEYS.index(k) for k in ['def_sacks','def_interceptions','fumble_recovery_opp','points_allowed']]
        self.model=make_pipeline(StandardScaler(),Ridge(alpha=self.alpha))
        self.model.fit(np.array([self.x(r) for r in rows]),targets if self.rates else y[:,self.indices])
        return self

    def predict(self, rows):
        result=np.zeros((len(rows),len(KEYS)))
        ix=[i for i,r in enumerate(rows) if r['pos']=='DST']
        if self.market:
            missing=[i for i in ix if not np.isfinite(rows[i]['market_x']).all()]
            if missing:result[missing]=self.fallback.predict([rows[i] for i in missing])
            ix=[i for i in ix if np.isfinite(rows[i]['market_x']).all()]
        if not ix: return result
        values=np.maximum(0,self.model.predict(np.array([self.x(rows[i]) for i in ix])))
        for j,i in enumerate(ix):
            p=self.prior.copy()
            if self.rates:
                passes,plays=values[j,:2]
                rates=np.clip(values[j,2:5],0,1)
                rates[1:]=self.retention*rates[1:]+(1-self.retention)*self.rate_prior[1:]
                p[self.indices]=[passes*rates[0],passes*rates[1],plays*rates[2],values[j,5]]
            else:
                p[self.indices]=values[j]
                for k in self.indices[1:3]:p[k]=self.retention*p[k]+(1-self.retention)*self.prior[k]
            result[i]=p
        return result
