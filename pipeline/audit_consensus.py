"""Retrospective archive audit, never represented as an immutable pregame backtest."""
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import gzip
import statistics
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import spearmanr

from .consensus import registry, fetch_feed, name_key, aggregate
from .data import Sources, ROOT, normalize_team, number

DEPTH = {'QB': 24, 'RB': 50, 'WR': 60, 'TE': 24}
TOP = {'QB': 6, 'RB': 12, 'WR': 12, 'TE': 6}
PACIFIC = ZoneInfo('America/Los_Angeles')
EASTERN = ZoneInfo('America/New_York')


def before_kickoff(published, game, strict=False):
    stamp = datetime.fromisoformat(published).replace(tzinfo=PACIFIC)
    kickoff = datetime.fromisoformat(game['gameday'] + 'T' + game['gametime']).replace(tzinfo=EASTERN)
    # Date-only variant avoids relying on the feed's undocumented hour timezone.
    return stamp.date() < kickoff.date() if strict else stamp < kickoff


def metrics(entries, top):
    if len(entries) < max(10, top + 2):
        return None
    ranks = np.array([e['rank'] for e in entries])
    points = np.array([e['points'] for e in entries])
    if np.ptp(points) == 0 or np.ptp(ranks) == 0:
        return None
    rho = float(spearmanr(-ranks, points).statistic)
    # Fractional boundary ties: all tied players share remaining selection slots.
    threshold = sorted(ranks)[top - 1]
    chosen = points[ranks < threshold].sum()
    remaining = top - int((ranks < threshold).sum())
    chosen += float(points[ranks == threshold].mean()) * remaining
    oracle = float(np.sort(points)[-top:].sum())
    return dict(rho=rho, players=len(entries), top_points_per_pick=float(chosen / top),
                hindsight_gap_per_pick=float((oracle - chosen) / top))


def summarize(items):
    if not items:
        return dict(weeks=0, players=0, rho=None, top_points_per_pick=None, hindsight_gap_per_pick=None)
    return dict(weeks=len(items), players=sum(x['players'] for x in items),
                **{k: round(statistics.mean(x[k] for x in items), 4)
                   for k in ['rho', 'top_points_per_pick', 'hindsight_gap_per_pick']})


def run():
    source = Sources()
    games_raw = source.csv('schedules', 'games.csv', 86400 * 30)
    games = {}
    for g in games_raw:
        if g['game_type'] == 'REG' and g['gametime']:
            for team in [g['home_team'], g['away_team']]:
                games[int(g['season']), int(g['week']), normalize_team(team)] = g
    actual, roster_ids, roster_names = {}, defaultdict(list), defaultdict(list)
    for year in [2024, 2025]:
        stats = source.csv('stats_player', f'stats_player_week_{year}.csv', 86400 * 30)
        for r in stats:
            if r['season_type'] == 'REG':
                actual[year, int(r['week']), r['player_id']] = r
        rosters = source.csv('weekly_rosters', f'roster_weekly_{year}.csv', 86400 * 30)
        for r in rosters:
            if r['game_type'] != 'REG' or not r['gsis_id'] or r['position'] not in DEPTH:
                continue
            base = year, int(r['week']), r['position']
            if r['yahoo_id']:
                roster_ids[(*base, r['yahoo_id'])].append(r)
            roster_names[(*base, name_key(r['full_name']))].append(r)

    jobs = [(s['id'], year, week, pos) for s in registry() for year in [2024, 2025]
            for week in range(1, 18) for pos in DEPTH]
    archive, observations, manifest = [], {}, []
    def task(job):
        try:
            return job, fetch_feed(*job), None
        except Exception as exc:
            return job, None, str(exc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index, ((expert, year, week, pos), result, error) in enumerate(pool.map(task, jobs)):
            audit = dict(source=expert, year=year, week=week, position=pos)
            if error:
                archive.append(dict(audit, status='unavailable', reason=error))
                continue
            data, provenance = result
            manifest.append(provenance)
            counters = Counter()
            records = []
            # Wrong-week archives can otherwise pass through an echoed week parameter.
            dates = [datetime.fromisoformat(g['gameday']).date() for (y,w,t),g in games.items()
                     if (y,w) == (year,week)]
            pub_date = datetime.fromisoformat(data['published']).date()
            if not dates or not min(dates)-timedelta(days=10) <= pub_date <= max(dates):
                archive.append(dict(audit, status='rejected', reason='Publication outside requested game-week window'))
                continue
            for p in data['players']:
                if int(p['rank']) > DEPTH[pos]:
                    continue
                base = year, week, pos
                candidates = roster_ids.get((*base, str(p.get('player_yahoo_id', ''))), [])
                method = 'yahoo_id'
                if not candidates:
                    candidates = roster_names.get((*base, name_key(p['player_name'])), [])
                    method = 'unique_name_position'
                candidates = { (r['gsis_id'],r['team']):r for r in candidates }
                if len(candidates) != 1:
                    counters['unresolved_identity'] += 1
                    continue
                r = next(iter(candidates.values()))
                game = games.get((year, week, normalize_team(r['team'])))
                if not game:
                    counters['no_game'] += 1
                    continue
                if not before_kickoff(data['published'], game):
                    counters['already_started'] += 1
                    continue
                stat = actual.get((year, week, r['gsis_id']))
                # Missing game stats only become zero after a historical roster + game match.
                points = number(stat, 'fantasy_points_ppr') if stat else 0.0
                counters[method] += 1
                counters['rostered_without_stat_row'] += int(stat is None)
                records.append(dict(player=r['gsis_id'], rank=int(p['rank']), points=points,
                                    strict=before_kickoff(data['published'], game, strict=True)))
            observations[expert, year, week, pos] = records
            archive.append(dict(audit, status='available', published=data['published'],
                                eligible=len(records), excluded_or_matched=dict(counters)))
            if index % 100 == 0:
                print(f'Archive audit {index + 1}/{len(jobs)}', flush=True)

    summaries = []
    # Matched comparison requires all seven analysts, same week and same player pool.
    for year in [2024, 2025]:
        for pos in DEPTH:
            values = defaultdict(list)
            for week in range(1, 18):
                panel = {s['id']: observations.get((s['id'], year, week, pos), []) for s in registry()}
                common = set.intersection(*(set(r['player'] for r in rows) for rows in panel.values()))
                strict_common = set.intersection(*(set(r['player'] for r in rows if r['strict']) for rows in panel.values()))
                for expert, records in panel.items():
                    for label, subset in [('own_coverage', records),
                        ('matched_panel', [r for r in records if r['player'] in common]),
                        ('date_only_matched', [r for r in records if r['player'] in strict_common])]:
                        m = metrics(subset, TOP[pos])
                        if m:
                            values[expert, label].append(m)
                for label, pool_ids in [('matched_panel', common), ('date_only_matched', strict_common)]:
                    by_id = {expert: {r['player']:r for r in records} for expert,records in panel.items()}
                    for trim, name in [(False, 'consensus-raw'), (True, 'consensus-filtered')]:
                        records = []
                        for player in sorted(pool_ids):
                            votes = [dict(source=expert, rank=by_id[expert][player]['rank']) for expert in panel]
                            records.append(dict(rank=aggregate(votes, trim)['mean'], points=next(iter(by_id.values()))[player]['points']))
                        m = metrics(records, TOP[pos])
                        if m:
                            values[name, label].append(m)
            for s in registry() + [dict(id='consensus-raw', name='Seven-analyst mean'), dict(id='consensus-filtered', name='Seven-analyst filtered mean')]:
                summaries.append(dict(source=s['id'], name=s['name'], year=year, position=pos,
                    **{label: summarize(values[s['id'], label])
                       for label in ['own_coverage', 'matched_panel', 'date_only_matched']}))
    report = dict(generated_at=datetime.now(timezone.utc).isoformat(), years=[2024, 2025],
        weeks='1–17 regular season', scoring='nflverse fantasy_points_ppr (full PPR, 4-point passing TD)',
        status='Retrospective archive audit; provisional timing, not a certified pregame backtest',
        method=['Equal-weight mean of weekly Spearman correlations; higher is better.',
                'Top-pick points and hindsight gap use QB/TE top 6 and RB/WR top 12 within the evaluated player pool.',
                'Matched panel uses identical players and weeks across all seven analysts. Own-coverage rows cannot establish a fair leaderboard.',
                'Publication timezone inferred as US Pacific by matching live feed times against public expert update epochs; provider has not documented it. Date-only sensitivity requires publication before game day.',
                'Archives may be mutable. The timestamp gate cannot prove that an old record was never edited later.',
                'Fixed rank-depth caps: QB24, RB50, WR60, TE24. Historical weekly rosters resolve identities; rostered players without game-stat rows score zero.',
                'No accuracy weighting or source selection based on these retrospective scores. K/DST excluded from this PPR audit because platform scoring rules differ.'],
        unavailable=['Footballers, Subvertadown, MonCalFF and Boris Chen: no verified machine-readable pregame archive integrated. Boris Chen is also derived consensus, not an additional independent vote.'],
        summary=summaries, archive=archive, manifest=manifest + source.manifest)
    target = ROOT / 'research/consensus-history.json'
    target.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    (ROOT / 'site/data/historical-accuracy.json').write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
    normalized = [dict(source=k[0], year=k[1], week=k[2], position=k[3], players=v)
                  for k,v in observations.items()]
    (ROOT / 'research/consensus-audit-records.json.gz').write_bytes(
        gzip.compress(json.dumps(normalized, sort_keys=True).encode(), mtime=0))
    print(Counter(a['status'] for a in archive))
    for year in [2024, 2025]:
        print(year, [(s['name'], s['position'], s['matched_panel']['weeks'], s['matched_panel']['rho'])
                     for s in summaries if s['year'] == year])
    return report


if __name__ == '__main__':
    run()
