"""Free, attributed weekly analyst ranks. Never substitute consensus for an analyst."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import statistics
from urllib.parse import urlencode

from .data import ROOT, Sources, normalize_team

POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
ACCURACY_URL = 'https://www.fantasypros.com/2026/01/2025-fantasy-football-rankings-most-accurate-experts/'
EXPERTS = [
    (285, 'Dalton Del Don', 'dalton-del-don', 6),
    (95, 'Kevin Hanson', None, 7),
    (835, 'Kev Wheeler', 'kevin-wheeler', 20),
    (2340, 'James Emrick-Wilson', 'james-emrick-wilson', 24),
    (1169, 'Elisha Twerski', 'elisha-twerski', 30),
    (22, 'Pat Fitzmaurice', 'pat-fitzmaurice', 31),
    (2791, 'Frank Ammirante', 'frank-ammirante', 35),
]


def registry():
    return [dict(id=str(i), name=n, family='FantasyPros-hosted individual analyst',
                 url=f'https://www.fantasypros.com/nfl/rankings/{slug}.php?type=weekly&scoring=PPR&position=RB'
                 if slug else 'https://eatdrinkandsleepfootball.com/fantasy/rankings/weekly.html',
                 accuracy_rank_2025=r, accuracy_url=ACCURACY_URL,
                 accuracy_note='FantasyPros 2025 overall HALF-PPR competition; not a Fieldwork PPR result.')
            for i, n, slug, r in EXPERTS]


def name_key(name):
    words = re.sub(r'[^a-z0-9 ]', '', name.lower()).split()
    return ''.join(w for w in words if w not in {'jr', 'sr', 'ii', 'iii', 'iv', 'v'})


def feed_url(expert, year, week, pos):
    return 'https://partners.fantasypros.com/api/v1/expert-rankings.php?' + urlencode(
        dict(sport='NFL', year=year, week=week, id=expert, position=pos, type='WEEKLY', scoring='PPR'))


def validate_feed(data, expert, year, week, pos):
    expected = {'expert_id': str(expert), 'year': str(year), 'week': str(week),
                'position_id': pos, 'scoring': 'PPR'}
    for key, value in expected.items():
        if str(data.get(key)) != value:
            raise ValueError(f'{key}: expected {value}, got {data.get(key)}')
    if not data.get('published') or not data.get('players'):
        raise ValueError('No dated ranks published for requested week')
    stamp = datetime.fromisoformat(data['published'])
    if stamp.year != year:
        raise ValueError('Publication year does not match requested season')
    seen = set()
    for p in data['players']:
        if p['player_id'] in seen or int(p['rank']) < 1:
            raise ValueError('Duplicate player or invalid rank')
        seen.add(p['player_id'])
    return data


def fetch_feed(expert, year, week, pos, refresh=False):
    source = Sources(refresh)
    url = feed_url(expert, year, week, pos)
    data = source.json(f'ranks-{expert}-{year}-{week}-{pos}.json', url,
                       ttl=1800 if year >= datetime.now().year else 86400 * 30)
    return validate_feed(data, expert, year, week, pos), source.manifest[0]


def aggregate(ranks, trim=True):
    """Symmetric robust rule, >=7 distinct analysts; never force an exclusion."""
    if len({r['source'] for r in ranks}) != len(ranks):
        raise ValueError('An analyst must have exactly one vote')
    values = [r['rank'] for r in ranks]
    if not values:
        raise ValueError('No ranks')
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    threshold = max(5, 3 * 1.4826 * mad)
    excluded = set()
    if trim and len(values) >= 7:
        candidates = sorted((r for r in ranks if abs(r['rank'] - median) > threshold),
                            key=lambda r: (-abs(r['rank'] - median), r['source']))
        excluded = {r['source'] for r in candidates[:math.floor(len(values) * .2)]}
    kept = [r['rank'] for r in ranks if r['source'] not in excluded]
    return dict(mean=statistics.mean(kept), raw_mean=statistics.mean(values), median=median,
                low=min(values), high=max(values), count=len(values), excluded=sorted(excluded))


def build(year, week, refresh=False):
    sources, manifest, rows, health = registry(), [], {}, []
    jobs = [(s['id'], year, week, pos) for s in sources for pos in POSITIONS]
    def task(job):
        try:
            return job, fetch_feed(*job, refresh=refresh), None
        except Exception as exc:
            return job, None, str(exc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for (expert, _, _, pos), result, error in pool.map(task, jobs):
            if error:
                health.append(dict(source=expert, position=pos, status='unavailable', reason=error))
                continue
            data, provenance = result
            manifest.append(provenance)
            health.append(dict(source=expert, position=pos, status='available',
                               published=data['published'], count=len(data['players'])))
            for p in data['players']:
                key = f"{pos}:{p['player_id']}"
                row = rows.setdefault(key, dict(id=key, name=p['player_name'], position=pos,
                    team=normalize_team(p.get('player_team_id', '')), matchup=p.get('matchup', ''), ranks=[]))
                row['ranks'].append(dict(source=expert, rank=int(p['rank']), published=data['published']))
    from .footballers import fetch as fetch_footballers, registry as footballers_registry
    try:
        extra_sources, extra_ranks, provenance = fetch_footballers(year, week, refresh)
        sources.extend(extra_sources)
        manifest.extend(provenance)
        names = {}
        for key, row in rows.items():
            names.setdefault((row['position'], name_key(row['name'])), []).append(key)
        for r in extra_ranks:
            matches = names.get((r['position'], name_key(r['name'])), [])
            key = matches[0] if len(matches) == 1 else f"{r['position']}:ballers-{r['player_id']}"
            row = rows.setdefault(key, dict(id=key, name=r['name'], position=r['position'],
                                           team=normalize_team(r['team']), matchup='', ranks=[]))
            row['ranks'].append({k:r[k] for k in ['source','rank','published']})
        for s in extra_sources:
            for pos in POSITIONS:
                contributions = [r for r in extra_ranks if r['source'] == s['id'] and r['position'] == pos]
                health.append(dict(source=s['id'], position=pos,
                    status='available' if contributions else 'unavailable', count=len(contributions),
                    reason='' if contributions else 'Free K/DST parser not verified'))
    except Exception as exc:
        for s in footballers_registry(year):
            sources.append(s)
            for pos in POSITIONS:
                health.append(dict(source=s['id'], position=pos, status='unavailable', reason=str(exc)))
    if not rows:
        raise RuntimeError('No current-week analyst data: refusing an empty/stale publication')
    bundle = dict(version='0.4.0', season=year, week=week, scoring='PPR',
        generated_at=datetime.now(timezone.utc).isoformat(), sources=sources, health=health,
        players=list(rows.values()), manifest=manifest,
        notes=['Named analysts are not independent platforms. Shared information can correlate their errors.',
               'Ranks are not projected points. K/DST scoring can differ by analyst; PPR does not standardize those rules.',
               'Historical accuracy remains retrospective, with explicit timestamp and archive limitations. No accuracy weighting.',
               'Boris Chen and aggregate ECR are excluded to avoid counting the same analysts twice.'])
    folder = ROOT / 'site/data'
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / 'consensus.json.tmp'
    temporary.write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')
    temporary.replace(folder / 'consensus.json')
    snapshot = ROOT / 'output/consensus-snapshots'
    snapshot.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode()
    tag = hashlib.sha256(raw).hexdigest()[:12]
    (snapshot / f'{year}-{week:02}-{tag}.json').write_bytes(raw)
    print(f'{year} week {week}: {len(rows)} players; {sum(h["status"] == "available" for h in health)}/{len(health)} source-position feeds')
    return bundle


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', type=int)
    parser.add_argument('--week', type=int)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    state = Sources().json('consensus-state.json', 'https://api.sleeper.app/v1/state/nfl', ttl=900)
    build(args.season or int(state['season']), args.week or int(state['week']), args.refresh)
