"""Reproduce the individual ranks shown on the free public PPR position pages.

Only ranks are exported. Numeric projections and premium FLEX content are not
published. Scoring follows the publisher's public UdkRankings.calcScore client.
"""
from collections import defaultdict
import json
import re

from .data import Sources, number


def parse_page(html, year, week):
    decoder = json.JSONDecoder()
    data = None
    for match in re.finditer(r'window\.udk\.data\s*=\s*', html):
        try:
            candidate = decoder.raw_decode(html[match.end():])[0]
        except ValueError:
            continue
        if isinstance(candidate, dict) and candidate.get('projections'):
            data = candidate
            break
    if not data:
        raise ValueError('Public ranking payload missing')
    rows = data['projections']
    if any(int(r['season']) != year or int(r['week']) != week for r in rows):
        raise ValueError('Footballers payload has a different season/week')
    if len({(r['player_id'], r['analyst_id']) for r in rows}) != len(rows):
        raise ValueError('Duplicate Footballers player/analyst records')
    return rows


def ppr_order_value(r):
    n = lambda key: number(r, key)
    if r['fantasy_position'] == 'QB':
        return (n('passing_yards')/25 + 4*n('passing_touchdowns') - 2*n('interceptions_thrown')
                - 2*n('fumbles_lost') + n('rushing_yards')/10 + 6*n('rushing_touchdowns'))
    return (n('receptions') - 2*n('fumbles_lost') + n('rushing_yards')/10
            + 6*n('rushing_touchdowns') + n('receiving_yards')/10 + 6*n('receiving_touchdowns'))


def registry(year):
    url = f'https://www.thefantasyfootballers.com/{year}-running-back-rankings/'
    return [dict(id=f'ballers-{i}', name=name, family='The Fantasy Footballers', url=url,
                    accuracy_rank_2025=None, accuracy_url='https://www.thefantasyfootballers.com/accuracy/',
                    accuracy_note='Historical accuracy highlights available; recent comparable PPR accuracy unverified.')
               for i, name in [('1','Andy Holloway'),('2','Jason Moore'),('3','Mike Wright')]]


def fetch(year, week, refresh=False):
    source = Sources(refresh)
    rows = []
    for pos, slug in [('QB','quarterback'),('RB','running-back'),('WR','wide-receiver'),('TE','tight-end')]:
        page = source.get(f'footballers-{year}-{week}-{pos}.html',
                          f'https://www.thefantasyfootballers.com/{year}-{slug}-rankings/', ttl=1800)
        rows.extend(r for r in parse_page(page, year, week) if r['fantasy_position'] == pos)
    sources = registry(year)
    groups = defaultdict(list)
    for r in rows:
        if r['analyst_id'] in {'1','2','3'} and r['fantasy_position'] in {'QB','RB','WR','TE'}:
            groups[r['analyst_id'], r['fantasy_position']].append(r)
    result = []
    totals = defaultdict(list)
    for players in groups.values():
        for r in players:
            totals[r['player_id']].append(ppr_order_value(r))
    # Restrict to useful depth, comfortably inside the free position boards.
    limits = {'QB': 30, 'RB': 60, 'WR': 60, 'TE': 30}
    for (analyst, pos), players in groups.items():
        players.sort(key=lambda r: (ppr_order_value(r), sum(totals[r['player_id']])/len(totals[r['player_id']])), reverse=True)
        for rank, r in enumerate(players[:limits[pos]], 1):
            result.append(dict(source=f'ballers-{analyst}', rank=rank, name=r['name'],
                               position=pos, team=r['team'], player_id=r['player_id'],
                               published=r['updated_at']))
    if len(groups) != 12:
        raise ValueError('Incomplete public Footballers analyst/position payload')
    return sources, result, source.manifest
