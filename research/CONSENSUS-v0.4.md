# Fieldwork weekly consensus and historical audit

Built September 16–17, 2026. Free data only. Main interface is now PPR analyst
consensus; the previous independent model remains at `model.html`.

## Current sources

Seven individual analysts expose free rankings through FantasyPros' public partner
widget: Dalton Del Don, Kevin Hanson, Kev Wheeler, James Emrick-Wilson, Elisha
Twerski, Pat Fitzmaurice, and Frank Ammirante. Their 2025 overall competition ranks
are respectively 6, 7, 20, 24, 30, 31, and 35. These are **half-PPR competition
credentials**, not our own full-PPR audit. They are not all top-ten analysts.

Evidence: the public [2025 accuracy announcement](https://www.fantasypros.com/2026/01/2025-fantasy-football-rankings-most-accurate-experts/)
and individual expert metadata on the [PPR rankings page](https://www.fantasypros.com/nfl/rankings/ppr-rb.php).
Captured relevant metadata is in `consensus-source-evidence.json`.
[FantasyPros' scoring methodology](https://support.fantasypros.com/hc/en-us/articles/44470556043547-How-do-you-measure-the-in-season-accuracy-of-fantasy-football-experts)
differs from ours; our correlations are not FantasyPros accuracy scores.

The other three analysts are Andy Holloway, Jason Moore, and Mike Wright. Their
individual ranks are visible on the Footballers' free position pages, with a PPR
4-point passing-TD setting. The importer follows the site's public client scoring
and ordering operations, publishing **only the displayed ranks**, not underlying
numeric projections or premium FLEX content. All 540 imported ranks were checked
against the rendered public QB/RB/WR/TE boards with zero mismatches at verification.
Footballers' [accuracy page](https://www.thefantasyfootballers.com/accuracy/) provides
historical highlights, not a verified recent PPR comparison against this panel.

This is ten analysts across two publishing platforms, not ten independent models.
The seven widget analysts supplied 38 of 42 requested position feeds at first build;
Footballers supplies 12 offensive-position feeds. Missing K/DST lists remain missing.
Future weekly availability is monitored, not guaranteed by this initial verification.

Subvertadown's full lists were not added through a subscription bypass. MonCalFF's
matchup ratings are not interchangeable with player ranks. Boris Chen derives tiers
from expert consensus; adding that output would double-count underlying opinions.

## Aggregation

Average positional ranks with one vote per selected analyst. Main board requires
at least three votes and 60% of selected available sources for the position.
Missing ranks are never zero. Limited-coverage players can be shown separately.
No cross-position FLEX ranks are invented from positional ordering.

Optional outlier filtering requires seven actual votes. Exclude deviations greater
than `max(5, 3 * 1.4826 * MAD)` from the median, capped at `floor(n * .2)` removals.
No forced trimming. Both original and filtered means remain inspectable.
Filtering defaults **off** because it did not consistently improve historical results.
The thresholds were specified before running the historical comparison, not tuned
against its outcomes. Equal weighting remains the default.

## Historical findings

`python -m pipeline.audit_consensus` checked all 952 requested lists:
seven analysts × two seasons × 17 weeks × four positions. All returned dated,
correct-season/week/position/PPR metadata. The audit matched 32,859 eligible
analyst-player-week observations after cutoff checks; these are repeated analyst
evaluations, not 32,859 distinct NFL player games.

Historical [weekly rosters](https://nflreadr.nflverse.com/reference/load_rosters_weekly.html)
resolve identities by Yahoo ID first, then an unambiguous name and position.
The audit excludes 4,725 rankings for games already started under the inferred
timestamp interpretation. Eighteen player identities remained unresolved. It keeps
295 rostered observations without a player-stat row as zero, instead of silently
discarding nonparticipants. Actual points use nflverse `fantasy_points_ppr`.

Comparisons use identical players and weeks across all seven analysts, within fixed
depth caps QB24/RB50/WR60/TE24. Matched comparisons contain 17 eligible weeks for
each season/position except 2025 TE, with 16. This is conditional accuracy within
that common player pool, not an evaluation of every possible player or lineup.

Primary measures: mean weekly Spearman correlation, realized PPR points per top
pick (QB/TE top six, RB/WR top twelve), and points left behind compared with the
best hindsight picks from that same pool. Correlation is **not percentage correct**.
Point prediction MAE is inappropriate because these inputs are ranks, not point
forecasts. Tied selection boundaries receive fractional selection weight.

| Season | Position | Raw mean correlation | Filtered correlation |
|---|---|---:|---:|
| 2024 | QB | 0.2915 | 0.2967 |
| 2024 | RB | 0.5742 | 0.5758 |
| 2024 | WR | 0.3322 | 0.3310 |
| 2024 | TE | 0.2960 | 0.2935 |
| 2025 | QB | 0.2680 | 0.2712 |
| 2025 | RB | 0.5109 | 0.5094 |
| 2025 | WR | 0.3686 | 0.3651 |
| 2025 | TE | 0.2662 | 0.2653 |

Filtering improved correlation in three comparisons and worsened it in five.
This is not evidence that removing dissent always helps. The small differences
are descriptive; no statistical significance or future superiority is claimed.
Analysts were selected partly using already-known 2025 credentials, introducing
selection bias; this is not an untouched test of the source-selection process.

## Limits that matter

The widget's `published` timezone is undocumented. Six live analyst timestamps
exactly matched the public update epochs when interpreted as US Pacific, supporting
that inference. Historical evaluation uses Pacific publication times and Eastern
kickoffs from the nflverse schedule. The inference is exposed, not called fact.
The strict sensitivity check requires publication **before game day**. It leaves
zero sufficiently large all-seven matched weeks, so it cannot confirm the main
results. The report does not hide that absence.

Old feeds are mutable. Correct metadata and a pre-kickoff publication stamp cannot
prove no later edit occurred. Results are therefore **provisional retrospective
archive audits**, not certified pregame accuracy. Weekly updates may contain results
of earlier games even after those players are excluded; timestamp filtering cannot
reconstruct a Tuesday forecasting horizon from Sunday's last stored list.

Footballers' 2024 and 2025 RB URLs redirected to the 2026 Week 2 page. Evidence is
stored in `footballers-archive-probe.json`; those redirects are not usable archives.
Footballers, Subvertadown, MonCalFF, and Boris Chen have no verified historical
pregame data integrated here. K/DST historical scoring also remains unaudited:
PPR does not standardize sacks, points-allowed bands, or kicker penalties.

## Reproduction and preservation

- `research/consensus-history.json`: complete summaries, exclusions, and URL/hash provenance.
- `research/consensus-audit-records.json.gz`: frozen normalized eligible ranks, points,
  identities, and strict-date eligibility used in the calculations.
- `.cache/ranks-*.json`: locally retained raw public responses; reruns reuse them.
- `python -m pipeline.consensus`: current board; wrong-season/week feeds rejected.
- GitHub Actions archives each observed current board in repository history under
  `history/YYYY/week-WW.json`, plus a 90-day artifact. Git commits preserve successive
  observations. Future audits can use actual capture times, not only provider stamps.

GitHub Pages serves static files; Python fetches and computes in Actions. Desktop
and Docker service use the same importer. A failed update preserves the last deployed
board, visibly marked stale after 36 hours. Individual failed feeds are excluded
and reported. No silent substitution with prior-week ranks.
