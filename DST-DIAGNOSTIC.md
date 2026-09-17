# Week 2 D/ST diagnostic — 2026-09-16

Reproduced published Jacksonville projection: 11.424640 (displayed 11.42).
Subvertadown screenshot image-7.png: Jacksonville 5.0. Difference 6.42.
This diagnoses Fieldwork; Subvertadown's Jacksonville components and coefficients are not available here.
No production model or published projections were changed.

## What produces 11.42

| Component | Expected statistic | Fantasy points |
|---|---:|---:|
| Sacks | 3.270 | 3.270 |
| Interceptions plus opponent fumbles recovered | 2.094 | 4.187 |
| Defensive / special-teams TDs | 0.201 | 1.205 |
| Blocks / safeties | 0.121 | 0.241 |
| Points-allowed bands integrated over residual scenarios | 15.498 mean PA | 2.522 |

PA contribution is an average across outcome scenarios, not the score for 15.5 PA alone.

## Input evidence

Cached nflverse inputs record Jacksonville Week 1 against Cleveland: 5 sacks, 1 interception,
1 opponent fumble recovery, 10 scoreboard points allowed. Fieldwork scoring: 13 fantasy points.
Jacksonville recency-weighted fantasy baseline entering Week 2: 10.818.
Denver Week 1 offense inputs: 131 passing yards, 61 rushing yards, 1 passing TD,
1 interception, 4 sacks suffered.
Denver matchup residual: -0.828 points, averaged over up to six prior defenses.
Setting that residual alone to zero changes Jacksonville from 11.425 to 11.447.
Thus the explicit historical DST-versus-Denver adjustment is slightly negative, not the reason for optimism.

## Fixed-model sensitivity experiments

Same trained coefficients and same 2024 residual scenarios throughout.

| Experiment | Jacksonville projection |
|---|---:|
| Published inputs | 11.42 |
| Remove all 2026 observations from feature history | 7.41 |
| Replace own historical-statistics block with training means | 7.98 |
| Replace opponent team-statistics block with training means | 9.62 |
| Replace latest-minus-average block with training means | 11.07 |
| Replace own kicking-stat history and latest changes with training means | 9.89 |

These are separate input-sensitivity experiments, NOT additive causal contributions.
The no-2026 experiment also changes history counts, recency, and matchup histories.
Training-mean replacements can create combinations not observed in real games.

## Structural concerns

960 training team-games, 124 feature columns in the DST Ridge model.
DST records inherit full team box scores. Generic average/latest blocks therefore include
team kicking and offensive statistics, plus separate own-team averages that duplicate some inputs.
For example, avg:attempts and team:attempts have identical Jacksonville PA contributions (-0.794 each).
This is not future-data leakage, but redundant features affect Ridge regularization and complicate attribution.
The largest individual positive pre-clipping non-PA attribution relative to training means is
avg:fg_made_40_49 (+0.665 fantasy points). It is an association, not a causal football claim.
Neutralizing all own kicking-history features reduces forecast by 1.54 points.
Regularization does not establish that these relationships generalize.

## Interpretation

Week 1 observations collectively lift the estimate approximately 4.02 points in the fixed-model experiment.
Own performance and Denver offensive inputs drive optimism; explicit matchup residual does not.
The model projects substantial turnover production; that remains uncertain, not a verified matchup edge.
Different scoring presets may explain part of the comparison but cannot be quantified from the screenshot alone.
Do not tune toward Subvertadown's 5.0 or treat agreement as accuracy.
Next model revision should evaluate a compact position-specific feature set using chronological development
splits and prospective forecasts; 2025 has already been inspected and should not become a repeated tuning target.

Reproduction: python diagnose_dst.py (uses existing .cache CSVs; outputs output/dst-diagnostic.json).
