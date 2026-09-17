"""Lagged role-similarity weighting; retain all records without rewriting outcomes."""
from collections import defaultdict
import numpy as np
from .model import KEYS
from .data import number


def role_average(history, year, bandwidth):
    if not history:return np.zeros(len(KEYS))
    recent=history[-12:]
    latest=number(recent[-1],'offense_pct')
    weights=[.8**(len(recent)-1-i)*(.35 if r['season']<year else 1)*
             np.exp(-abs(number(r,'offense_pct')-latest)/bandwidth) for i,r in enumerate(recent)]
    return np.average([r['y'] for r in recent],weights=weights,axis=0)


def annotate_roles(ds):
    histories=defaultdict(list)
    weeks=defaultdict(list)
    for r in ds:
        if r['pos']=='QB':weeks[(r['season'],r['week'])].append(r)
    for key in sorted(weeks):
        for r in weeks[key]:
            for band in [.15,.35]:r[f'role_{band}']=role_average(histories[r['player_id']],r['season'],band)
        for r in weeks[key]:histories[r['player_id']].append(r)
    return histories
