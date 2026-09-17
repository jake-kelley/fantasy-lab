import copy
import json
import unittest

from pipeline.consensus import aggregate, validate_feed
from pipeline.audit_consensus import before_kickoff, metrics
from pipeline.footballers import parse_page


def votes(values):
    return [dict(source=str(i), rank=v) for i,v in enumerate(values)]


class ConsensusTests(unittest.TestCase):
    def test_outlier_gate_and_zero_mad(self):
        self.assertEqual(aggregate(votes([10]*5+[90]))['excluded'], [])
        result = aggregate(votes([10]*6+[90]))
        self.assertEqual(result['excluded'], ['6'])
        self.assertEqual(result['mean'], 10)
        self.assertGreater(result['raw_mean'], 10)

    def test_symmetric_exclusion_and_cap(self):
        self.assertEqual(aggregate(votes([1]+[20]*6))['excluded'], ['0'])
        self.assertEqual(len(aggregate(votes([1]+[20]*5+[90]))['excluded']), 1)
        self.assertEqual(aggregate(votes([1,3,5,7,9,11,13]))['excluded'], [])
        self.assertEqual(aggregate(votes([10]*6+[90]), False)['excluded'], [])

    def test_duplicate_analyst_rejected(self):
        with self.assertRaises(ValueError):
            aggregate([dict(source='a',rank=1),dict(source='a',rank=2)])

    def test_wrong_week_scoring_expert_and_year_rejected(self):
        row = dict(expert_id='95',year='2025',week='2',position_id='RB',scoring='PPR',
                   published='2025-09-14 09:00:00',players=[dict(player_id=1,rank=1)])
        validate_feed(row,95,2025,2,'RB')
        for field,value in [('scoring','HALF'),('week','1'),('expert_id','22'),('published','2026-09-14 09:00:00')]:
            bad=copy.deepcopy(row);bad[field]=value
            with self.assertRaises(ValueError):validate_feed(bad,95,2025,2,'RB')

    def test_kickoff_gate_pacific_and_dst(self):
        game=dict(gameday='2025-09-14',gametime='13:00')
        self.assertTrue(before_kickoff('2025-09-14 09:59:59',game))
        self.assertFalse(before_kickoff('2025-09-14 10:00:00',game))
        self.assertFalse(before_kickoff('2025-09-14 09:00:00',game,True))
        self.assertTrue(before_kickoff('2025-09-13 23:59:59',game,True))
        winter=dict(gameday='2025-12-14',gametime='13:00')
        self.assertFalse(before_kickoff('2025-12-14 10:00:00',winter))

    def test_metrics_direction_and_tie_boundary(self):
        entries=[dict(rank=i+1,points=20-i) for i in range(12)]
        m=metrics(entries,6)
        self.assertAlmostEqual(m['rho'],1)
        self.assertEqual(m['hindsight_gap_per_pick'],0)
        entries=[dict(rank=1 if i<7 else i,points=i) for i in range(12)]
        self.assertEqual(metrics(entries,6)['top_points_per_pick'],3)

    def test_old_footballers_url_cannot_masquerade_as_history(self):
        html='window.udk.data = '+json.dumps(dict(projections=[dict(season='2026',week='2')]))
        with self.assertRaises(ValueError):parse_page(html,2025,2)


if __name__ == '__main__':
    unittest.main()
