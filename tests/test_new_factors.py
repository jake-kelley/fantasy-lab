import copy
import unittest
import numpy as np
from pipeline.dst_factors import annotate
from pipeline.market_context import market_features
from pipeline.position_candidate import PositionCandidate
from pipeline.dst_experiment import FEATURE_NAMES
from pipeline.model import KEYS, vector
from pipeline.team_outlook import historical


class NewFactorTests(unittest.TestCase):
    def test_team_totals_do_not_use_same_week_outcomes(self):
        rows=[]
        for week in [1,2,3]:
            for team,opp in [('BUF','NE'),('NE','BUF')]:
                rows.append(dict(pos='WR',season=2024,week=week,team=team,
                                 opponent_team=opp,factor_x=np.zeros(28),
                                 y=vector(dict(receiving_yards=100))))
        before=historical(rows)[0]
        changed=copy.deepcopy(rows)
        changed[2]['y']=vector(dict(receiving_yards=900))
        after=historical(changed)[0]
        for a,b in zip(before[:4],after[:4]):
            np.testing.assert_array_equal(a['group_x'],b['group_x'])
        self.assertFalse(np.array_equal(before[4]['group_x'],after[4]['group_x']))

    def test_market_sign_and_no_postgame_inputs(self):
        game=dict(total_line='45.5',spread_line='2.5',home_score='99',wind='99')
        np.testing.assert_array_equal(market_features(game,True),[24,21.5])
        np.testing.assert_array_equal(market_features(game,False),[21.5,24])
        self.assertTrue(np.isnan(market_features({},True)).all())
        game.update(home_score='0',wind='0')
        np.testing.assert_array_equal(market_features(game,True),[24,21.5])

    def test_market_missing_uses_statistical_fallback(self):
        rng=np.random.default_rng(7)
        rows=[dict(pos='K',x=rng.normal(size=len(FEATURE_NAMES)),factor_x=rng.normal(size=28),
                   market_x=np.array([24.,21.])+rng.normal(size=2),y=rng.uniform(0,2,len(KEYS)),
                   fg_att=3,pat_att=2) for _ in range(40)]
        model=PositionCandidate('K',market=True).fit(rows)
        missing=dict(rows[0],market_x=np.array([np.nan,np.nan]))
        np.testing.assert_array_equal(model.predict([missing]),model.fallback.predict([missing]))
        self.assertTrue(np.isfinite(model.predict([rows[0],missing])).all())

    def test_factor_history_cannot_see_current_or_future_outcomes(self):
        rows=[];teams={}
        for week in [1,2]:
            for team,opp in [('BUF','NE'),('NE','BUF')]:
                r=dict(pos='DST',season=2024,week=week,game_id=str(week),team=team,
                       opponent_team=opp,home=float(team=='BUF'),roof_indoor=0,rest=7,
                       points_allowed=20)
                r['y']=vector(r);rows.append(r)
                teams[(str(week),team)]=dict(attempts=30,carries=20,sacks_suffered=2,passing_yards=200)
        annotate(rows,teams)
        expected=[r['factor_x'].copy() for r in rows]
        changed=copy.deepcopy(rows);other=copy.deepcopy(teams)
        changed[-1]['points_allowed']=99;other[('2','BUF')]['passing_yards']=999
        annotate(changed,other)
        for a,r in zip(expected,changed):np.testing.assert_array_equal(a,r['factor_x'])
        np.testing.assert_array_equal(expected[0],expected[1]-np.r_[np.zeros(25),-1,0,0])


if __name__=='__main__':unittest.main()
