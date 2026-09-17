"""Public-data downloads with local cache and provenance; no credentials required."""
import csv
import hashlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'
BASE = 'https://github.com/nflverse/nflverse-data/releases/download'


class Sources:
    def __init__(self, refresh=False):
        self.refresh = refresh
        self.manifest = []

    def get(self, name, url, ttl=86400):
        CACHE.mkdir(exist_ok=True)
        path = CACHE / name
        if self.refresh or not path.exists() or time.time() - path.stat().st_mtime > ttl:
            response = requests.get(url, timeout=90)
            response.raise_for_status()
            temp = path.with_suffix(path.suffix + '.tmp')
            temp.write_bytes(response.content)
            temp.replace(path)
        raw = path.read_bytes()
        self.manifest.append(dict(name=name, url=url, bytes=len(raw),
                                  sha256=hashlib.sha256(raw).hexdigest(),
                                  fetched_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()))
        return raw.decode('utf-8-sig')

    def csv(self, tag, name, ttl=86400):
        return list(csv.DictReader(io.StringIO(self.get(name, f'{BASE}/{tag}/{name}', ttl))))

    def json(self, name, url, ttl=86400):
        return json.loads(self.get(name, url, ttl))


def number(row, key, default=0.0):
    try:
        value = float(row.get(key, default) or default)
        return value if abs(value) < 1e12 else default
    except (ValueError, TypeError):
        return default


def normalize_team(team):
    return {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC'}.get(team, team)
