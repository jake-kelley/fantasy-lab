"""Position-specific inputs and exposure-scaled rare-event shrinkage candidates."""
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .model import KEYS, OFF, KICK, IDP, USAGE, targets
from .dst_experiment import FEATURE_NAMES

INPUTS = {
    'QB': ['passing_yards','passing_tds','passing_interceptions','rushing_yards',
           'rushing_tds','attempts','carries','offense_pct'],
    'RB': ['rushing_yards','rushing_tds','receptions','receiving_yards','receiving_tds',
           'fumbles_lost_total','carries','targets','receiving_air_yards','offense_pct'],
    'WR': ['receptions','receiving_yards','receiving_tds','rushing_yards','rushing_tds',
           'targets','receiving_air_yards','carries','offense_pct'],
    'TE': ['receptions','receiving_yards','receiving_tds','targets','receiving_air_yards','offense_pct'],
    'K': KICK+['fg_att','pat_att'],
    'DL': IDP+['defense_pct'], 'LB': IDP+['defense_pct'], 'DB': IDP+['defense_pct'],
}
# Outcomes shrink toward a training-only event rate times the estimated exposure.
EXPOSURES = {'passing_tds':'attempts','passing_interceptions':'attempts',
             'rushing_tds':'carries','receiving_tds':'targets',
             'fg_missed':'fg_att','pat_missed':'pat_att'}
IDP_RARE = ['def_sacks','def_interceptions','def_fumbles_forced','fumble_recovery_opp','def_tds','def_safeties']


class PositionCandidate:
    def __init__(self, pos, alpha=100, retention=.5, context=True, market=False):
        self.pos,self.alpha,self.retention,self.context,self.market=pos,alpha,retention,context,market
        # No duplicate team box scores or unrelated positions' statistics.
        self.indices=[FEATURE_NAMES.index(prefix+k) for prefix in ['avg:','change:'] for k in INPUTS[pos]]
        self.indices += [FEATURE_NAMES.index(k) for k in ['history','season_history','gap','team_change']]
        if not context:
            self.indices += [FEATURE_NAMES.index(k) for k in ['home','indoor','rest']]

    def x(self, r):
        base=r['x'][self.indices]
        base=np.r_[base,r['factor_x']] if self.context else base
        return np.r_[base,r['market_x']] if self.market else base

    def fit(self, rows):
        rows=[r for r in rows if r['pos']==self.pos]
        if self.market:
            self.fallback=PositionCandidate(self.pos,self.alpha,self.retention,self.context).fit(rows)
            rows=[r for r in rows if np.isfinite(r['market_x']).all()]
        self.scored=targets(self.pos)
        self.exposures=({k:'defense_pct' for k in IDP_RARE} if self.pos in ['DL','LB','DB'] else
                        {k:v for k,v in EXPOSURES.items() if k in self.scored})
        self.output=list(dict.fromkeys(self.scored+list(self.exposures.values())))
        def value(r,k):
            if k in KEYS: return r['y'][KEYS.index(k)]
            return float(r.get(k,0) or 0)
        y=np.array([[value(r,k) for k in self.output] for r in rows])
        self.prior={k:float(y[:,self.output.index(k)].sum()/max(y[:,self.output.index(v)].sum(),1))
                    for k,v in self.exposures.items()}
        self.model=make_pipeline(StandardScaler(),Ridge(alpha=self.alpha))
        self.model.fit(np.array([self.x(r) for r in rows]),y)
        return self

    def predict(self, rows):
        result=np.zeros((len(rows),len(KEYS)))
        ix=[i for i,r in enumerate(rows) if r['pos']==self.pos]
        if self.market:
            missing=[i for i in ix if not np.isfinite(rows[i]['market_x']).all()]
            if missing:result[missing]=self.fallback.predict([rows[i] for i in missing])
            ix=[i for i in ix if np.isfinite(rows[i]['market_x']).all()]
        if not ix: return result
        raw=np.maximum(0,self.model.predict(np.array([self.x(rows[i]) for i in ix])))
        for k,exposure in self.exposures.items():
            j=self.output.index(k);e=self.output.index(exposure)
            if exposure=='defense_pct': raw[:,e]=np.minimum(raw[:,e],1)
            raw[:,j]=self.retention*raw[:,j]+(1-self.retention)*self.prior[k]*raw[:,e]
        for k in self.scored: result[ix,KEYS.index(k)]=raw[:,self.output.index(k)]
        return result
