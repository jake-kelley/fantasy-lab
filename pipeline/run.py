"""Build an auditable static bundle: python -m pipeline.run [--refresh]."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone, date
import json
from pathlib import Path
import numpy as np

from .data import Sources, ROOT, normalize_team, number
from .model import (POSITIONS, KEYS, TEAM, USAGE, Estimator, dataset, distribution,
                    group, prepare, score, targets, weighted)


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temp.replace(path)


def metrics(actual, predicted, baseline):
    a, p, b = map(np.asarray, (actual, predicted, baseline))
    return dict(n=len(a), mae=round(float(np.mean(abs(a-p))), 3),
                rmse=round(float(np.sqrt(np.mean((a-p)**2))), 3),
                baseline_mae=round(float(np.mean(abs(a-b))), 3),
                baseline_rmse=round(float(np.sqrt(np.mean((a-b)**2))), 3))


def run(refresh=False):
    started = datetime.now(timezone.utc)
    sources = Sources(refresh)
    state = sources.json('sleeper-state.json', 'https://api.sleeper.app/v1/state/nfl', ttl=3600)
    season = int(state['season'])
    if season < 2026: raise ValueError('Live season precedes the 2024/2025 development period')
    players, teams, snaps = [], [], []
    for year in range(2024, season+1):
        ttl = 86400*30 if year < season else 3600
        players.extend(sources.csv('stats_player', f'stats_player_week_{year}.csv', ttl))
        teams.extend(sources.csv('stats_team', f'stats_team_week_{year}.csv', ttl))
        snaps.extend(sources.csv('snap_counts', f'snap_counts_{year}.csv', ttl))
    ids = sources.csv('players', 'players.csv')
    games = sources.csv('schedules', 'games.csv', ttl=3600)
    # Final score is required for an observation. Dates in the future are never admitted.
    today = date.today().isoformat()
    known_games = [g for g in games if g['gameday'] <= today]
    rows, team_index, join_audit = prepare(players, teams, snaps, ids, known_games)
    ds, feature_state = dataset(rows, team_index)
    print(f'Prepared {len(ds):,} player/team games; {join_audit}', flush=True)

    # D/ST settings frozen by the recorded 2024-only development experiment.
    dst_selection = json.loads((ROOT/'research'/'dst-selection.json').read_text())
    def estimator(): return Estimator(dst_retention=dst_selection['retention'])
    warm_train = [r for r in ds if r['season'] == 2024 and 5 <= r['week'] <= 12]
    calibration = [r for r in ds if r['season'] == 2024 and r['week'] >= 13]
    warm_model = estimator().fit(warm_train)
    warm_pred = warm_model.predict(calibration)
    residuals, score_errors = {}, {}
    for pos in POSITIONS:
        ix = [i for i, r in enumerate(calibration) if r['pos'] == pos]
        residuals[pos] = np.array([calibration[i]['y']-warm_pred[i] for i in ix])
        if not len(ix): raise ValueError('No calibration observations for '+pos)
        score_errors[pos] = np.array([[float(score(calibration[i]['y'], pos, p))-
                                      float(distribution(warm_pred[i], residuals[pos], pos)[0][j])
                                      for j, p in enumerate([0,.5,1])] for i in ix])

    train = [r for r in ds if r['season'] == 2024 and r['week'] >= 5]
    test = [r for r in ds if r['season'] == 2025]
    model = estimator().fit(train)
    test_pred = model.predict(test)
    report, predictions = {}, []
    for pos in POSITIONS:
        ix = [i for i, r in enumerate(test) if r['pos'] == pos]
        actual, forecast, baseline, cover = [], [], [], []
        weekly = defaultdict(lambda: [[], [], []])
        for i in ix:
            r, pred = test[i], test_pred[i]
            mean, quant = distribution(pred, residuals[pos], pos, score_errors[pos])
            a, p, b = float(score(r['y'], pos)), float(mean[2]), float(r['baseline_scores'][2])
            actual.append(a); forecast.append(p); baseline.append(b)
            cover.append(float(quant[0, 2] <= a <= quant[2, 2]))
            for bucket, val in zip(weekly[r['week']], [a, p, b]): bucket.append(val)
            predictions.append(dict(id=r['player_id'], name=r['player_display_name'], pos=pos,
                                    week=r['week'], team=r['team'], actual=round(a, 3),
                                    forecast=round(p, 3), baseline=round(b, 3)))
        result = metrics(actual, forecast, baseline)
        result['interval_coverage'] = round(float(np.mean(cover)), 3)
        result['weekly'] = [dict(week=w, **metrics(*vals)) for w, vals in sorted(weekly.items())]
        result['beats_baseline_mae'] = result['mae'] < result['baseline_mae']
        report[pos] = result
        print(pos, result['n'], 'MAE', result['mae'], 'baseline', result['baseline_mae'], flush=True)

    # Refit point models on both requested seasons. Current-season stats only update features.
    production = estimator().fit([r for r in ds if r['season'] in [2024, 2025] and
                                 (r['season'] > 2024 or r['week'] >= 5)])
    nfl_players = sources.json('sleeper-players.json', 'https://api.sleeper.app/v1/players/nfl')
    current_games = [g for g in games if int(g['season']) == season and g['game_type'] == 'REG']
    unfinished = [int(g['week']) for g in current_games if not g.get('home_score') or not g.get('away_score')]
    if not unfinished: raise ValueError('No unplayed regular-season games; refusing to publish stale projections')
    week = min(unfinished)
    weeks = list(range(week, min(18, week+2)+1))
    game_map = {}
    for g in current_games:
        for key in ['home_team', 'away_team']: game_map[(int(g['week']), normalize_team(g[key]))] = g
    latest = {pid: history[-1] for pid, history in feature_state.players.items()}
    current = {}
    rosters = sources.csv('rosters', f'roster_{season}.csv', ttl=3600)
    for roster in rosters:
        pid = roster.get('gsis_id')
        sid = roster.get('sleeper_id')
        p = nfl_players.get(sid, {})
        team = normalize_team(roster.get('team'))
        pos = group(roster.get('position'))
        if pos not in POSITIONS or not team or not pid: continue
        # Rostered currently; all depth roles visible but low-workload options marked.
        if roster.get('status') not in ['ACT', 'RES', 'RSR', 'INA', 'PUP', 'DEV']: continue
        previous = latest.get(pid, {})
        current[pid] = dict(id=pid, sleeper_id=sid, name=roster.get('full_name') or pid,
                            pos=pos, team=team, status=p.get('injury_status') or p.get('status') or 'Unknown',
                            depth=p.get('depth_chart_order'), history_games=len(feature_state.players[pid]),
                            last_played=previous.get('date'), forecasts=[])
    for team in {normalize_team(g['home_team']) for g in current_games}:
        pid = 'DST:'+team
        current[pid] = dict(id=pid, sleeper_id=team, name=team+' Defense', pos='DST', team=team,
                            status='Active', depth=1, history_games=len(feature_state.players[pid]),
                            last_played=latest.get(pid, {}).get('date'), forecasts=[])

    future_rows, references = [], []
    for p in current.values():
        for w in weeks:
            g = game_map.get((w, p['team']))
            if not g:
                p['forecasts'].append(dict(week=w, bye=True)); continue
            if g.get('home_score') and g.get('away_score'):
                p['forecasts'].append(dict(week=w, played=True)); continue
            home = normalize_team(g['home_team']) == p['team']
            opp = normalize_team(g['away_team'] if home else g['home_team'])
            r = dict(player_id=p['id'], pos=p['pos'], team=p['team'], opponent_team=opp,
                     season=season, week=w, date=g['gameday'], home=float(home),
                     roof_indoor=float(g.get('roof') in ['dome', 'closed']),
                     rest=number(g, 'home_rest' if home else 'away_rest', 7))
            # Do not mistake future calendar distance for intervening missed games.
            first_game = game_map.get((week, p['team']))
            r['as_of_date'] = first_game['gameday'] if first_game else today
            r['x'], r['baseline'], r['matchup'] = feature_state.row(r)
            future_rows.append(r); references.append(p)
    future_pred = production.predict(future_rows)
    for r, pred, p in zip(future_rows, future_pred, references):
        mean, quant = distribution(pred, residuals[p['pos']], p['pos'], score_errors[p['pos']])
        history = feature_state.players[p['id']]
        usage = weighted(history, USAGE, season)
        recent = history[-1] if history else {}
        # Report workload, not undocumented claims of causal feature attribution.
        detail = {k: round(float(pred[KEYS.index(k)]), 2) for k in targets(p['pos'])}
        low_history = p['history_games'] < 3
        unavailable = p['status'] in ['Out', 'IR', 'Injured Reserve', 'PUP', 'Sus']
        p['forecasts'].append(dict(week=r['week'], opponent=r['opponent_team'], home=bool(r['home']),
                                  date=r['date'], mean=[round(float(v), 2) for v in mean],
                                  p10=[round(float(v), 2) for v in quant[0]],
                                  p90=[round(float(v), 2) for v in quant[2]],
                                  baseline=[round(float(v), 2) for v in r['baseline_scores']],
                                  stats=detail, matchup_residual=round(r['matchup'], 2),
                                  low_history=low_history, unavailable=unavailable,
                                  usage={k: round(float(v), 2) for k, v in zip(USAGE, usage)},
                                  latest_snap_pct=number(recent, 'defense_pct' if p['pos'] in ['DL','LB','DB'] else 'offense_pct')))
    for p in current.values(): p['forecasts'].sort(key=lambda f: f['week'])

    payload = dict(version='0.2.0', generated_at=started.isoformat(), season=season, weeks=weeks,
                   observations_through=max(r['date'] for r in rows), model='Position-specific ridge component model',
                   train_seasons=[2024,2025], validation_season=2025, players=list(current.values()),
                   validation=report, sources=sources.manifest, joins=join_audit,
                   dst_revision=dst_selection,
                   limitations=[
                       'Research model, not proven to beat expert projections. See historical results by position.',
                       'D/ST v0.2 uses 15 inputs and training-league averages for turnovers, TDs, blocks and safeties. It omits the explicit matchup residual.',
                       'D/ST revision was motivated by inspected results; 2024 selected its settings, and 2025 is a retrospective comparison, not a pristine holdout.',
                       'Historical evaluation conditions on recorded participation; it does not test injury/DNP prediction.',
                       'Projections are conditional on playing. Current injury flags persist into future weeks; return dates are not modeled.',
                       '80% ranges are empirical residual estimates; use measured coverage, not an assumed guarantee.',
                       'D/ST preset uses scoreboard points allowed. It is not exact Sleeper/ESPN/Yahoo scoring.',
                       'No live routes, coverage charting, betting lines or weather inputs. No paid data.',
                       'Two seasons limit rare-event and rookie estimates. Future weeks hold current workload assumptions fixed.',
                       'Matchup chart shows past points above a rolling baseline, not a causal percentage boost.',
                   ])
    output = ROOT/'site'/'data'
    dump(output/'projections.json', payload)
    dump(output/'validation-2025.json', predictions)
    dump(ROOT/'output'/'run-manifest.json', dict(generated_at=started.isoformat(), sources=sources.manifest,
                                              runtime_seconds=(datetime.now(timezone.utc)-started).total_seconds()))
    print(f'Published bundle: {len(current):,} entities; {season} weeks {weeks}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    run(args.refresh)
