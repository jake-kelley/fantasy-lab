"""Pregame lines only. Historical closing lines are not Tuesday-known snapshots."""
import numpy as np
from .data import number


def market_features(game, home):
    if not game.get('total_line') or game.get('spread_line') in [None,'']:
        return np.array([np.nan,np.nan])
    total=number(game,'total_line');margin=number(game,'spread_line')*(1 if home else -1)
    return np.array([(total+margin)/2,(total-margin)/2])


def annotate_market(rows,games):
    lookup={g['game_id']:g for g in games}
    for r in rows:r['market_x']=market_features(lookup[r['game_id']],bool(r['home']))
