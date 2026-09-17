# Fieldwork

A free-data fantasy football research dashboard, hosted as static files on GitHub Pages.
Python runs in GitHub Actions, on a desktop, or in a Linux container. Pages does not execute Python.

**Experimental v0.1.** This is an independently implemented statistical baseline, not a clone
of Subvertadown, MonCalFF, or Boris Chen. The dashboard shows both the fitted model and a
rolling baseline, including where the model loses. No claim of superiority over experts.

## What works

- QB, RB, WR, TE, FLEX, K, D/ST, DL, LB, and DB boards for the next three regular-season weeks.
- Standard / half-PPR / PPR offense; explicit kicker, scoreboard-D/ST, and IDP presets.
- Player scoring-component details, prior workload, injury flags, empirical outcome ranges,
  matchup context, search, tiers, CSV export, and downloadable historical test predictions.
- Real 2024/2025 statistics and snap counts. Current rosters are joined through nflverse IDs;
  Sleeper supplies status and platform IDs. No personal account, roster, or credential is embedded.
- Chronological tests, source URLs, retrieval timestamps, and SHA-256 hashes.

## Run locally

Python 3.12+ is recommended. A virtual environment is optional but recommended.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m pipeline.run
python -m http.server 8080 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8080. Do not open index.html with a file:// URL; browsers restrict JSON fetches there.
For a persistent service with automatic six-hour refresh:

```sh
python -m pipeline.serve
```

Data downloads live in `.cache/`, generated files in `site/data/`, and the run manifest in `output/`.
`python -m pipeline.run --refresh` bypasses caches. Historical files normally cache for 30 days;
current stats, rosters, schedules, and NFL state for one hour; Sleeper's player dump for a day.
Requests have timeouts and fail rather than entering a retry loop. Failed builds do not replace
the main projection bundle. The UI flags a bundle older than two days.

## GitHub Pages / Actions

The repository workflow builds on a main-branch push, a manual dispatch, and these UTC schedules:

- 12:17 daily during September–January.
- 16:17 Sunday, Monday, and Thursday during September–January.

Schedules can be delayed by GitHub and are not a real-time service. Enable Pages with
**GitHub Actions** as the build source. The workflow needs `contents: read`, `pages: write`,
and `id-token: write`. It uses standard Linux runners; no GPU, secrets, paid feeds, database,
Vercel subscription, or external backend is needed. Availability/cost remain subject to GitHub's
plan and usage rules. Workflow timeout is 25 minutes. Audit artifacts (including current
projections and validation rows) are retained for 14 days, not indefinitely.

To retain a full season of forecast snapshots, download audit artifacts before they expire.
Historical input files can be revised upstream; hashes detect changes but are not copies of the inputs.
The website publishes only source metadata and derived outputs, not cached raw datasets.

## Docker / Linux

```sh
docker compose up --build -d
```

Open http://localhost:8080. The container serves static files and updates them every six hours.
Named volumes retain downloads and the last successful projection bundle across restarts.
On the first launch, the page may show a missing-bundle message until the initial build completes.
Use `docker compose logs -f` for progress. This container uses the same pipeline as Actions.
Use a reverse proxy if exposing the Python static server beyond a trusted network.

## Model specification

Each position has a separate multi-output Ridge regression (`alpha=100`) after feature
standardization. Coefficients estimate scoring components; fantasy points are calculated afterward.
All features precede the target week. All games within a week are predicted before any outcomes
from that week enter feature history.

Inputs include recency-weighted scoring components and workload, the latest observation minus
that average, team/opponent offensive and defensive statistics, prior positional matchup residuals,
home/away, indoor roof, rest, target week, experience in the observed history, team changes, and
time since participation. Rolling history uses at most 12 appearances and weights of 0.8 per
appearance; previous-season observations have an additional 0.35 factor. These fixed design
choices are **not** claimed to be optimal. No player names or IDs are fitted as features.

2024 weeks 1–4 initialize history. Weeks 5–12 fit an initial model and weeks 13–18 estimate
joint component residuals and signed scoring errors. A model fitted on weeks 5–18 is then
evaluated throughout 2025 with fixed coefficients, while inputs update from preceding weeks.
Live coefficients are refitted on 2024 weeks 5–18 plus all of 2025. New seasons update inputs
but do not change the training seasons. Earlier intermediate runs were used to correct scoring,
identity joins, and horizon bugs; 2025 has not been used to tune alpha, select features, or blend models.

The test is conditional on recorded participation: box-score rows plus ID-matched snap records
include zero-production participants, but not a full pregame eligible roster including DNPs.
This is **not** a prospective lineup-choice or injury forecast evaluation. Modern historical files
also contain statistical corrections that may not have been available at original prediction time.

For D/ST, points-allowed scoring bands are integrated over empirical residual scenarios, rather
than scoring only average predicted points allowed. Outcome intervals use 2024 calibration
scoring errors, allowing zero and negative scores. They are preliminary marginal intervals,
not guaranteed conditional coverage. The dashboard reports actual 2025 coverage.

Baseline points are recency-weighted **observed fantasy scores**. This distinction matters for
nonlinear D/ST scoring. MAE and RMSE are shown by position and week. Improvements have not
been assessed for statistical significance; lower average error alone does not prove an edge.

## Scoring and interpretation

Exact weights are in `pipeline/model.py::score` and the website's Method & sources view.
Offensive presets use 4-point passing TDs and -2 interceptions. D/ST points allowed is the
**opponent's scoreboard total**, with no exclusions for defensive scores. Therefore it is not
exact Sleeper, ESPN, or Yahoo D/ST scoring. IDP tackle categories and bonuses stack as documented.
Do not use these presets as a substitute for checking custom league settings.

The matchup map is a descriptive six-matchup mean of **group-level points above a prior rolling
baseline**, in PPR for offensive positions. It is not MonCalFF's percentage algorithm, a causal
effect, or an extra adjustment to apply on top of the already matchup-aware model.
Tiers are presentation buckets within two points of the tier leader, not fitted Gaussian clusters
or evidence that players are statistically equivalent.

Upcoming-week views hold current workload and availability assumptions fixed. They do not infer
future injury returns. Future calendar distance is not treated as additional missed games.
OUT/IR tags mean forecasts are conditional, not advice to start that player. Inactive teams/players,
roster inconsistencies, or delayed upstream updates can still require a manual check.

## Free-data limitations and next research steps

This release does not incorporate weather forecasts, betting lines, live routes, coverage shells,
projected personnel redistribution after injuries, opponent-adjusted EPA models, or a drive-level
kicker simulator. Some are available free but require additional timestamp-aware modeling and
validation; others lack dependable free live coverage. It does not implement custom Sleeper scoring
or roster sync. Those are additions, not capabilities claimed by this build.

Before making the model a primary decision source: improve offensive opportunity forecasts,
evaluate eligible-player start/sit decisions, archive prospective predictions, evaluate feature
ablations, and check calibration by workload rather than position alone. Retain the baseline
comparison throughout; do not tune repeatedly on 2025 and keep calling it an untouched holdout.

## Sources and research

- [nflverse](https://nflverse.nflverse.com/) and [data releases](https://github.com/nflverse/nflverse-data/releases):
  weekly player/team statistics, snaps, rosters, player identities, schedules.
- [Sleeper API](https://docs.sleeper.com/): public player status; no account credentials required.
- [Subvertadown methodology](https://subvertadown.com/article/what-s-in-the-model-).
- [MonCalFF methodology](https://www.dynastynerds.com/analytics/introduction-to-weekly-positional-matchups-posafpa/).
- [Boris Chen source](https://github.com/borisachen/fftiers).
- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

Data availability correction, inspected September 16, 2026: nflverse documentation described
an injury-feed outage, but live release assets include `injuries_2025.csv` (6,068 rows, 5,783 REG)
and `injuries_2026.csv` (193 rows, weeks 1–2 at inspection). This proves those files exist, not that
every historical report timestamp or current report is complete. They lack issue timestamps and
are not used as historical pregame features. Current statuses in this release use Sleeper.

Original code: MIT. Third-party inputs retain their respective upstream terms; the code license
does not relicense data. Source URLs and hashes are included in every generated bundle.
