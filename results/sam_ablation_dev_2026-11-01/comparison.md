# SAM ablation (dev set) — joined comparison

## Caveats — these travel with every number below

1. **Post-hoc.** The no-SAM arm was defined on 2026-11-01, after the
   gate, the pivot, and the confirmation run were all known. This is a
   supplementary diagnostic, not a pre-registered comparison, and must
   always be described as post-hoc and supplementary.
2. **Dev is the design set.** The rules' thresholds were tuned on these
   clips. Absolute dev numbers are optimistic for BOTH arms; only the
   within-dev delta between arms is informative, and even it is a
   dev-set quantity.
3. **The frozen test was not touched** — not run, not read for scoring.
   The sealed subjects 3–5 were not touched. Headline numbers
   (confirmation run) are unchanged by this analysis.
4. **Zero SAM calls were made.** The shipped arm is the recorded gate
   output (`results/gate_d1_dev_results.csv`, `rules_disposition`,
   config hash `6d7c03257b12ab00`); the no-SAM arm needs no SAM by
   construction.
5. **Confirmation is unreachable in the no-SAM arm by construction**:
   confirming requires both posture phases, and posture is SAM
   evidence with no motion-signal equivalent. Read the confirmed
   delta as "what confirmation costs", not as a tuning failure.
6. **The motion stillness is a construction, and its sensitivity is
   reported, not hidden.** The arm of record (v2) anchors the
   stillness window at the descent run's end and reads "moved after
   the descent" as a new motion burst under the frozen hysteresis.
   The originally defined reading (v1, core-anchored activity level)
   was found to book the descent's own envelope tail as post-descent
   movement; it and the intermediate reading (v2a) are reported in
   the appendix. See METHODS_AMENDMENT.md for the full account and
   the recorded instance that exposed it.
7. Further known asymmetries (window span = segment rather than
   track; the shipped arm's multi-track verdict merge has no motion
   counterpart; no keyframe-fallback descent; no no_evidence path)
   are documented in METHODS.md and qualify every per-event
   difference.
8. **Intervals are per-arm.** The intervals shown are per-arm Wilson
   intervals on paired events; the between-arm deltas carry no
   paired interval, and small-stratum deltas (e.g. UP-Fall: 15
   falls, 9 ADL events) should not be over-read.

Arm definition, in one line: identical gate, identical timing,
identical thresholds and scoring; SAM-derived phases (pre/post
posture, keyframe-fallback descent) treated as evidence-absent, and
stillness replaced by its motion-signal equivalent. Full definition:
METHODS.md + METHODS_AMENDMENT.md.

Note what the arm removes: not SAM segmentation evidence alone,
but SAM-derived evidence together with the SAM-dependent track
logic in this pipeline (track-span windows and the multi-track
verdict merge). Every delta below is attributable to that bundle,
not to segmentation evidence in isolation.


### All dev events (falls 99, ADL 92)

| Measure | rules+SAM (recorded) | no-SAM v2 (this run) | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 71/99 = 0.717 [0.622, 0.796] | 98/99 = 0.990 [0.945, 0.998] | +0.273 |
| Falls confirmed | 26/99 = 0.263 [0.186, 0.357] | 0/99 = 0.000 [0.000, 0.037] | -0.263 |
| Falls escalated | 45/99 = 0.455 [0.360, 0.552] | 98/99 = 0.990 [0.945, 0.998] | +0.535 |
| Falls cleared | 27/99 = 0.273 [0.195, 0.368] | 0/99 = 0.000 [0.000, 0.037] | -0.273 |
| Falls gate-missed | 1/99 = 0.010 [0.002, 0.055] | 1/99 = 0.010 [0.002, 0.055] | +0.000 |
| Falls missed (cleared+gate-missed) | 28/99 = 0.283 [0.204, 0.378] | 1/99 = 0.010 [0.002, 0.055] | -0.273 |
| ADL false alarms (confirmed) | 4/92 = 0.043 [0.017, 0.107] | 0/92 = 0.000 [0.000, 0.040] | -0.043 |
| ADL escalated | 52/92 = 0.565 [0.463, 0.662] | 92/92 = 1.000 [0.960, 1.000] | +0.435 |
| ADL cleared | 36/92 = 0.391 [0.298, 0.493] | 0/92 = 0.000 [0.000, 0.040] | -0.391 |
| ADL gate-missed | 0/92 = 0.000 [0.000, 0.040] | 0/92 = 0.000 [0.000, 0.040] | +0.000 |
| Escalation rate (all events) | 97/191 = 0.508 [0.437, 0.578] | 190/191 = 0.995 [0.971, 0.999] | +0.487 |

### Stratum: up_fall (falls 15, ADL 9)

| Measure | rules+SAM (recorded) | no-SAM v2 (this run) | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 13/15 = 0.867 [0.621, 0.963] | 15/15 = 1.000 [0.796, 1.000] | +0.133 |
| Falls confirmed | 8/15 = 0.533 [0.301, 0.752] | 0/15 = 0.000 [0.000, 0.204] | -0.533 |
| Falls escalated | 5/15 = 0.333 [0.152, 0.583] | 15/15 = 1.000 [0.796, 1.000] | +0.667 |
| Falls cleared | 2/15 = 0.133 [0.037, 0.379] | 0/15 = 0.000 [0.000, 0.204] | -0.133 |
| Falls gate-missed | 0/15 = 0.000 [0.000, 0.204] | 0/15 = 0.000 [0.000, 0.204] | +0.000 |
| Falls missed (cleared+gate-missed) | 2/15 = 0.133 [0.037, 0.379] | 0/15 = 0.000 [0.000, 0.204] | -0.133 |
| ADL false alarms (confirmed) | 0/9 = 0.000 [0.000, 0.299] | 0/9 = 0.000 [0.000, 0.299] | +0.000 |
| ADL escalated | 1/9 = 0.111 [0.020, 0.435] | 9/9 = 1.000 [0.701, 1.000] | +0.889 |
| ADL cleared | 8/9 = 0.889 [0.565, 0.980] | 0/9 = 0.000 [0.000, 0.299] | -0.889 |
| ADL gate-missed | 0/9 = 0.000 [0.000, 0.299] | 0/9 = 0.000 [0.000, 0.299] | +0.000 |
| Escalation rate (all events) | 6/24 = 0.250 [0.120, 0.449] | 24/24 = 1.000 [0.862, 1.000] | +0.750 |

### Stratum: le2i (falls 84, ADL 83)

| Measure | rules+SAM (recorded) | no-SAM v2 (this run) | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 58/84 = 0.690 [0.585, 0.779] | 83/84 = 0.988 [0.936, 0.998] | +0.298 |
| Falls confirmed | 18/84 = 0.214 [0.140, 0.313] | 0/84 = 0.000 [0.000, 0.044] | -0.214 |
| Falls escalated | 40/84 = 0.476 [0.373, 0.582] | 83/84 = 0.988 [0.936, 0.998] | +0.512 |
| Falls cleared | 25/84 = 0.298 [0.210, 0.402] | 0/84 = 0.000 [0.000, 0.044] | -0.298 |
| Falls gate-missed | 1/84 = 0.012 [0.002, 0.064] | 1/84 = 0.012 [0.002, 0.064] | +0.000 |
| Falls missed (cleared+gate-missed) | 26/84 = 0.310 [0.221, 0.415] | 1/84 = 0.012 [0.002, 0.064] | -0.298 |
| ADL false alarms (confirmed) | 4/83 = 0.048 [0.019, 0.117] | 0/83 = 0.000 [0.000, 0.044] | -0.048 |
| ADL escalated | 51/83 = 0.614 [0.507, 0.712] | 83/83 = 1.000 [0.956, 1.000] | +0.386 |
| ADL cleared | 28/83 = 0.337 [0.245, 0.444] | 0/83 = 0.000 [0.000, 0.044] | -0.337 |
| ADL gate-missed | 0/83 = 0.000 [0.000, 0.044] | 0/83 = 0.000 [0.000, 0.044] | +0.000 |
| Escalation rate (all events) | 91/167 = 0.545 [0.469, 0.619] | 166/167 = 0.994 [0.967, 0.999] | +0.449 |

## How to read this

What is robust across every stillness reading (v1, v2a, v2):

- **Confirmation is SAM-carried.** Falls confirmed fall 26/99 → 0 and
  ADL false alarms 4/92 → 0 in all readings, by construction: the
  posture phases are the confirmation path.
- **The shipped joint operating point is unreachable under every
  motion-only operationalization tried.** The
  shipped arm holds falls not-missed at 0.717 while clearing 36/92
  ADL events. No motion reading holds both: v1 and v2a keep ADL
  clearances (70, 64) only by clearing most falls as well (falls
  not-missed 0.222, 0.303); v2 keeps the falls (0.990) only by
  escalating all 92 ADL events. Motion evidence alone trades one
  failure mode for the other at every operationalization tried.
- By the shipped rules' structure, the only veto available on a
  slow descent is the SAM posture phase (a descent contradicted by
  "not horizontal after"), and the only stillness test reads the
  SAM mask centroid — so the shipped arm's ADL clearances and its
  fall clearances are attributable to those SAM channels. That
  attribution is design inference from the rule structure, not a
  finding of this comparison: the tables above count outcomes, not
  phases. Nor does any single sensitivity statement hold for the
  motion energy signal: across the three stillness readings it
  brackets the shipped arm in both directions — one reading (v1)
  clears far more falls than the shipped arm (76/99 against 27/99),
  another (v2) clears none — so the energy signal cannot be said
  simply to lack the centroid's sensitivity.

What is NOT robust: falls not-missed and the escalation rate swing
with the stillness construction (0.222 / 0.303 / 0.990). Any single
one of those numbers quoted without its construction would mislead;
the deltas that survive are the structural ones above.

## Appendix — sensitivity to the stillness construction

Pooled dev events under the two alternative stillness readings (same arm otherwise). V1 is the definition as originally written; v2a isolates the anchor change; v2 (the arm of record, above) additionally reads post-descent movement as a new burst.

### V1 reading (as originally defined) (falls 99, ADL 92)

| Measure | rules+SAM (recorded) | no-SAM v1 | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 71/99 = 0.717 [0.622, 0.796] | 22/99 = 0.222 [0.152, 0.314] | -0.495 |
| Falls confirmed | 26/99 = 0.263 [0.186, 0.357] | 0/99 = 0.000 [0.000, 0.037] | -0.263 |
| Falls escalated | 45/99 = 0.455 [0.360, 0.552] | 22/99 = 0.222 [0.152, 0.314] | -0.232 |
| Falls cleared | 27/99 = 0.273 [0.195, 0.368] | 76/99 = 0.768 [0.675, 0.840] | +0.495 |
| Falls gate-missed | 1/99 = 0.010 [0.002, 0.055] | 1/99 = 0.010 [0.002, 0.055] | +0.000 |
| Falls missed (cleared+gate-missed) | 28/99 = 0.283 [0.204, 0.378] | 77/99 = 0.778 [0.686, 0.848] | +0.495 |
| ADL false alarms (confirmed) | 4/92 = 0.043 [0.017, 0.107] | 0/92 = 0.000 [0.000, 0.040] | -0.043 |
| ADL escalated | 52/92 = 0.565 [0.463, 0.662] | 22/92 = 0.239 [0.164, 0.336] | -0.326 |
| ADL cleared | 36/92 = 0.391 [0.298, 0.493] | 70/92 = 0.761 [0.664, 0.836] | +0.370 |
| ADL gate-missed | 0/92 = 0.000 [0.000, 0.040] | 0/92 = 0.000 [0.000, 0.040] | +0.000 |
| Escalation rate (all events) | 97/191 = 0.508 [0.437, 0.578] | 44/191 = 0.230 [0.176, 0.295] | -0.277 |

### V2a reading (run anchor, activity level) (falls 99, ADL 92)

| Measure | rules+SAM (recorded) | no-SAM v2a | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 71/99 = 0.717 [0.622, 0.796] | 30/99 = 0.303 [0.221, 0.400] | -0.414 |
| Falls confirmed | 26/99 = 0.263 [0.186, 0.357] | 0/99 = 0.000 [0.000, 0.037] | -0.263 |
| Falls escalated | 45/99 = 0.455 [0.360, 0.552] | 30/99 = 0.303 [0.221, 0.400] | -0.152 |
| Falls cleared | 27/99 = 0.273 [0.195, 0.368] | 68/99 = 0.687 [0.590, 0.770] | +0.414 |
| Falls gate-missed | 1/99 = 0.010 [0.002, 0.055] | 1/99 = 0.010 [0.002, 0.055] | +0.000 |
| Falls missed (cleared+gate-missed) | 28/99 = 0.283 [0.204, 0.378] | 69/99 = 0.697 [0.600, 0.779] | +0.414 |
| ADL false alarms (confirmed) | 4/92 = 0.043 [0.017, 0.107] | 0/92 = 0.000 [0.000, 0.040] | -0.043 |
| ADL escalated | 52/92 = 0.565 [0.463, 0.662] | 28/92 = 0.304 [0.220, 0.405] | -0.261 |
| ADL cleared | 36/92 = 0.391 [0.298, 0.493] | 64/92 = 0.696 [0.595, 0.780] | +0.304 |
| ADL gate-missed | 0/92 = 0.000 [0.000, 0.040] | 0/92 = 0.000 [0.000, 0.040] | +0.000 |
| Escalation rate (all events) | 97/191 = 0.508 [0.437, 0.578] | 58/191 = 0.304 [0.243, 0.372] | -0.204 |

## Per-event agreement (arm of record, v2)

98/191 events agree; 93 differ.

| event | dataset | label | rules+SAM | no-SAM v2 |
|---|---|---|---|---|
| le2i_coffee-room-01_video-01 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-02 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-03 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-07 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-08 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-10 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-11 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-14 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-15 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-17 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-18 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-19 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-20 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-21 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-23 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-27 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-28 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-30 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-31 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-32 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-33 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-35 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-37 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-40 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-44 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-45 | le2i | fall | confirmed | escalated |
| le2i_coffee-room-01_video-47 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-02 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-03 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-04 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-13 | le2i | fall | cleared | escalated |
| le2i_home-01_video-14 | le2i | fall | cleared | escalated |
| le2i_home-01_video-15 | le2i | fall | cleared | escalated |
| le2i_home-01_video-17 | le2i | fall | cleared | escalated |
| le2i_home-01_video-19 | le2i | fall | cleared | escalated |
| le2i_home-01_video-20 | le2i | fall | cleared | escalated |
| le2i_home-01_video-21 | le2i | fall | cleared | escalated |
| le2i_home-01_video-22 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-23 | le2i | fall | cleared | escalated |
| le2i_home-01_video-29 | le2i | fall | cleared | escalated |
| le2i_home-01_video-30 | le2i | fall | cleared | escalated |
| le2i_home-02_video-31 | le2i | fall | cleared | escalated |
| le2i_home-02_video-35 | le2i | fall | cleared | escalated |
| le2i_home-02_video-38 | le2i | adl | cleared | escalated |
| le2i_home-02_video-39 | le2i | adl | cleared | escalated |
| le2i_home-02_video-42 | le2i | adl | cleared | escalated |
| le2i_home-02_video-43 | le2i | adl | cleared | escalated |
| le2i_home-02_video-44 | le2i | adl | cleared | escalated |
| le2i_home-02_video-45 | le2i | adl | cleared | escalated |
| le2i_home-02_video-46 | le2i | adl | cleared | escalated |
| le2i_home-02_video-47 | le2i | adl | cleared | escalated |
| le2i_home-02_video-48 | le2i | adl | cleared | escalated |
| le2i_home-02_video-49 | le2i | adl | cleared | escalated |
| le2i_home-02_video-50 | le2i | adl | cleared | escalated |
| le2i_home-02_video-51 | le2i | adl | cleared | escalated |
| le2i_home-02_video-54 | le2i | adl | cleared | escalated |
| le2i_home-02_video-58 | le2i | adl | cleared | escalated |
| le2i_lecture-room_video-01 | le2i | adl | cleared | escalated |
| le2i_lecture-room_video-02 | le2i | adl | confirmed | escalated |
| le2i_lecture-room_video-03 | le2i | adl | confirmed | escalated |
| le2i_lecture-room_video-04 | le2i | adl | cleared | escalated |
| le2i_lecture-room_video-11 | le2i | adl | cleared | escalated |
| le2i_lecture-room_video-12 | le2i | adl | cleared | escalated |
| le2i_office_video-04 | le2i | adl | cleared | escalated |
| le2i_office_video-06 | le2i | adl | confirmed | escalated |
| le2i_office_video-07 | le2i | adl | cleared | escalated |
| le2i_office_video-08 | le2i | adl | cleared | escalated |
| le2i_office_video-09 | le2i | adl | cleared | escalated |
| le2i_office_video-11 | le2i | adl | cleared | escalated |
| le2i_office_video-13 | le2i | adl | confirmed | escalated |
| le2i_office_video-15 | le2i | adl | cleared | escalated |
| le2i_office_video-17 | le2i | adl | cleared | escalated |
| le2i_office_video-23 | le2i | adl | cleared | escalated |
| le2i_office_video-25 | le2i | adl | cleared | escalated |
| le2i_office_video-30 | le2i | adl | cleared | escalated |
| upfall:S1:A11:T1 | up_fall | adl | cleared | escalated |
| upfall:S1:A11:T2 | up_fall | adl | cleared | escalated |
| upfall:S1:A11:T3 | up_fall | adl | cleared | escalated |
| upfall:S1:A1:T1 | up_fall | fall | confirmed | escalated |
| upfall:S1:A1:T2 | up_fall | fall | confirmed | escalated |
| upfall:S1:A1:T3 | up_fall | fall | confirmed | escalated |
| upfall:S1:A2:T1 | up_fall | fall | confirmed | escalated |
| upfall:S1:A2:T3 | up_fall | fall | confirmed | escalated |
| upfall:S1:A3:T1 | up_fall | fall | cleared | escalated |
| upfall:S1:A3:T2 | up_fall | fall | confirmed | escalated |
| upfall:S1:A4:T1 | up_fall | fall | cleared | escalated |
| upfall:S1:A4:T3 | up_fall | fall | confirmed | escalated |
| upfall:S1:A5:T1 | up_fall | fall | confirmed | escalated |
| upfall:S1:A8:T1 | up_fall | adl | cleared | escalated |
| upfall:S1:A8:T3 | up_fall | adl | cleared | escalated |
| upfall:S1:A9:T1 | up_fall | adl | cleared | escalated |
| upfall:S1:A9:T2 | up_fall | adl | cleared | escalated |
| upfall:S1:A9:T3 | up_fall | adl | cleared | escalated |
