import copy
import json
import unittest

from pipeline.consensus import merge_publisher, registry
from pipeline.publishers import parse_rotoballer, parse_espn, parse_fftoday, order_projections


class PublisherTests(unittest.TestCase):
    def test_rotoballer_edition_and_positional_order(self):
        page = 'var rbRankings = ' + json.dumps(dict(currentWeek='2', season='2026')) + ';'
        data = dict(total=3, data=[dict(rank=i, position=pos, player_id=i,
                    player=dict(name=str(i)), team='DET', updated_at='2026-09-17 12:00:00')
                    for i, pos in [(1, 'RB'), (2, 'WR'), (3, 'RB')]])
        self.assertEqual([r['rank'] for r in parse_rotoballer(page, data, 2026, 2)], [1, 1, 2])
        with self.assertRaises(ValueError): parse_rotoballer(page, data, 2026, 3)
        with self.assertRaises(ValueError): parse_rotoballer(page, data, 2025, 2)
        data['total'] = 4
        with self.assertRaises(ValueError): parse_rotoballer(page, data, 2026, 2)

    def test_fftoday_rejects_wrong_scoring_and_edition(self):
        html = '<title>Running Back Projections: 2026 Week 2 - FF Today</title><p>FFToday PPR Scoring:</p><table><tr><td></td><td><a href="/stats/players/123/Test">Test</a></td><td>DET</td><td>BUF</td><td>4</td><td>20.1</td></tr></table>'
        rows = parse_fftoday(html, 2026, 2, 'RB', 'now')
        self.assertEqual(rows[0]['points'], 20.1)
        for bad in [html.replace('Week 2', 'Week 12'), html.replace('2026', '2025'), html.replace('PPR Scoring', 'Half-PPR Scoring')]:
            with self.assertRaises(ValueError): parse_fftoday(bad, 2026, 2, 'RB', 'now')

    def test_midrank_and_duplicate_identity(self):
        rows = [dict(name=str(i), player_id=i, position='RB', points=p) for i,p in enumerate([20,18,18,12])]
        self.assertEqual([r['rank'] for r in order_projections(rows)], [1,2.5,2.5,4])
        with self.assertRaises(ValueError): order_projections(rows + [dict(rows[0])])

    def test_espn_uses_weekly_projected_stats_and_checks_scoring(self):
        settings = dict(seasonId=2026, settings=dict(scoringSettings=dict(playerRankType='PPR', scoringItems=[
            dict(statId=53, points=1), dict(statId=4, points=4)])))
        players = []
        for i, pos in enumerate([1,2,3,4,5,16]):
            stat = dict(seasonId=2026, scoringPeriodId=2, statSourceId=1, statSplitTypeId=1,
                        appliedTotal=10, stats={'53': 2, '4': 2})
            players.append(dict(player=dict(id=i, fullName=str(i), defaultPositionId=pos, proTeamId=1,
                stats=[stat, dict(stat, scoringPeriodId=0, appliedTotal=999), dict(stat, statSourceId=0, appliedTotal=999)])))
        data = dict(players=players)
        rows = parse_espn(data, settings, {'1':'ATL'}, 2026, 2, 'now')
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r['points'] == 10 for r in rows))
        with self.assertRaises(ValueError): parse_espn(data, settings, {}, 2026, 3, 'now')
        bad = copy.deepcopy(settings); bad['settings']['scoringSettings']['scoringItems'][0]['points'] = .5
        with self.assertRaises(ValueError): parse_espn(data, bad, {}, 2026, 2, 'now')
        players[0]['player']['stats'][0]['appliedTotal'] = 11
        with self.assertRaises(ValueError): parse_espn(data, settings, {}, 2026, 2, 'now')

    def test_defense_names_merge_by_team_and_duplicate_votes_fail(self):
        rows = {'DST:1': dict(name='Denver Broncos', team='DEN', position='DST', ranks=[])}
        vote = dict(source='espn', player_id=99, name='Broncos D/ST', team='DEN', position='DST', rank=1, published='now')
        merge_publisher(rows, [vote])
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError): merge_publisher(rows, [vote])

    def test_historical_registry_stays_frozen(self):
        self.assertEqual([s['id'] for s in registry()], ['285','95','835','2340','1169','22','2791'])

    def test_verified_name_aliases_share_one_player(self):
        rows = {'RB:1': dict(name='Kenny Gainwell', team='TB', position='RB', ranks=[])}
        merge_publisher(rows, [dict(source='fftoday', player_id=3, name='Kenneth Gainwell', team='TB',
                                   position='RB', rank=40, published='now')])
        self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()
