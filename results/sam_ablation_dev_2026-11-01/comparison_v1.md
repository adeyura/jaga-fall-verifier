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
6. Known asymmetries (window span = segment rather than track;
   motion stillness measurable more often than SAM stillness and
   measuring changed area rather than centroid displacement; no
   keyframe-fallback descent; no no_evidence path) are documented in
   METHODS.md and qualify every per-event difference.

Arm definition, in one line: identical gate, identical timing,
identical thresholds and scoring; SAM-derived phases (pre/post
posture, keyframe-fallback descent) treated as evidence-absent, and
stillness replaced by its motion-energy equivalent (changed-area
fraction held at the clip's own activity level over the post-descent
window). Full definition: METHODS.md.


### All dev events (falls 99, ADL 92)

| Measure | rules+SAM (recorded) | no-SAM (this run) | delta |
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

### Stratum: up_fall (falls 15, ADL 9)

| Measure | rules+SAM (recorded) | no-SAM (this run) | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 13/15 = 0.867 [0.621, 0.963] | 1/15 = 0.067 [0.012, 0.298] | -0.800 |
| Falls confirmed | 8/15 = 0.533 [0.301, 0.752] | 0/15 = 0.000 [0.000, 0.204] | -0.533 |
| Falls escalated | 5/15 = 0.333 [0.152, 0.583] | 1/15 = 0.067 [0.012, 0.298] | -0.267 |
| Falls cleared | 2/15 = 0.133 [0.037, 0.379] | 14/15 = 0.933 [0.702, 0.988] | +0.800 |
| Falls gate-missed | 0/15 = 0.000 [0.000, 0.204] | 0/15 = 0.000 [0.000, 0.204] | +0.000 |
| Falls missed (cleared+gate-missed) | 2/15 = 0.133 [0.037, 0.379] | 14/15 = 0.933 [0.702, 0.988] | +0.800 |
| ADL false alarms (confirmed) | 0/9 = 0.000 [0.000, 0.299] | 0/9 = 0.000 [0.000, 0.299] | +0.000 |
| ADL escalated | 1/9 = 0.111 [0.020, 0.435] | 4/9 = 0.444 [0.189, 0.733] | +0.333 |
| ADL cleared | 8/9 = 0.889 [0.565, 0.980] | 5/9 = 0.556 [0.267, 0.811] | -0.333 |
| ADL gate-missed | 0/9 = 0.000 [0.000, 0.299] | 0/9 = 0.000 [0.000, 0.299] | +0.000 |
| Escalation rate (all events) | 6/24 = 0.250 [0.120, 0.449] | 5/24 = 0.208 [0.092, 0.405] | -0.042 |

### Stratum: le2i (falls 84, ADL 83)

| Measure | rules+SAM (recorded) | no-SAM (this run) | delta |
|---|---|---|---|
| Falls not-missed (confirmed+escalated) | 58/84 = 0.690 [0.585, 0.779] | 21/84 = 0.250 [0.170, 0.352] | -0.440 |
| Falls confirmed | 18/84 = 0.214 [0.140, 0.313] | 0/84 = 0.000 [0.000, 0.044] | -0.214 |
| Falls escalated | 40/84 = 0.476 [0.373, 0.582] | 21/84 = 0.250 [0.170, 0.352] | -0.226 |
| Falls cleared | 25/84 = 0.298 [0.210, 0.402] | 62/84 = 0.738 [0.635, 0.820] | +0.440 |
| Falls gate-missed | 1/84 = 0.012 [0.002, 0.064] | 1/84 = 0.012 [0.002, 0.064] | +0.000 |
| Falls missed (cleared+gate-missed) | 26/84 = 0.310 [0.221, 0.415] | 63/84 = 0.750 [0.648, 0.830] | +0.440 |
| ADL false alarms (confirmed) | 4/83 = 0.048 [0.019, 0.117] | 0/83 = 0.000 [0.000, 0.044] | -0.048 |
| ADL escalated | 51/83 = 0.614 [0.507, 0.712] | 18/83 = 0.217 [0.142, 0.317] | -0.398 |
| ADL cleared | 28/83 = 0.337 [0.245, 0.444] | 65/83 = 0.783 [0.683, 0.858] | +0.446 |
| ADL gate-missed | 0/83 = 0.000 [0.000, 0.044] | 0/83 = 0.000 [0.000, 0.044] | +0.000 |
| Escalation rate (all events) | 91/167 = 0.545 [0.469, 0.619] | 39/167 = 0.234 [0.176, 0.303] | -0.311 |

## Per-event agreement

84/191 events agree; 107 differ.

| event | dataset | label | rules+SAM | no-SAM |
|---|---|---|---|---|
| le2i_coffee-room-01_video-02 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-04 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-05 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-06 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-09 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-10 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-11 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-12 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-13 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-16 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-18 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-20 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-21 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-22 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-25 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-27 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-28 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-30 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-32 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-33 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-34 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-35 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-36 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-38 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-39 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-40 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-41 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-43 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-44 | le2i | fall | cleared | escalated |
| le2i_coffee-room-01_video-45 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-46 | le2i | fall | escalated | cleared |
| le2i_coffee-room-01_video-47 | le2i | fall | confirmed | cleared |
| le2i_coffee-room-01_video-48 | le2i | fall | escalated | cleared |
| le2i_home-01_video-01 | le2i | fall | escalated | cleared |
| le2i_home-01_video-02 | le2i | fall | confirmed | cleared |
| le2i_home-01_video-03 | le2i | fall | confirmed | cleared |
| le2i_home-01_video-04 | le2i | fall | confirmed | cleared |
| le2i_home-01_video-05 | le2i | fall | escalated | cleared |
| le2i_home-01_video-06 | le2i | fall | escalated | cleared |
| le2i_home-01_video-09 | le2i | fall | escalated | cleared |
| le2i_home-01_video-15 | le2i | fall | cleared | escalated |
| le2i_home-01_video-19 | le2i | fall | cleared | escalated |
| le2i_home-01_video-20 | le2i | fall | cleared | escalated |
| le2i_home-01_video-21 | le2i | fall | cleared | escalated |
| le2i_home-01_video-22 | le2i | fall | confirmed | escalated |
| le2i_home-01_video-26 | le2i | fall | escalated | cleared |
| le2i_home-02_video-32 | le2i | fall | escalated | cleared |
| le2i_home-02_video-33 | le2i | fall | escalated | cleared |
| le2i_home-02_video-34 | le2i | fall | escalated | cleared |
| le2i_home-02_video-37 | le2i | fall | escalated | cleared |
| le2i_home-02_video-40 | le2i | adl | escalated | cleared |
| le2i_home-02_video-41 | le2i | adl | escalated | cleared |
| le2i_home-02_video-43 | le2i | adl | cleared | escalated |
| le2i_home-02_video-47 | le2i | adl | cleared | escalated |
| le2i_home-02_video-52 | le2i | adl | escalated | cleared |
| le2i_home-02_video-53 | le2i | adl | escalated | cleared |
| le2i_home-02_video-55 | le2i | adl | escalated | cleared |
| le2i_home-02_video-57 | le2i | adl | escalated | cleared |
| le2i_home-02_video-59 | le2i | adl | escalated | cleared |
| le2i_home-02_video-60 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-02 | le2i | adl | confirmed | cleared |
| le2i_lecture-room_video-03 | le2i | adl | confirmed | cleared |
| le2i_lecture-room_video-05 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-06 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-07 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-08 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-09 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-10 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-13 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-14 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-15 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-16 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-18 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-19 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-20 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-21 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-23 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-24 | le2i | adl | escalated | cleared |
| le2i_lecture-room_video-26 | le2i | adl | escalated | cleared |
| le2i_office_video-01 | le2i | adl | escalated | cleared |
| le2i_office_video-02 | le2i | adl | escalated | cleared |
| le2i_office_video-03 | le2i | adl | escalated | cleared |
| le2i_office_video-05 | le2i | adl | escalated | cleared |
| le2i_office_video-06 | le2i | adl | confirmed | cleared |
| le2i_office_video-10 | le2i | adl | escalated | cleared |
| le2i_office_video-12 | le2i | adl | escalated | cleared |
| le2i_office_video-13 | le2i | adl | confirmed | cleared |
| le2i_office_video-14 | le2i | adl | escalated | cleared |
| le2i_office_video-16 | le2i | adl | escalated | cleared |
| le2i_office_video-18 | le2i | adl | escalated | cleared |
| le2i_office_video-29 | le2i | adl | escalated | cleared |
| upfall:S1:A11:T2 | up_fall | adl | cleared | escalated |
| upfall:S1:A11:T3 | up_fall | adl | cleared | escalated |
| upfall:S1:A1:T1 | up_fall | fall | confirmed | cleared |
| upfall:S1:A1:T2 | up_fall | fall | confirmed | cleared |
| upfall:S1:A1:T3 | up_fall | fall | confirmed | cleared |
| upfall:S1:A2:T1 | up_fall | fall | confirmed | escalated |
| upfall:S1:A2:T2 | up_fall | fall | escalated | cleared |
| upfall:S1:A2:T3 | up_fall | fall | confirmed | cleared |
| upfall:S1:A3:T2 | up_fall | fall | confirmed | cleared |
| upfall:S1:A3:T3 | up_fall | fall | escalated | cleared |
| upfall:S1:A4:T2 | up_fall | fall | escalated | cleared |
| upfall:S1:A4:T3 | up_fall | fall | confirmed | cleared |
| upfall:S1:A5:T1 | up_fall | fall | confirmed | cleared |
| upfall:S1:A5:T2 | up_fall | fall | escalated | cleared |
| upfall:S1:A5:T3 | up_fall | fall | escalated | cleared |
| upfall:S1:A8:T3 | up_fall | adl | cleared | escalated |
