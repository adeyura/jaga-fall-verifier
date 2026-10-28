# D1 gate run — dev split (2026-10-28)

Config hash `6d7c03257b12ab00` (verified at run start and stamped on every record). Evidence form: traces only (D3). Set: dev split, 215 clips / 191 events (99 fall, 92 ADL); UP-Fall Subject 1 + Le2i-dev. Test split untouched.

## D1 verdict: FAIL

| Criterion | Required | Measured | Result |
|---|---|---|---|
| 1. Safety veto: additional missed falls vs rules-only | 0 | 0 | PASS |
| 2a. Hard-negative FA reduction, relative | >= 40% | 0.0% (4 -> 4) | FAIL |
| 2b. Hard-negative FA reduction, absolute | >= 3 | 0 | FAIL |
| 3. Usable adjudicator verdicts | >= 95% | 141/142 = 0.993 [0.961, 0.999] | PASS |

Missed falls: rules-only 28, full 28; missed by full only: none; missed by rules only: none.
FA discordant pairs: both arms 4, rules-only only 0, full only 0.
THIN POOL, stated plainly: rules-only produced only 4 false alarms on the dev hard-negative pool, so the >=3-absolute criterion rests on 2-3 clips and the relative criterion on a handful of events.

## Stratum: overall

### Rules-only
- Fall events: 99; confirmed 26, escalated 45, cleared 27, gate-missed 1, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 71/99 = 0.717 [0.622, 0.796].
- ADL events: 92; false alarms (confirmed) 4, escalated 52, cleared 36, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 26/30 = 0.867 [0.703, 0.947].
- Escalation rate (all events, errors excluded): 97/191 = 0.508 [0.437, 0.578].
- False alarms per hour of ADL footage: 7.29 (4 FA / 0.55 h)

### Full (rules + Spark traces)
- Fall events: 99; confirmed 23, escalated 48, cleared 27, gate-missed 1, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 71/99 = 0.717 [0.622, 0.796].
- ADL events: 92; false alarms (confirmed) 4, escalated 52, cleared 36, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 23/27 = 0.852 [0.675, 0.941].
- Escalation rate (all events, errors excluded): 100/191 = 0.524 [0.453, 0.593].
- False alarms per hour of ADL footage: 7.29 (4 FA / 0.55 h)

## Stratum: up_fall

### Rules-only
- Fall events: 15; confirmed 8, escalated 5, cleared 2, gate-missed 0, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 13/15 = 0.867 [0.621, 0.963].
- ADL events: 9; false alarms (confirmed) 0, escalated 1, cleared 8, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 8/8 = 1.000 [0.676, 1.000].
- Escalation rate (all events, errors excluded): 6/24 = 0.250 [0.120, 0.449].
- False alarms per hour of ADL footage: 0.00 (0 FA / 0.11 h)

### Full (rules + Spark traces)
- Fall events: 15; confirmed 6, escalated 7, cleared 2, gate-missed 0, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 13/15 = 0.867 [0.621, 0.963].
- ADL events: 9; false alarms (confirmed) 0, escalated 1, cleared 8, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 6/6 = 1.000 [0.610, 1.000].
- Escalation rate (all events, errors excluded): 8/24 = 0.333 [0.180, 0.533].
- False alarms per hour of ADL footage: 0.00 (0 FA / 0.11 h)

## Stratum: le2i

### Rules-only
- Fall events: 84; confirmed 18, escalated 40, cleared 25, gate-missed 1, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 58/84 = 0.690 [0.585, 0.779].
- ADL events: 83; false alarms (confirmed) 4, escalated 51, cleared 28, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 18/22 = 0.818 [0.615, 0.927].
- Escalation rate (all events, errors excluded): 91/167 = 0.545 [0.469, 0.619].
- False alarms per hour of ADL footage: 9.04 (4 FA / 0.44 h)

### Full (rules + Spark traces)
- Fall events: 84; confirmed 17, escalated 41, cleared 25, gate-missed 1, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 58/84 = 0.690 [0.585, 0.779].
- ADL events: 83; false alarms (confirmed) 4, escalated 51, cleared 28, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 17/21 = 0.810 [0.600, 0.923].
- Escalation rate (all events, errors excluded): 92/167 = 0.551 [0.475, 0.624].
- False alarms per hour of ADL footage: 9.04 (4 FA / 0.44 h)

## Cascade metrics (clip level, main pass)

- Gate recall on fall clips: 113/114 = 0.991 [0.952, 0.998] reached the SAM stage; gate-missed fall clips 1.
- SAM keyframes: 4890 total, 214 empty (4.4%); fresh API calls 4777.
- Pipeline-error clips: 0 ([]).
- Segment-level SAM/rules errors recorded: 0.
- Latency per clip: median 43.7s, mean 50.1s.

## Baselines (D5, event level)

| Baseline | Falls called fall | ADL called fall |
|---|---|---|
| aspect-only | 89/99 | 87/92 |
| spark-only | 49/99 | 7/92 |

## D3 A/B/C rerun — UP-Fall dev (event level, full arm)

| Form | Falls confirmed | Falls escalated | Falls missed | ADL FA | ADL escalated | ADL cleared |
|---|---|---|---|---|---|---|
| traces | 6/15 | 7/15 | 2/15 | 0/9 | 1/9 | 8/9 |
| raw | 5/15 | 8/15 | 2/15 | 0/9 | 1/9 | 8/9 |
| overlay | 7/15 | 6/15 | 2/15 | 0/9 | 1/9 | 8/9 |

## Spend

```json
{
 "main_spend": {
  "sam_est_usd": 11.9425,
  "sam_images_billed": 4777,
  "sam_runs_cost_unknown": 0,
  "adjudications": 142,
  "adjudications_usable": 141,
  "adj_prompt_tokens": 166259,
  "adj_completion_tokens": 470196
 },
 "abc_spend": {
  "sam_est_usd": 0.0,
  "sam_images_billed": 0,
  "sam_runs_cost_unknown": 0,
  "adjudications": 44,
  "adjudications_usable": 43,
  "adj_prompt_tokens": 101776,
  "adj_completion_tokens": 141183
 },
 "baselines_spend": {
  "sam_est_usd": 0.0,
  "sam_images_billed": 0,
  "sam_runs_cost_unknown": 0,
  "adjudications": 209,
  "adjudications_usable": 202,
  "adj_prompt_tokens": 308515,
  "adj_completion_tokens": 730238
 }
}
```

Limitations: staged falls by young actors in lab rooms; dataset performance is not deployment performance. Le2i is room×class confounded (see split freeze note). UP-Fall ADL categories are 3 events each; stumble-and-recover and crouch do not exist as labeled categories in either dataset.
