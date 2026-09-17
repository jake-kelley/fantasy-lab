# Fieldwork

A free-data fantasy football research dashboard, hosted as static files on GitHub Pages.
Python runs in GitHub Actions, on a desktop, or in a Linux container. Pages does not execute Python.

**v0.4: weekly PPR analyst consensus.** The main board combines ten named analysts,
with source selection, individual ranks, coverage gates, optional outlier filtering,
and a retrospective 2024/2025 accuracy audit. No account or paid feed required.
The independent v0.3 projection model remains accessible under **Model lab**.
Fieldwork is not affiliated with FantasyPros or the contributing publishers.

The historical audit covers seven analysts, 952 archived positional lists, and actual
PPR scores. It checks publication times but cannot certify immutable pregame history.
Footballers' old ranking URLs redirect to current rankings, so their historical accuracy
is unverified here. Details, source evidence, limitations, and measured results:
[consensus research report](research/CONSENSUS-v0.4.md).

Outlier filtering is **off by default**: it improved rank correlation in only 3 of the
8 tested season/position comparisons. Both filtered and raw means remain available.

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
python -m pipeline.consensus
python -c "import shutil; shutil.copyfile('research/consensus-history.json', 'site/data/historical-accuracy.json')"
node tests/consensus.test.cjs
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

Analyst snapshots additionally receive a 90-day artifact and a committed weekly file
under `history/`. Git history preserves earlier captures; the archive job needs
`contents: write`. These observed captures support future pregame evaluation without
depending on mutable upstream historical pages. Model forecast artifacts still expire.
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

v0.3 evaluates separate candidates for all nine positions. Frozen choices live in
`research/position-selection-extended.json`; scheduled builds never tune against current outcomes.

- QB/RB: 25% original Ridge component estimates, 75% recency-weighted component averages.
- WR/LB: 50% model, 50% rolling component averages. DL: 75% model, 25% rolling averages.
- TE/K/DB: position-specific Ridge inputs and exposure-scaled event shrinkage. TE and K use
  new team context; DB's selected model does not. Coefficients/settings differ by position.
- D/ST: forecasts pass plays (official attempts + sacks, not charted dropbacks), plays,
  sack/interception/recovery rates and points allowed. Rates times opportunities become event counts.
  Touchdowns, blocked kicks and safeties use training-league priors.
- K and D/ST use current `total_line`/`spread_line` from free nflverse schedules. Historical files
  contain closing lines. No target-game scores, observed temperature or observed wind are inputs.
  Missing future lines trigger the corresponding statistical model without market inputs.

New context includes prior EPA per play, QB-hit rates, per-play production, play volume and
opponent-adjusted points scored/allowed. Context histories use up to 16 games, 0.9 recency decay,
0.35 previous-season weight and four pseudo-games at the available historical league average.
Player rolling histories retain the original 12 appearances, 0.8 decay and 0.35 season factor.
QB role-similarity weighting was tested and rejected by the development criterion.

Development compares chronological fits on 2024 weeks 9-12 and 2025 weeks 1-12. The published
accuracy report now covers **2025 weeks 13-18**, not the full season used by v0.2. Point coefficients
for that report are trained only on 2024 weeks 5-18; the hyperparameter choices use the earlier
2025 development weeks. Empirical error ranges still come from 2024 weeks 13-18, predicted by
an initial fit on weeks 5-12. Live coefficients refit on 2024 weeks 5-18 plus all 2025.
All football histories update only after every feature for a week is calculated.

This is retrospective development: earlier versions' 2025 results were inspected. It is not
pristine external validation, and market-model evaluation is not a Tuesday-time backtest because
historical closing quotes were not necessarily available on Tuesday. The model's superior error
in the reported period does not establish an expert-ranking edge or statistical significance.
Historical inputs may have upstream corrections. Evaluation conditions on recorded participation,
including zero-production snap records, not all eligible players including DNPs.

D/ST points-allowed bands are integrated over empirical component residual scenarios. Other
scoring is linear on expected components. The 80% ranges are marginal historical error intervals,
not guarantees or distributions conditioned on every player's workload. Measured coverage is shown.

The Matchup view also includes independent RB/WR/TE **PPR team totals**, trained on summed
position-group outcomes rather than speculative individual roster forecasts. A team-total model
blends Ridge with rolling production; weights were selected on the same development periods.
Its matchup bonus compares the actual opponent with training-average opponent features, holding
team, venue and rest fixed. That neutral-opponent baseline differs from Subvertadown's definition.
The separate team-total evaluation is displayed, including where it loses to the rolling baseline.

## Scoring and interpretation

Exact weights are in `pipeline/model.py::score` and the website's Method & sources view.
Offensive presets use 4-point passing TDs and -2 interceptions. D/ST points allowed is the
**opponent's scoreboard total**, with no exclusions for defensive scores. Therefore it is not
exact Sleeper, ESPN, or Yahoo D/ST scoring. IDP tackle categories and bonuses stack as documented.
Do not use these presets as a substitute for checking custom league settings.

The matchup map is a descriptive six-matchup mean of **group-level points above a prior rolling
baseline**, in PPR for offensive positions. It is not MonCalFF's percentage algorithm, a causal
effect, or an extra adjustment to apply on top of the model. The map remains descriptive context; modeled team-total bonuses appear separately.
Tiers are presentation buckets within two points of the tier leader, not fitted Gaussian clusters
or evidence that players are statistically equivalent.

Upcoming-week views hold current workload and availability assumptions fixed. They do not infer
future injury returns. Future calendar distance is not treated as additional missed games.
OUT/IR tags mean forecasts are conditional, not advice to start that player. Inactive teams/players,
roster inconsistencies, or delayed upstream updates can still require a manual check.

## Free-data limitations and next research steps

This release does not incorporate weather forecasts, live routes, coverage shells,
projected personnel redistribution after injuries, opponent-adjusted EPA models, or a drive-level
kicker simulator. Some are available free but require additional timestamp-aware modeling and
validation; others lack dependable free live coverage. It does not implement custom Sleeper scoring
or roster sync. Those are additions, not capabilities claimed by this build.

Before making the model a primary decision source: improve offensive opportunity forecasts,
evaluate eligible-player start/sit decisions, archive prospective predictions, evaluate feature
ablations, and check calibration by workload rather than position alone. Retain the baseline
comparison throughout; do not tune repeatedly on 2025 and keep calling it an untouched holdout.

See [v0.3 results and screenshot comparison](research/MODEL-REVISION-v0.3.md) for measured improvements and remaining disagreements.

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

## Historical D/ST v0.2 experiment (superseded by v0.3)

The generic 124-column D/ST model is replaced by a 15-input Ridge model (alpha=100).
It keeps own historical sacks, interceptions, opponent fumbles recovered and points allowed;
eight opponent offensive statistics; home, indoor venue and rest. It excludes kicking history,
duplicate own-team inputs, the latest-minus-average block and the explicit matchup residual.
At that release, other positions retained v0.1 behavior.

Three fixed retention settings (0, 0.5, 1) were tested for turnovers, touchdowns, blocks and safeties.
A retention of zero uses training-league means; one retains the fitted predictions. Settings were
selected by MAE on 2024 weeks 9–12, with expanding fits ending at weeks 8 and 10. Training residuals
were used for PA scenarios during development only. This small 112-team-game selection favored
zero retention by only 0.0019 MAE over half retention; the precise setting is provisional.
This is output shrinkage of counts, not a dropback/opportunity-rate model or empirical Bayes fit.

After freezing that selection, the existing 2024 weeks 13–18 calibration protocol was used for
the 2025 comparison (544 team-games): legacy MAE 4.505 / RMSE 5.824, compact MAE 4.146 / RMSE 5.352,
rolling baseline MAE 4.561 / RMSE 5.860. Empirical 80% interval coverage changed from 79.4% to 84.4%.
No claim of statistical significance or superiority over expert forecasts. Design was informed by
previously inspected results, so this is retrospective evidence, not untouched external validation.

Reproduce after the main pipeline downloads data:

```sh
python -m pipeline.dst_experiment select
python -m pipeline.dst_experiment evaluate
```

The recorded selection and comparison are in `research/dst-selection.json` and
`research/dst-evaluation.json`. Production reads the frozen selection; it does not reselect settings
on each update. No Subvertadown values enter training or selection. This revision does not add
weather, injury redistribution, opportunity modeling, or offseason-weighted matchup residuals.

## Reproduce v0.3 research

```sh
python -m pipeline.tune_positions extended-select
python -m pipeline.tune_positions extended-evaluate
python -m pipeline.tune_team_outlook
python -m pipeline.run
python -m pipeline.compare_snapshot
```

Run the main pipeline once to populate downloads before research commands. The tuning helper caches
its derived dataset in ignored `output/tuning-dataset.pkl`; remove that one file when changing source
data or factor-building code. Production does not read this cache. Expert screenshots are transcribed
in `research/subvertadown-week2-snapshot.json` for comparison ONLY, never imported by fitting/selection.
The comparison script reports point differences and rank correlation, not forecasting accuracy.
Combined-player screenshot entries are excluded; Andy/Andres Borregales is an explicit name alias.
TE/IDP expert-comparison data were not supplied. No claim of matching all expert results.

Field definitions: https://nflreadr.nflverse.com/articles/dictionary_team_stats.html and
https://github.com/nflverse/nflfastR/blob/master/NEWS.md (closing-line sign convention).
