import json
import unittest
from pathlib import Path
import numpy as np
from pipeline.model import KEYS, Features, dataset, distribution, rolling_scores, score


def stats(**kwargs):
    out = np.zeros(len(KEYS))
    for k,v in kwargs.items(): out[KEYS.index(k)] = v
    return out


def row(pid='test', week=1, **values):
    r = dict(player_id=pid, pos='RB', season=2024, week=week, team='BUF', opponent_team='NE',
             home=1, roof_indoor=0, rest=7, date=f'2024-09-{week*7:02d}', game_id=f'g{week}')
    r.update(values);r['y']=stats(**{k:v for k,v in values.items() if k in KEYS})
    return r


class FootballTests(unittest.TestCase):
    def test_offense_scoring(self):
        x=stats(passing_yards=250,passing_tds=2,passing_interceptions=1,rushing_yards=30,
                rushing_tds=1,receptions=3,receiving_yards=20,fumbles_lost_total=1)
        self.assertAlmostEqual(float(score(x,'QB',0)),25)
        self.assertAlmostEqual(float(score(x,'QB',.5)),26.5)
        self.assertAlmostEqual(float(score(x,'QB',1)),28)

    def test_kick_distances_and_misses(self):
        x=stats(fg_made_30_39=1,fg_made_40_49=1,fg_made_50_59=1,fg_made_60_=1,pat_made=2,fg_missed=1,pat_missed=1)
        self.assertEqual(float(score(x,'K')),17)

    def test_defense_bands(self):
        for pa, points in [(0,10),(1,7),(6,7),(7,4),(13,4),(14,1),(20,1),(21,0),(27,0),(28,-1),(34,-1),(35,-4)]:
            self.assertEqual(float(score(stats(points_allowed=pa),'DST')),points)

    def test_dst_baseline_averages_scores_not_average_pa(self):
        rr=[dict(season=2024,y=stats(points_allowed=0)),dict(season=2024,y=stats(points_allowed=40))]
        self.assertAlmostEqual(rolling_scores(rr,2024,'DST')[2],(10*.8-4)/1.8)

    def test_dst_integrates_nonlinear_scoring(self):
        pred=stats(points_allowed=20)
        errors=np.array([stats(points_allowed=-20),stats(points_allowed=20)])
        mean,_=distribution(pred,errors,'DST')
        self.assertAlmostEqual(mean[2],3)
        self.assertNotEqual(mean[2],float(score(pred,'DST')))

    def test_future_outcomes_cannot_change_earlier_features(self):
        first=row(week=1,rushing_yards=10)
        second=row(week=2,rushing_yards=20)
        ds,_=dataset([first,second],{})
        changed=row(week=2,rushing_yards=999)
        other,_=dataset([row(week=1,rushing_yards=10),changed],{})
        np.testing.assert_array_equal(ds[0]['x'],other[0]['x'])
        np.testing.assert_array_equal(ds[1]['x'],other[1]['x'])

    def test_same_week_cannot_leak_between_players(self):
        a=row(pid='a',week=1,rushing_yards=100)
        b=row(pid='b',week=1,rushing_yards=0)
        ds,_=dataset([a,b],{})
        self.assertEqual(ds[1]['baseline_scores'][2],0)
        self.assertEqual(ds[1]['matchup'],0)

    def test_future_horizon_does_not_imply_missed_games(self):
        state=Features();state.players['test'].append(row(week=1,rushing_yards=10))
        next_week=row(week=2);next_week['as_of_date']='2024-09-14'
        later=row(week=3);later['as_of_date']='2024-09-14'
        x,_,_=state.row(next_week);y,_,_=state.row(later)
        differences=np.flatnonzero(x!=y)
        self.assertEqual(len(differences),1) # only target-week feature changes

    def test_empirical_ranges_can_include_zero(self):
        pred=stats(receiving_yards=10)
        errors=np.array([[-2,-2,-2],[2,2,2]])
        _,q=distribution(pred,np.zeros((2,len(KEYS))),'WR',errors)
        self.assertLess(q[0,2],0)

    def test_bundle_integrity_if_present(self):
        path=Path('site/data/projections.json')
        if not path.exists(): self.skipTest('Bundle built after unit tests')
        data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['train_seasons'],[2024,2025])
        self.assertEqual(len(data['validation']),9)
        names={p['name'] for p in data['players']}
        self.assertIn('Drake Maye',names)
        self.assertNotIn('Dwayne Haskins',names)
        self.assertEqual(len([p for p in data['players'] if p['pos']=='DST']),32)
        for p in data['players']:
            for f in p['forecasts']:
                if 'mean' not in f: continue
                self.assertTrue(all(np.isfinite(f['mean'])))
                self.assertTrue(all(a<=b for a,b in zip(f['p10'],f['p90'])))
                self.assertNotEqual(p['team'],f['opponent'])


if __name__=='__main__': unittest.main()
