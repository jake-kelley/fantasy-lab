"""Free publisher feeds, with scoring and edition checks before admitting votes."""
from collections import defaultdict
from datetime import datetime
import json
import math
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .data import Sources, normalize_team

RB_URL = 'https://www.rotoballer.com/nfl-fantasy-football-rankings-tiered-ppr/265860'
ESPN_BASE = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leaguedefaults/3'
FFT_URL = 'https://www.fftoday.com/rankings/playerwkproj.php'
POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']


def registry():
    return [dict(id=key, name=name, family=family, kind=kind, url=url,
                 accuracy_rank_2025=None, accuracy_url=None,
                 accuracy_note='Not included in the historical audit; comparable PPR accuracy unverified.')
            for key, name, family, kind, url in [
                ('rotoballer', 'RotoBaller weekly PPR', 'RotoBaller', 'Publisher rankings', RB_URL + '?spreadsheet=ppr&league=Overall'),
                ('espn', 'ESPN weekly projections', 'ESPN', 'Projection-derived ranks', 'https://fantasy.espn.com/football/players/projections'),
                ('fftoday', 'FFToday weekly projections', 'FFToday', 'Projection-derived ranks', FFT_URL + '?LeagueID=107644')]]


def validate_rows(rows):
    seen = set()
    for r in rows:
        key = (r['position'], str(r['player_id']))
        if key in seen or not r['name'] or r['position'] not in POSITIONS or not math.isfinite(r['rank']) or r['rank'] < 1:
            raise ValueError('Duplicate identity or invalid publisher rank')
        seen.add(key)
    if not rows:
        raise ValueError('No verified ranks for requested edition')
    return rows


def order_projections(rows):
    """Equal projections receive midranks, not an arbitrary alphabetical advantage."""
    groups = defaultdict(list)
    for r in rows:
        if not math.isfinite(r['points']):
            raise ValueError('Nonfinite projection')
        groups[r['position']].append(r)
    result = []
    for players in groups.values():
        players.sort(key=lambda r: (-r['points'], str(r['player_id'])))
        start = 0
        while start < len(players):
            end = start + 1
            while end < len(players) and players[end]['points'] == players[start]['points']:
                end += 1
            for r in players[start:end]:
                r['rank'] = (start + 1 + end) / 2
                result.append(r)
            start = end
    return validate_rows(result)


def parse_rotoballer(page, payload, year, week):
    match = re.search(r'var rbRankings\s*=\s*({[^;]+});', page)
    if not match:
        raise ValueError('RotoBaller edition metadata missing')
    config = json.loads(match[1])
    if str(config.get('currentWeek')) != str(week) or str(config.get('season')) != str(year):
        raise ValueError('RotoBaller has a different season/week')
    data = payload.get('data', [])
    if not data or len(data) != int(payload['total']) or payload.get('next_page_url'):
        raise ValueError('Incomplete RotoBaller ranking response')
    result, counts, overall = [], defaultdict(int), set()
    for p in sorted(data, key=lambda p: int(p['rank'])):
        rank = int(p['rank'])
        if rank < 1 or rank in overall:
            raise ValueError('Invalid or duplicate RotoBaller overall rank')
        overall.add(rank)
        pos = {'DEF': 'DST', 'D/ST': 'DST', 'PK': 'K'}.get(p['position'], p['position'])
        if pos not in POSITIONS:
            continue
        if datetime.fromisoformat(p['updated_at']).year != year:
            raise ValueError('Old RotoBaller ranks')
        counts[pos] += 1
        result.append(dict(source='rotoballer', position=pos, player_id=p['player_id'],
                           name=p['player']['name'], team=normalize_team(p.get('team', '')),
                           rank=counts[pos], published=p['updated_at']))
    return validate_rows(result)


def fetch_rotoballer(year, week, refresh=False):
    source = Sources(refresh)
    page = source.get(f'rotoballer-{year}-{week}.html', RB_URL, ttl=1800)
    # Exactly the free PPR tab's request; premium categories are never requested.
    payload = source.json(f'rotoballer-ppr-{year}-{week}.json',
        'https://www.rotoballer.com/wp-json/rb/v1/rankings?league=Overall&perPage=600&spreadsheet=ppr', ttl=1800)
    return parse_rotoballer(page, payload, year, week), source.manifest


def parse_espn(payload, settings, teams, year, week, retrieved):
    if settings.get('seasonId') != year:
        raise ValueError('ESPN settings season mismatch')
    scoring = settings['settings']['scoringSettings']
    weights = {str(s['statId']): s for s in scoring['scoringItems']}
    if scoring['playerRankType'] != 'PPR' or weights.get('53', {}).get('points') != 1 or weights.get('4', {}).get('points') != 4:
        raise ValueError('ESPN scoring is not full PPR / four-point passing TD')
    players = payload.get('players', [])
    # Request exceeds total eligible pool; reject a truncated result, not a partial top list.
    if not players or len(players) >= 2000:
        raise ValueError('Empty or potentially truncated ESPN player pool')
    positions = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}
    rows = []
    for entry in players:
        p = entry['player']
        pos = positions.get(p['defaultPositionId'])
        if not pos:
            continue
        projected = [s for s in p.get('stats', []) if s.get('seasonId') == year
                     and s.get('scoringPeriodId') == week and s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 1]
        if len(projected) > 1:
            raise ValueError('Duplicate ESPN weekly projection')
        if not projected:
            continue
        stat = projected[0]
        points = float(stat['appliedTotal'])
        # Cross-check returned totals against publisher's public scoring configuration.
        calculated = sum(float(stat['stats'].get(k, 0)) * float(v.get('pointsOverrides', {}).get(str(p['defaultPositionId']), v['points']))
                         for k, v in weights.items())
        if not math.isfinite(points) or abs(calculated - points) > .02:
            raise ValueError('ESPN applied points disagree with verified PPR scoring')
        if points <= 0:
            continue
        rows.append(dict(source='espn', position=pos, player_id=p['id'], name=p['fullName'],
                         team=teams.get(str(p['proTeamId']), ''), points=points,
                         published=f'Retrieved {retrieved}; publisher update time unavailable'))
    if set(r['position'] for r in rows) != set(POSITIONS):
        raise ValueError('Missing ESPN weekly projection positions')
    return order_projections(rows)


def fetch_espn(year, week, refresh=False):
    source = Sources(refresh)
    base = ESPN_BASE.format(year=year)
    settings = source.json(f'espn-settings-{year}.json', base + '?view=mSettings', ttl=1800)
    filters = {'players': {'limit': 2000, 'sortPercOwned': {'sortAsc': False, 'sortPriority': 1}}}
    url = base + '?' + urlencode(dict(view='kona_player_info', scoringPeriodId=week, filter=json.dumps(filters)))
    payload = source.json(f'espn-ppr-{year}-{week}.json', url, ttl=1800)
    retrieved = source.manifest[-1]['fetched_at']
    team_data = source.json('espn-teams.json', 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=100', ttl=86400)
    teams = {t['team']['id']: normalize_team(t['team']['abbreviation']) for t in team_data['sports'][0]['leagues'][0]['teams']}
    return parse_espn(payload, settings, teams, year, week, retrieved), source.manifest


def parse_fftoday(html, year, week, pos, retrieved):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if not re.search(rf'\b{year} Week {week}\b', title):
        raise ValueError('FFToday has a different season/week')
    if 'FFToday PPR Scoring:' not in soup.get_text(' ', strip=True):
        raise ValueError('FFToday full-PPR scoring not confirmed')
    rows = []
    for a in soup.select('a[href*="/stats/players/"]'):
        cells = a.find_parent('tr').find_all('td', recursive=False)
        if len(cells) < 6:
            raise ValueError('FFToday player row layout changed')
        values = [c.get_text(' ', strip=True) for c in cells]
        player_id = re.search(r'/stats/players/(\d+)/', a['href'])[1]
        rows.append(dict(source='fftoday', position=pos, player_id=player_id,
                         name=a.get_text(' ', strip=True), team=normalize_team(values[2]),
                         points=float(values[-1]), published=f'Retrieved {retrieved}; publisher update time unavailable'))
    if not rows:
        raise ValueError('FFToday player table missing')
    return rows


def fetch_fftoday(year, week, refresh=False):
    source, rows = Sources(refresh), []
    for pos, ident in [('QB',10), ('RB',20), ('WR',30), ('TE',40), ('K',80)]:
        # Follow pagination so tied scores at page boundaries receive correct midranks.
        for page in range(10):
            url = FFT_URL + '?' + urlencode(dict(Season=year, GameWeek=week, PosID=ident,
                LeagueID=107644, order_by='FFPts', sort_order='DESC', cur_page=page))
            html = source.get(f'fftoday-ppr-{year}-{week}-{pos}-{page}.html', url, ttl=1800)
            rows.extend(parse_fftoday(html, year, week, pos, source.manifest[-1]['fetched_at']))
            if 'Next Page' not in BeautifulSoup(html, 'html.parser').get_text():
                break
        else:
            raise ValueError('FFToday pagination exceeded safety bound')
    return order_projections(rows), source.manifest


FETCHERS = {'rotoballer': fetch_rotoballer, 'espn': fetch_espn, 'fftoday': fetch_fftoday}


def comparisons():
    return [dict(name='Boris Chen', url='https://www.borischen.co/',
                 reason='Tiers derived from FantasyPros rankings. Reference only: adding a vote would reuse underlying analyst opinions.'),
            dict(name='theScore / Eric Patterson', url='https://www.thescore.com/author/eric-patterson',
                 reason='Current weekly rankings are labeled half-PPR. Excluded from this full-PPR consensus.'),
            dict(name='Rotoworld / Patrick Daugherty', url='https://www.nbcsports.com/fantasy/football',
                 reason='Free weekly ranks found, but their full-PPR scoring basis is not verified. No vote until scoring is confirmed.')]
