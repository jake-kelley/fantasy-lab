# All-position revision: v0.3

This revision improves retrospective error in all nine position groups. It does **not**
reproduce Subvertadown across all positions. Expert screenshots are comparison targets
only: their values are never imported by model fitting or configuration selection.

## What changed

Separate chronological candidate selection replaces one shared modeling recipe. QB/RB,
WR/LB and DL use different blends of the original component model and recent production.
TE/K/DB use curated inputs and exposure-scaled shrinkage of event rates. D/ST forecasts
opportunities and rates separately. K and D/ST incorporate free schedule totals/spreads
when available and fall back to statistical models when absent.

New context measures prior EPA per play, QB hits, volume, efficiency, and points scored
or allowed relative to opponents' prior expectations. Features update only after an
entire week's predictions. QB role-weighted histories and additional factor variants
were tested; selection rejected them where development MAE was worse.

RB/WR/TE team-total forecasts are independent PPR models. Their neutral-opponent bonus
definition differs from Subvertadown; they are not individual-player forecasts.

## Historical comparison

Both versions below evaluated on the same 2025 weeks 13–18 participants. Lower MAE is
better. Point coefficients fitted on 2024; configuration selection used 2024 development
weeks and 2025 weeks 1–12. See `position-evaluation-extended.json` for unrounded values,
RMSE, coverage and sample sizes.

| Position | v0.2 MAE | v0.3 MAE | Rolling baseline MAE |
|---|---:|---:|---:|
| QB | 6.915 | 6.511 | 6.564 |
| RB | 4.353 | 4.066 | 4.031 |
| WR | 4.201 | 4.027 | 3.951 |
| TE | 3.189 | 2.878 | 2.913 |
| K | 4.044 | 3.943 | 4.182 |
| D/ST | 3.986 | 3.900 | 4.377 |
| DL | 1.842 | 1.830 | 1.916 |
| LB | 2.240 | 2.188 | 2.200 |
| DB | 2.081 | 2.062 | 2.097 |

All nine also improve RMSE versus v0.2. RB/WR still lose on MAE to the rolling baseline.
Team-total MAE: RB 8.052 versus baseline 8.395; WR 10.598 versus 10.594; TE 6.473 versus
6.554. WR team totals do not beat that baseline.

## Supplied Week 2 screenshot agreement

Spearman rank correlation measures agreement, **not predictive accuracy**. Values below
compare the supplied screenshots with the saved v0.2/v0.3 outputs, not later expert updates.
Different scoring and baseline definitions limit direct point comparisons.

| Comparison | Matched entities | v0.2 correlation | v0.3 correlation |
|---|---:|---:|---:|
| QB | 31 | 0.668 | 0.623 |
| K | 31 | 0.550 | 0.611 |
| D/ST | 32 | 0.634 | 0.900 |
| RB team total | 32 | — | 0.777 |
| WR team total | 32 | — | 0.707 |

Mean absolute point differences: QB 2.013 → 2.469; K 0.991 → 0.772; D/ST 1.182 → 0.835.
Jacksonville D/ST moves from 7.97 to 5.75, against the screenshot's 5.0.
RB matchup-bonus correlation is 0.554; WR just 0.105. QB agreement got worse, and WR
bonuses remain a major unresolved difference. No TE/IDP expert comparison was available.
See `snapshot-comparison.json` for every matched row and the screenshot transcription
in `subvertadown-week2-snapshot.json`. Combined-player entries were excluded; Andy and
Andres Borregales were explicitly matched as the same New England kicker.

## Limits and reproduction

This is retrospective research. Earlier versions' 2025 results influenced development;
weeks 13–18 must not be described as a pristine holdout. Historical schedule market lines
are closing quotes, not archived Tuesday information. Evaluation conditions on recorded
participation, not every eligible player or correct starter selection. No significance
or superiority over experts is established. Weather and injury workload redistribution
remain unmodeled. Prospective timestamped evaluation remains necessary.

Historical quote documentation: [nflfastR release notes](https://github.com/nflverse/nflfastR/blob/master/NEWS.md).
No target-game actual score or observed weather is used as a predictor.

```sh
python -m pipeline.run
python -m pipeline.tune_positions extended-select
python -m pipeline.tune_positions extended-evaluate
python -m pipeline.tune_team_outlook
python -m pipeline.run
python -m unittest discover -s tests -v
```

Research tuning reads downloaded `.cache` files. Remove only `output/tuning-dataset.pkl`
before retuning if raw files or feature construction changed; it is a local derived cache.
Production never reads that pickle or retunes settings. Intermediate `position-selection.json`
and `position-evaluation.json` preserve earlier research, not production choices.
`compare_snapshot.py` compares with the currently published site; after deployment that
will no longer represent v0.2. Preserve the committed comparison for the before/after audit.
