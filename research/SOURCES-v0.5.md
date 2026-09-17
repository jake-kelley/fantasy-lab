# Expanded free weekly sources — 2026-09-17

Fieldwork adds three contributing publishers to its ten existing individual analysts.
These are 13 sources across five delivery platforms, not 13 independent statistical models.
The existing seven-analyst retrospective audit is unchanged; new sources have no comparable
historical accuracy claim or accuracy weight. Current successful fetching is not evidence
of guaranteed future availability.

## Verified additions

| Source | What casts one vote | Week 2 verified coverage QB/RB/WR/TE/K/DST |
|---|---|---|
| [RotoBaller](https://www.rotoballer.com/nfl-fantasy-football-rankings-tiered-ppr/265860?spreadsheet=ppr&league=Overall) | Free full-PPR publisher ranks, converted from overall ordering to positional order | 34 / 87 / 118 / 54 / 32 / 32 |
| [ESPN](https://fantasy.espn.com/football/players/projections) | Weekly projected points under ESPN's full-PPR settings, ordered within position | 32 / 96 / 152 / 91 / 32 / 32 |
| [FFToday](https://www.fftoday.com/rankings/playerwkproj.php?Season=2026&GameWeek=2&LeagueID=107644) | Public FFToday PPR projection scores, ordered within position | 32 / 73 / 100 / 45 / 32 / unavailable |

ESPN and FFToday are projection-derived ranks, not additional named expert rank lists.
Equal point projections receive tied midranks. No projected-point values are averaged
with ranks. No artificial bottom rank is assigned to missing players.

### RotoBaller

The public page embeds `rbRankings.currentWeek` and `season`. Both must match.
Its public `rankings-mobile-cards.js` calls
`/wp-json/rb/v1/rankings?league=Overall&perPage=600&spreadsheet=ppr`.
That explicit PPR request matters: a request with only `spreadsheet=ppr` returned a
different/default ordering during investigation. The adapter uses the complete request.
The client filters overall rows by position and renumbers, which Fieldwork follows.
The API must return its complete declared player count, unique ranks and identities,
and current-season row update dates. JSON hashes and retrieval times are archived.

The [weekly article](https://www.rotoballer.com/2026-fantasy-football-rankings-week-2-start-sit/1933468)
credits Nick Mariano, but the public tool describes its data as staff ranks. Accordingly
Fieldwork labels this publisher-level rather than assigning premium analysts' names.
Engel and Calandro premium categories are not requested. Numeric projection fields in
this feed contain inconsistent horizons, so they are not used; only the verified ranks.
The edition gate is page-level: the API does not independently echo season/week on every
ranking row. This is less strong than ESPN's per-record edition metadata.

### ESPN

The unauthenticated public fantasy game endpoint is
`/apis/v3/games/ffl/seasons/{year}/segments/0/leaguedefaults/3` at
`https://lm-api-reads.fantasy.espn.com`. `view=mSettings` identifies the preset as
FFL PPR Scoring. `view=kona_player_info`, `scoringPeriodId`, and a JSON `filter` query
return the player pool. A limit requires a sort, so the request sets limit 2000 plus
`sortPercOwned`; 1042 players were returned on this inspection. If the limit is reached,
the adapter rejects potential truncation.

Only stats matching season, week, `statSourceId=1` (projected), and
`statSplitTypeId=1` (weekly) are considered. Actual and season-total rows are excluded.
Every `appliedTotal` is recomputed from the returned public scoring weights (including
position overrides) within .02 points. The preset must explicitly award one point per
reception and four per passing TD. Positive projections are ranked; all six positions
must be present. Public team metadata supplies names and abbreviations.
ESPN's [scoring documentation](https://support.espn.com/hc/en-us/articles/360031085331-League-Scoring-Types-Standard-and-Non-PPR)
also identifies its standard setup as full PPR.

This does not import ESPN+ editorial rankings. Publisher projection revision times are
not provided; retrieval timestamps are explicitly distinguished from publication times.

### FFToday

The public scoring selector identifies `LeagueID=107644` as FFToday PPR. The adapter
checks the rendered `FFToday PPR Scoring:` label and exact year/week in the page title.
It reads visible player rows and their fantasy point column, follows pagination,
and ranks only after combining pages so ties across page boundaries are handled.
No login or custom league is required for this predefined scoring preset.
No D/ST projection endpoint has been verified, so that source-position is unavailable.
Publisher revision time is unavailable; the UI says retrieved, not published.

## Explicitly excluded references

- [Boris Chen](https://www.borischen.co/): its stated input is FantasyPros rankings.
  Linked for reference, not counted as another independent vote.
- [theScore / Eric Patterson](https://www.thescore.com/author/eric-patterson): the current
  [Week 2 RB page](https://www.thescore.com/nflfan/news/3600616/fantasy-week-2-rankings-running-backs-early-edition)
  explicitly labels its rankings half-PPR. Not converted by guessing.
- [Rotoworld / Patrick Daugherty](https://www.nbcsports.com/fantasy/football/news/week-2-fantasy-football-rankings-rb):
  free weekly ranks are readable, but full-PPR scoring was not verified. Held out.

## Validation

Local generation: 472 player identities, 67 available source-position feeds of 78.
Identity joins retain position and use team for D/ST. Explicit nickname aliases for
Kenneth/Kenny Gainwell and Marquise/Hollywood Brown were cross-checked with ESPN IDs
4371733 / 4241372 and nflverse player metadata. Ambiguous matches never receive a guessed join.

31 Python tests pass, including wrong week/year/scoring rejection, ESPN actual-vs-projected
selection and scoring recomputation, tied ranks, duplicate identity/vote rejection,
D/ST matching, nickname matching, and a frozen historical registry. Node aggregation
regressions pass. Browser checks confirmed 13-source selection, individual votes,
publisher/model labels, unavailable-feed reasons and the nonvoting references.

Failed new sources are isolated and visible. The daily/Sunday/Thursday/Monday publication
schedule and dated Git archive already cover the new adapters; no paid service added.
