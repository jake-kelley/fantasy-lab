"""Chronological, position-specific ridge models. All features precede target week."""
from collections import defaultdict
from datetime import date
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .data import number, normalize_team

OFF = ['passing_yards', 'passing_tds', 'passing_interceptions', 'rushing_yards',
       'rushing_tds', 'receptions', 'receiving_yards', 'receiving_tds',
       'fumbles_lost_total', 'passing_2pt_conversions', 'rushing_2pt_conversions',
       'receiving_2pt_conversions']
KICK = ['fg_made_0_19', 'fg_made_20_29', 'fg_made_30_39', 'fg_made_40_49',
        'fg_made_50_59', 'fg_made_60_', 'pat_made', 'fg_missed', 'pat_missed']
DEF = ['def_sacks', 'def_interceptions', 'fumble_recovery_opp', 'def_tds',
       'special_teams_tds', 'def_safeties', 'def_punt_blocks', 'def_fg_blocks',
       'def_pat_blocks', 'points_allowed']
IDP = ['def_tackles_solo', 'def_tackles_with_assist', 'def_tackle_assists',
       'def_tackles_for_loss', 'def_sacks', 'def_interceptions', 'def_pass_defended',
       'def_fumbles_forced', 'fumble_recovery_opp', 'def_tds', 'def_safeties']
KEYS = list(dict.fromkeys(OFF + KICK + DEF + IDP))
USAGE = ['attempts', 'carries', 'targets', 'receiving_air_yards', 'offense_pct',
         'defense_pct', 'fg_att', 'pat_att']
TEAM = ['attempts', 'carries', 'passing_yards', 'rushing_yards', 'passing_tds',
        'rushing_tds', 'passing_interceptions', 'sacks_suffered', 'def_sacks',
        'def_interceptions', 'fg_att', 'pat_att']
POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'DL', 'LB', 'DB']


def group(pos):
    if pos in ['DE', 'DT', 'NT', 'DL']: return 'DL'
    if pos in ['ILB', 'OLB', 'MLB', 'LB']: return 'LB'
    if pos in ['CB', 'S', 'SS', 'FS', 'SAF', 'DB']: return 'DB'
    if pos == 'FB': return 'RB'
    return pos


def targets(pos):
    return KICK if pos == 'K' else DEF if pos == 'DST' else IDP if pos in ['DL', 'LB', 'DB'] else OFF


def vector(row, keys=KEYS):
    return np.array([number(row, k) for k in keys], dtype=float)


def score(arr, pos, ppr=1):
    a = np.asarray(arr)
    d = {k: a[..., i] for i, k in enumerate(KEYS)}
    if pos == 'K':
        return (3*(d[KICK[0]]+d[KICK[1]]+d[KICK[2]]) + 4*d[KICK[3]]
                + 5*(d[KICK[4]]+d[KICK[5]]) + d['pat_made']-d['fg_missed']-d['pat_missed'])
    if pos == 'DST':
        pa = d['points_allowed']
        band = np.select([pa < .5, pa <= 6, pa <= 13, pa <= 20, pa <= 27, pa <= 34],
                         [10, 7, 4, 1, 0, -1], default=-4)
        return (d['def_sacks']+2*(d['def_interceptions']+d['fumble_recovery_opp']+
                d['def_safeties']+d['def_punt_blocks']+d['def_fg_blocks']+d['def_pat_blocks'])
                +6*(d['def_tds']+d['special_teams_tds'])+band)
    if pos in ['DL', 'LB', 'DB']:
        return (d['def_tackles_solo']+d['def_tackles_with_assist']+.5*d['def_tackle_assists']
                +d['def_tackles_for_loss']+3*d['def_sacks']+3*d['def_interceptions']
                +d['def_pass_defended']+2*d['def_fumbles_forced']+2*d['fumble_recovery_opp']
                +6*d['def_tds']+2*d['def_safeties'])
    return (.04*d['passing_yards']+4*d['passing_tds']-2*d['passing_interceptions']
            +.1*(d['rushing_yards']+d['receiving_yards'])+6*(d['rushing_tds']+d['receiving_tds'])
            +ppr*d['receptions']-2*d['fumbles_lost_total']
            +2*(d['passing_2pt_conversions']+d['rushing_2pt_conversions']+d['receiving_2pt_conversions']))


def prepare(player_rows, team_rows, snaps, player_ids, games):
    """Join on IDs. Include participating players with zero box-score production."""
    pfr = {r['pfr_id']: r for r in player_ids if r.get('pfr_id') and r.get('gsis_id')}
    schedules = {g['game_id']: g for g in games if g.get('game_type') == 'REG'}
    rows = {}
    for r in player_rows:
        if r.get('season_type') != 'REG' or r['game_id'] not in schedules: continue
        r = dict(r)
        r['pos'] = group(r['position'])
        if r['pos'] not in POSITIONS: continue
        rows[(r['game_id'], r['player_id'])] = r
    mapped, missing = 0, 0
    for snap in snaps:
        if snap.get('game_type') != 'REG' or snap['game_id'] not in schedules: continue
        pos = group(snap['position'])
        if pos not in POSITIONS: continue
        relevant = 'defense_snaps' if pos in ['DL', 'LB', 'DB'] else 'st_snaps' if pos == 'K' else 'offense_snaps'
        if number(snap, relevant) <= 0: continue
        identity = pfr.get(snap['pfr_player_id'])
        if not identity:
            missing += 1
            continue
        mapped += 1
        pid = identity['gsis_id']
        key = (snap['game_id'], pid)
        if key not in rows:
            rows[key] = dict(player_id=pid, player_display_name=snap['player'], pos=pos,
                             team=snap['team'], opponent_team=snap['opponent'],
                             season=snap['season'], week=snap['week'], game_id=snap['game_id'])
        rows[key].update({k: snap[k] for k in ['offense_pct', 'defense_pct']})
    team_index = {}
    for t in team_rows:
        if t.get('season_type') != 'REG' or t['game_id'] not in schedules: continue
        team = normalize_team(t['team'])
        team_index[(t['game_id'], team)] = t
        g = schedules[t['game_id']]
        is_home = normalize_team(g['home_team']) == team
        if not g.get('home_score') or not g.get('away_score'): continue
        dst = dict(t, player_id='DST:'+team, player_display_name=team+' Defense', pos='DST')
        # Explicit scoreboard-points-allowed preset, not an assertion of platform scoring parity.
        dst['points_allowed'] = g['away_score'] if is_home else g['home_score']
        rows[(t['game_id'], dst['player_id'])] = dst
    result = []
    for r in rows.values():
        g = schedules[r['game_id']]
        if not g.get('home_score') or not g.get('away_score'): continue
        r['season'], r['week'] = int(r['season']), int(r['week'])
        r['team'] = normalize_team(r['team'])
        r['opponent_team'] = normalize_team(r['opponent_team'])
        r['home'] = float(r['team'] == normalize_team(g['home_team']))
        r['roof_indoor'] = float(g.get('roof') in ['dome', 'closed'])
        r['rest'] = number(g, 'home_rest' if r['home'] else 'away_rest', 7)
        r['date'] = g['gameday']
        r['y'] = vector(r)
        result.append(r)
    return sorted(result, key=lambda r: (r['season'], r['week'], r['player_id'])), team_index, dict(snap_rows_mapped=mapped, snap_rows_unmapped=missing)


def weighted(history, keys, year):
    if not history: return np.zeros(len(keys))
    recent = history[-12:]
    weights = np.array([.8**(len(recent)-1-i) * (.35 if h['season'] < year else 1)
                        for i, h in enumerate(recent)])
    return np.average([vector(h, keys) for h in recent], axis=0, weights=weights)


def rolling_scores(history, year, pos):
    if not history: return np.zeros(3)
    recent = history[-12:]
    weights = [.8**(len(recent)-1-i)*(.35 if h['season'] < year else 1) for i,h in enumerate(recent)]
    outcomes = np.array([h['y'] for h in recent])
    return np.array([np.average(score(outcomes, pos, p), weights=weights) for p in [0,.5,1]])


class Features:
    def __init__(self):
        self.players = defaultdict(list)
        self.teams = defaultdict(list)
        self.matchups = defaultdict(list)

    def row(self, r):
        history = self.players[r['player_id']]
        year = r['season']
        avg = weighted(history, KEYS+USAGE, year)
        r['baseline_scores'] = rolling_scores(history, year, r['pos'])
        last = vector(history[-1], KEYS+USAGE) if history else np.zeros(len(KEYS+USAGE))
        team = weighted(self.teams[r['team']], TEAM, year)
        opp = weighted(self.teams[r['opponent_team']], TEAM, year)
        previous = history[-1] if history else {}
        gap = min(60, max(0, (date.fromisoformat(r.get('as_of_date', r['date']))-date.fromisoformat(previous.get('date', r['date']))).days))/7
        match = self.matchups[(r['opponent_team'], r['pos'])][-6:]
        matchup = float(np.mean(match)) if match else 0
        x = np.r_[avg, last-avg, team, opp, min(len(history), 20),
                  sum(h['season'] == year for h in history), gap,
                  float(bool(history) and previous.get('team') != r['team']),
                  r['home'], r['roof_indoor'], min(r['rest'], 21)/7, r['week']/18,
                  matchup, len(match)/6]
        return x, avg[:len(KEYS)], matchup

    def update_week(self, rows, team_index):
        # Calculate every matchup residual before admitting this week's outcomes.
        groups = defaultdict(list)
        for r in rows: groups[(r['team'], r['opponent_team'], r['pos'])].append(r)
        for (_, opponent, pos), rr in groups.items():
            baseline = sum(float(rolling_scores(self.players[r['player_id']], r['season'], pos)[2]) for r in rr)
            actual = sum(float(score(r['y'], pos)) for r in rr)
            # Points residual avoids division by nearly zero or negative DST/IDP baselines.
            if baseline > 0: self.matchups[(opponent, pos)].append(actual-baseline)
        added = set()
        for r in rows:
            self.players[r['player_id']].append(r)
            key = (r['game_id'], r['team'])
            if key not in added and key in team_index:
                self.teams[r['team']].append(dict(team_index[key], season=r['season']))
                added.add(key)


def dataset(rows, teams):
    state = Features()
    out = []
    by_week = defaultdict(list)
    for r in rows: by_week[(r['season'], r['week'])].append(r)
    for key in sorted(by_week):
        batch = by_week[key]
        for r in batch:
            x, baseline, matchup = state.row(r)
            out.append(dict(r, x=x, baseline=baseline, matchup=matchup))
        state.update_week(batch, teams)
    return out, state


class Estimator:
    def __init__(self, dst_retention=None):
        # None preserves v0.1 for reproducible comparisons and diagnostics.
        self.dst_retention = dst_retention
        self.dst_model = None

    def fit(self, rows):
        self.models = {}
        for pos in POSITIONS:
            if pos == 'DST' and self.dst_retention is not None:
                from .dst_experiment import CompactDST
                self.dst_model = CompactDST(self.dst_retention).fit(rows)
                continue
            selected = [r for r in rows if r['pos'] == pos]
            if len(selected) < 30: continue
            indices = [KEYS.index(k) for k in targets(pos)]
            model = make_pipeline(StandardScaler(), Ridge(alpha=100))
            model.fit(np.array([r['x'] for r in selected]), np.array([r['y'][indices] for r in selected]))
            self.models[pos] = model, indices
        return self

    def predict(self, rows):
        result = np.zeros((len(rows), len(KEYS)))
        for pos, (model, indices) in self.models.items():
            ix = [i for i, r in enumerate(rows) if r['pos'] == pos]
            if not ix: continue
            values = model.predict(np.array([rows[i]['x'] for i in ix]))
            result[np.ix_(ix, indices)] = np.maximum(values, 0)
        if self.dst_model is not None:
            dst = self.dst_model.predict(rows)
            ix = [i for i, r in enumerate(rows) if r['pos'] == 'DST']
            result[ix] = dst[ix]
        return result


def distribution(pred, residuals, pos, score_errors=None):
    # Resample observed JOINT residual vectors; preserves component dependencies.
    sims = np.maximum(0, pred + residuals)
    if pos == 'DST': sims[:, KEYS.index('points_allowed')] = np.rint(sims[:, KEYS.index('points_allowed')])
    scores = np.stack([score(sims, pos, p) for p in [0, .5, 1]], axis=1)
    # Mean point estimate: linear scoring on expected stats, PA band integrated over distribution.
    means = np.array([float(score(pred, pos, p)) for p in [0, .5, 1]])
    if pos == 'DST':
        pidx = KEYS.index('points_allowed')
        pa_only = np.zeros_like(sims)
        pa_only[:, pidx] = sims[:, pidx]
        pred_pa = np.zeros(len(KEYS)); pred_pa[pidx] = pred[pidx]
        means += np.mean(score(pa_only, pos))-float(score(pred_pa, pos))
    # Scoring residuals preserve zero/negative outcomes. Component clipping is inappropriate
    # for interval bounds (it otherwise systematically excludes zero-point games).
    quantiles = (means + np.quantile(score_errors, [.1, .5, .9], axis=0)
                 if score_errors is not None else np.quantile(scores, [.1, .5, .9], axis=0))
    return means, quantiles
