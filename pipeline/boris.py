"""Boris Chen's public exports: one derived-consensus vote, with original tiers."""
import csv
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import io
import re

import requests

from .data import Sources
from .publishers import validate_rows

BASE = 'https://s3-us-west-1.amazonaws.com/fftiers/out/'
CONFIG = 'https://raw.githubusercontent.com/borisachen/fftiers/master/src/config.R'


def parse(text, modified, config, year, week, pos):
    season = re.search(r'^year\s*<-\s*(\d+)', config, re.M)
    first = re.search(r'^weekonetuesday\s*<-\s*"(\d{4}-\d{2}-\d{2})"', config, re.M)
    if not season or int(season[1]) != year or not first or not 1 <= week <= 18:
        raise ValueError('Boris season configuration does not match requested edition')
    start = date.fromisoformat(first[1]) + timedelta(weeks=week-1)
    stamp = parsedate_to_datetime(modified).astimezone(timezone.utc)
    if not start <= stamp.date() < start + timedelta(days=7):
        raise ValueError('Boris export upload is outside requested week')
    rows = []
    for p in csv.DictReader(io.StringIO(text)):
        rank, tier = int(p['Rank']), int(p['Tier'])
        if tier < 1:
            raise ValueError('Invalid Boris tier')
        rows.append(dict(source='boris', player_id=p['Player.Name'], name=p['Player.Name'],
            position=pos, team='', rank=rank, tier=tier,
            published=f'Export uploaded {stamp.isoformat()}; edition inferred from upload date'))
    validate_rows(rows)
    if [r['rank'] for r in rows] != list(range(1, len(rows)+1)):
        raise ValueError('Boris ranks are not contiguous')
    return rows


def fetch(year, week, refresh=False):
    source = Sources(refresh)
    config = source.get('boris-config.R', CONFIG, ttl=1800)
    rows = []
    for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
        suffix = pos + ('-PPR' if pos in {'RB', 'WR', 'TE'} else '')
        url = BASE + f'weekly-{suffix}.csv'
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        modified = response.headers.get('Last-Modified')
        if not modified:
            raise ValueError('Boris export has no verifiable upload timestamp')
        rows.extend(parse(response.content.decode('utf-8-sig'), modified, config, year, week, pos))
        source.manifest.append(dict(name=f'boris-{year}-{week}-{suffix}.csv', url=url,
            bytes=len(response.content), sha256=hashlib.sha256(response.content).hexdigest(),
            fetched_at=datetime.now(timezone.utc).isoformat(), last_modified=modified,
            edition_basis='Upload date within publisher-configured Tuesday-to-Tuesday week; CSV has no edition field'))
    return rows, source.manifest
