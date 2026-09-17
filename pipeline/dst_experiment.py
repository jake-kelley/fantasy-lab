"""Small, chronological D/ST experiment. Selection uses 2024 weeks 9–12 only."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import ROOT
from .model import DEF, KEYS, USAGE, TEAM, Estimator, dataset, distribution, prepare, score


FEATURE_NAMES = ([f'avg:{k}' for k in KEYS+USAGE]
                 + [f'change:{k}' for k in KEYS+USAGE]
                 + [f'team:{k}' for k in TEAM] + [f'opp:{k}' for k in TEAM]
                 + ['history', 'season_history', 'gap', 'team_change', 'home',
                    'indoor', 'rest', 'week', 'matchup', 'matchup_count'])
COMPACT_FEATURES = ['avg:def_sacks', 'avg:def_interceptions', 'avg:fumble_recovery_opp',
                    'avg:points_allowed', 'opp:attempts', 'opp:carries',
                    'opp:passing_yards', 'opp:rushing_yards', 'opp:passing_tds',
                    'opp:rushing_tds', 'opp:passing_interceptions', 'opp:sacks_suffered',
                    'home', 'indoor', 'rest']
RARE = [k for k in DEF if k not in ['def_sacks', 'points_allowed']]


class CompactDST:
    def __init__(self, retention=0.5):
        if retention not in [0, 0.5, 1]:
            raise ValueError('Retention must be 0, 0.5, or 1')
        self.retention = retention
        self.features = [FEATURE_NAMES.index(k) for k in COMPACT_FEATURES]
        self.targets = [KEYS.index(k) for k in DEF]
        self.rare = [DEF.index(k) for k in RARE]

    def fit(self, rows):
        selected = [r for r in rows if r['pos'] == 'DST']
        x = np.array([r['x'][self.features] for r in selected])
        y = np.array([r['y'][self.targets] for r in selected])
        self.prior = y.mean(axis=0)
        self.model = make_pipeline(StandardScaler(), Ridge(alpha=100))
        self.model.fit(x, y)
        return self

    def predict(self, rows):
        out = np.zeros((len(rows), len(KEYS)))
        indices = [i for i, r in enumerate(rows) if r['pos'] == 'DST']
        if not indices:
            return out
        values = self.model.predict(np.array([rows[i]['x'][self.features] for i in indices]))
        values[:, self.rare] = (self.retention*values[:, self.rare]
                               + (1-self.retention)*self.prior[self.rare])
        out[np.ix_(indices, self.targets)] = np.maximum(values, 0)
        return out


def load():
    def read(name):
        with (ROOT/'.cache'/name).open(encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    games = read('games.csv')
    teams = sum([read(f'stats_team_week_{y}.csv') for y in [2024, 2025, 2026]], [])
    rows, team_index, _ = prepare([], teams, [], [], games)
    ds, state = dataset(rows, team_index)
    return ds, state, games


def errors(rows, preds):
    a = np.array([float(score(r['y'], 'DST')) for r in rows])
    p = np.array(preds)
    return dict(n=len(rows), mae=float(np.mean(abs(a-p))),
                rmse=float(np.sqrt(np.mean((a-p)**2))))


def forecast(model, train, test, calibration=None):
    model.fit(train)
    reference = train if calibration is None else calibration
    residuals = np.array([r['y'] for r in reference])-model.predict(reference)
    preds = [float(distribution(p, residuals, 'DST')[0][2]) for p in model.predict(test)]
    return preds, residuals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['select', 'evaluate'])
    args = parser.parse_args()
    ds, _, _ = load()
    path = ROOT/'research'/'dst-selection.json'
    if args.phase == 'select':
        results = {}
        for label, make in [('legacy', Estimator), ('compact_0', lambda: CompactDST(0)),
                            ('compact_0.5', lambda: CompactDST(0.5)),
                            ('compact_1', lambda: CompactDST(1))]:
            outcomes, all_preds = [], []
            for end in [8, 10]:
                train = [r for r in ds if r['season']==2024 and 5<=r['week']<=end]
                test = [r for r in ds if r['season']==2024 and end<r['week']<=end+2]
                preds, _ = forecast(make(), train, test)
                outcomes.extend(test); all_preds.extend(preds)
            results[label] = errors(outcomes, all_preds)
        results['baseline'] = errors(outcomes, [r['baseline_scores'][2] for r in outcomes])
        selected = min((k for k in results if k.startswith('compact')), key=lambda k: results[k]['mae'])
        result = dict(selection_period='2024 weeks 9-12; expanding fits end at weeks 8 and 10',
                      selection_metric='MAE; training residual scenarios used for PA bands in development only',
                      selected=selected, retention=float(selected.split('_')[1]),
                      features=COMPACT_FEATURES, results=results,
                      caveat='Design motivated by inspected 2025 results and 2026 forecast. No pristine holdout claim.')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(result, indent=2)+'\n')
    else:
        selected = json.loads(path.read_text())
        result = dict(selection=selected, models={})
        test = [r for r in ds if r['season']==2025]
        warm = [r for r in ds if r['season']==2024 and 5<=r['week']<=12]
        cal = [r for r in ds if r['season']==2024 and r['week']>=13]
        train = [r for r in ds if r['season']==2024 and r['week']>=5]
        for label, make in [('legacy', Estimator), ('compact', lambda: CompactDST(selected['retention']))]:
            model=make().fit(warm)
            residuals=np.array([r['y'] for r in cal])-model.predict(cal)
            cal_preds=[float(distribution(p,residuals,'DST')[0][2]) for p in model.predict(cal)]
            score_errors=np.array([float(score(r['y'],'DST'))-p for r,p in zip(cal,cal_preds)])
            model.fit(train)
            predictions=model.predict(test)
            points=[float(distribution(p,residuals,'DST')[0][2]) for p in predictions]
            metrics=errors(test,points)
            lo,hi=np.quantile(score_errors,[.1,.9])
            metrics['interval_coverage']=float(np.mean([p+lo<=score(r['y'],'DST')<=p+hi for r,p in zip(test,points)]))
            metrics['weekly']=[dict(week=w,**errors([r for r in test if r['week']==w],
                                                  [p for r,p in zip(test,points) if r['week']==w])) for w in range(1,19)]
            result['models'][label]=metrics
        result['models']['baseline']=errors(test,[r['baseline_scores'][2] for r in test])
        (ROOT/'research'/'dst-evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
