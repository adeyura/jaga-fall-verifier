# Confirmation run — frozen test split (2026-10-29)

Config hash `6d7c03257b12ab00` (verified at run start and stamped on every record). Arm: `pivot_rules_primary` — the pivot configuration adopted 2026-10-29 (DECISIONS) after the D1 gate FAIL: motion gate -> SAM 3.1 evidence -> features/timing (amended window) -> rules -> D2 alert ladder. Muse Spark is not in this arm; the analyzer asserted no record carries an adjudication. Set: the frozen test split only, 68 clips / 44 events (27 fall, 17 ADL); UP-Fall Subject 2 + Le2i holdout Coffee_room_02. One run; no tuning. Dev and confirmation numbers are labeled and never pooled.

## Stratum: overall

### Pivot (rules-primary)
- Fall events: 27; confirmed 7, escalated 12, cleared 8, gate-missed 0, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 19/27 = 0.704 [0.515, 0.841].
- ADL events: 17; false alarms (confirmed) 0, escalated 12, cleared 4, gate-missed 1, pipeline errors 0.
- Precision at dataset prevalence: 7/7 = 1.000 [0.646, 1.000].
- Escalation rate (all events, errors excluded): 24/44 = 0.545 [0.401, 0.683].
- False alarms per hour of ADL footage: 0.00 (0 FA / 0.18 h)

## Stratum: up_fall

### Pivot (rules-primary)
- Fall events: 15; confirmed 5, escalated 6, cleared 4, gate-missed 0, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 11/15 = 0.733 [0.480, 0.891].
- ADL events: 9; false alarms (confirmed) 0, escalated 5, cleared 3, gate-missed 1, pipeline errors 0.
- Precision at dataset prevalence: 5/5 = 1.000 [0.566, 1.000].
- Escalation rate (all events, errors excluded): 11/24 = 0.458 [0.279, 0.649].
- False alarms per hour of ADL footage: 0.00 (0 FA / 0.10 h)

## Stratum: le2i

### Pivot (rules-primary)
- Fall events: 12; confirmed 2, escalated 6, cleared 4, gate-missed 0, pipeline errors 0.
- Not-missed recall (confirmed or escalated, errors excluded): 8/12 = 0.667 [0.391, 0.862].
- ADL events: 8; false alarms (confirmed) 0, escalated 7, cleared 1, gate-missed 0, pipeline errors 0.
- Precision at dataset prevalence: 2/2 = 1.000 [0.342, 1.000].
- Escalation rate (all events, errors excluded): 13/20 = 0.650 [0.433, 0.819].
- False alarms per hour of ADL footage: 0.00 (0 FA / 0.08 h)

## Cascade metrics (clip level)

- Gate recall on fall clips: 42/42 = 1.000 [0.916, 1.000] reached the SAM stage; gate-missed fall clips 0.
- SAM keyframes: 1524 total, 14 empty (0.9%); fresh API calls 1489.
- Pipeline-error clips: 0 ([]).
- Segment-level SAM/rules errors recorded: 0.
- Latency per clip: median 46.1s, mean 53.1s.

## Spend

```json
{
 "retry_log": [
  {
   "clips": [
    "Subject2Activity4Trial1_Camera1.zip",
    "Subject2Activity4Trial1_Camera2.zip",
    "Subject2Activity4Trial2_Camera1.zip",
    "Subject2Activity4Trial2_Camera2.zip",
    "Subject2Activity4Trial3_Camera1.zip"
   ],
   "unix": 1793207395.2557287
  }
 ],
 "spend": {
  "sam_est_usd": 3.7225,
  "sam_images_billed": 1489,
  "sam_runs_cost_unknown": 0,
  "adjudications": 0
 }
}
```

Limitations: staged falls by young actors in lab rooms; dataset performance is not deployment performance. The Le2i confirmation is a single room's result (Coffee_room_02, a different physical room and camera from dev's Coffee_room_01 but the same scene type), and UP-Fall confirmation a single subject's (Subject 2): the run bounds generalization, it does not establish it. UP-Fall ADL categories are 3 events each; stumble-and-recover and crouch do not exist as labeled categories in either dataset.
