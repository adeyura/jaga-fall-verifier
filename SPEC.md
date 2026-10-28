# Jaga evaluation spec — FROZEN 2026-10-27

This document is the contract the implementation is built to. It was
written before results existed and froze on 2026-10-27; the
decisions adopted at the freeze are recorded in DECISIONS.md. Any
change after the freeze is a dated commit with a stated reason. The
test set is run ONCE, after the freeze. All prompt and threshold
iteration happens on the dev split only.

## Datasets and scope

- Scope (decision D5): the headline datasets are UP-Fall and
  Le2i. UR Fall is per-view diagnostics only and is never pooled into
  headline numbers, because in UR Fall the class determines the
  camera. UP-Fall's two views of one event count as one sample.
- Accepted risk, stated plainly: decoded frame counts are reconciled
  against container duration with a tolerance of max(2 frames, 10%) as a
  variable-frame-rate allowance. A loss inside that tolerance could in
  principle hide a tail event; the checks refuse gross shortening, they
  do not guarantee frame-perfect decoding.
- UR Fall as distributed (verified 2026-10-27): falls are the CEILING
  camera (cam1) only, ADL the floor-parallel camera (cam0) only — a
  class-conditional camera confound. UR Fall results are reported with
  views stated and are never pooled with Le2i's room-corner views.
  Every file is a side-by-side composite: depth map (left 320x240) and
  RGB (right 320x240) in one 640x240 frame (visually verified
  2026-10-27). Preprocessing (decision P1, adopted): every UR
  Fall clip is cropped to its RGB half before any processing. The
  layout was verified by an automated per-file audit (70/70 files:
  the right half is markedly more colorful than the near-grayscale
  depth half), and gate recall was re-measured on the cropped signal
  (30/30 falls). On the composite, the depth half's speckle held the
  local-timing noise floor at 0.036-0.068; on the RGB half it is
  0.0001-0.041. A persistent ~150 px false-positive SAM instance (a
  ceiling fixture) appears in cam1 keyframes; instances under 1% of
  frame area are not treated as person evidence for phase decisions
  (measured: artifact ~150 px ≈ 0.2%, feet at entry ~510 px, fallen
  person ~5,000 px ≈ 6.5% at 320x240). Cam1 event structure: the subject
  enters from the frame's top edge and falls within about half a
  second, so pre-descent posture is unobservable by construction; no
  SAM prompt variant finds a standing person before entry because
  there is none in frame.
- Target frozen set: ~90 clips from UP-Fall and Le2i — falls plus
  ~12 per hard-negative category (fast sit-down, bend to pick up,
  crouch, intentional lie-down, stumble-and-recover), as the datasets'
  activity inventories allow. Existing dataset labels only.
- Stumble-and-recover barely exists in these datasets. Shortfall is reported,
  not papered over. Any self-recorded supplements are labeled as such and
  kept out of benchmark numbers.
- Datasets enter the repo as download scripts + clip manifest + checksums.
  No media files are ever committed.

## Splits

- Two-split protocol (D5): a dev split for all iteration, and a frozen
  test split that receives exactly ONE confirmation run after the
  freeze. Dev/test assignment is frozen in the manifest before the
  first scored run.
- Person/event independent where labels allow: frames or clips from the same
  recorded event never appear in both dev and test.
- UP-Fall's two camera views of one event count as ONE sample.
- Exception process: a genuine bug found during the confirmation run
  may be fixed and the run repeated, but every such exception is
  logged with the bug, the fix, and both runs' numbers.
- If the frozen test would fall under ~25 events, the split is
  abandoned and the full frozen set is run once instead (D5).

## Pipeline under test

- Motion gate (local frame differencing, consecutive + background channels)
  selects candidate segments, padded by the candidate window (-2 s / +4 s).
  **Gate parameters (src/jaga/config.py) are part of this frozen spec**;
  their hash is recorded in the results file and the manifest. Before the
  freeze, gate-only recall is measured on dev falls and must be ~100%: the
  gate may never silently cap end-to-end recall, and per-clip gate
  statistics (segments kept/dropped, seconds flagged, zero-candidate
  flags) are logged to the manifest for every clip.
- SAM 3.1 (Meta Model API) segments the person on keyframes sampled at
  2 fps (frozen; about $0.04 of SAM per candidate window at the
  per-image rate); masks are associated across frames locally by
  bounding-box IoU tracking (box IoU, not mask IoU — stated plainly).
- Mask-derived kinematics: bbox aspect ratio and elongation, mask
  area, centroid height/velocity, floor_proximity (mask bottom edge
  over frame height), bottom_band_share (share of mask pixels in the
  bottom band of the person's own mask), post-event stillness. There
  is no frame-relative "floor-contact area" measure; the earlier
  draft's phrase is retired.
- Descent timing is measured locally at native frame rate from the
  motion signal (timing.py): the descent duration is the interval's
  core duration (width at half the run's 90th-percentile peak), which
  excludes recovery tails merged into the same envelope run. The
  keyframe centroid path is a labeled fallback only: it can establish
  a fast downward step but leaves duration UNMEASURED, and a verdict
  resting on it caps at uncertain.
- Rules state machine, per camera view. Side view: upright → rapid
  descent → horizontal → stillness. Ceiling view (UR Fall's
  enter-and-fall construction only, decision P2): pre-descent
  posture is unobservable by construction; the post phases are
  person-sized mask presence and stillness; ceiling rules verdicts
  cap at uncertain and the adjudicator decides from the evidence
  pack. Safeguard composition (P3, mandatory): all phases are always
  evaluated, and an out-of-window descent yields a confident negative
  ONLY when another phase contradicts a fall; when the remaining
  evidence is fall-consistent or unmeasured, the verdict escalates to
  uncertain. Missing evidence is always distinct from contradictory
  evidence.
- Descent windows, frozen: side view core duration in [0.4, 1.0] s
  (carried from the design; to be checked against UP-Fall dev-split
  fall distributions before the confirmation run — any change is a
  dated amendment made before that run, with the test split
  untouched). Ceiling view [0.15, 1.35] s, derived 2026-10-27 from
  the full UR Fall cam1 diagnostics distribution on the cropped
  signal (n=27 falls with a detected descent, cores 0.17-1.27 s,
  median 0.57) with modest padding at both ends.
- Stillness, operationalized as implemented: an observed span of at
  least 2.5 s inside the 3 s window starting at the descent's end,
  no unobserved gap over 1.0 s, centroid displacement within the
  frozen threshold. A shorter observable span reads as unmeasured,
  never as motion.
- Candidate window: -2 s to +4 s around the event (the post-event segment is
  the most discriminative evidence). Tunable on dev only.
- Muse Spark adjudication (evidence form per D3): temporally ordered
  mask overlays over an aggressively blurred low-resolution
  background plus the numeric kinematic traces — never raw frames.
  The verdict must argue both sides (strongest fall case, strongest
  benign case, data-quality problems, the discriminating
  observation) and may escalate to uncertain. Temperature 0. The
  scored evidence form is chosen by an A/B/C comparison on the dev
  split at equal recall (overlays+traces vs traces-only vs the
  current frames+traces iteration form) and adopted by dated
  amendment before the gate run; dev iteration until then is
  explicitly not the scored form.

## Metrics (all reported, none cherry-picked)

- End-to-end event-level recall (not stage-wise).
- Precision at dataset prevalence AND false alarms per hour of
  everyday-activity footage.
- Per-category results for falls and each hard-negative category.
- Wilson score intervals on every reported proportion (D5).
- Cascade metrics are first-class (D5): gate recall and the SAM
  failure/anomaly rate are reported alongside end-to-end numbers, so
  a stage's losses are never hidden inside a later stage's score.
- Escalation rate (share of events whose final disposition is a human
  check rather than a confirmed verdict) and its cost, reported with
  the scored results (P3).
- Trivial baselines on the dev split (D5): an aspect-ratio-only
  classifier and a Spark-only classifier (no rules), so the pipeline
  must beat the cheap alternatives, not just a strawman.
- Adjudicator agreement rate: the adjudicator runs twice on the frozen set;
  agreement is reported (below 90% is a finding, not something to hide).
- Cost and latency per candidate clip, measured, including which SAM
  billing mode applies (video-frame vs per-image rate).
- At most four result artifacts (D5): the single results file, the
  manifest, the cascade summary, and the ablation table. No parallel
  spreadsheets of numbers.

## The ablation and the gate rule — ADOPTED (decision D1)

Rules-only vs rules + Muse adjudication, same frozen set, rules baseline
tuned honestly on dev first (beating a strawman proves nothing).

The gate is PAIRED and runs on the DEV split at about hour 36 of the
build: the same clips through both arms. The Spark stage is kept
only if ALL of the following hold:

1. Safety veto: zero additional missed falls versus rules-only. A
   fall counts as missed only when its final disposition clears it
   without escalation; an adjudicator "uncertain" escalates to a
   human check and is an alert, not a miss (and never a silent
   discard).
2. At least 40% relative AND at least 3 absolute fewer hard-negative
   false alarms than rules-only. A hard negative counts as cleared
   only on a "benign" verdict; "uncertain" escalations are reported
   as their own line, neither wins nor false alarms.
3. At least 95% of adjudications return usable structured verdicts.

If the gate fails, the project pivots to the fallback without
renegotiating the rule. The frozen test split then receives its one
confirmation run under whichever arm the gate selected.

## Hour-3 feasibility gate (measured, not argued)

A 10-second candidate clip must process end to end in <= 60 s wall-clock and
<= $0.05 marginal cost, with person masks usable for tracking, and the actual
SAM billing mode identified from the first calls. Fail: pivot with evidence.

## Alert policy — ADOPTED (decision D2)

Tiered ladder, built as working software: Urgent / Check now / No
immediate alert. Uncertainty escalates to a check, never to silence,
and a fail-safe alert fires when cloud verification is unavailable.
Acknowledgement and escalation (no acknowledgement within the window
→ next recipient) are part of the software. The consent layer (the
watched person chooses rooms, hours, recipients, retention) is a
clearly labeled design mock — "designed, not implemented" — and is
upgraded to a minimal working slice only if a full spare day remains
after the evaluation freezes.

## Adjudicator evidence — ADOPTED (decision D3)

One-shot adjudication with the evidence form specified under
"Pipeline under test" (overlays + traces, argue-both-sides,
escalation allowed). An evidence-gathering loop (the adjudicator
requesting denser frames or a second SAM look) is NOT built; it is
deferred explicitly, not silently dropped.

## Claim discipline

- Every public number traces to the single results file in results/.
- Limitations stated wherever numbers appear: staged falls by young actors
  in lab rooms; dataset performance is not deployment performance.
- No deployment claim. No medical framing. The system is a verifier and a
  response workflow, never a medical device.

## Freeze record (2026-10-27)

Settled by this freeze: keyframe rate 2 fps; descent from dense local
timing (core duration) with a labeled keyframe fallback; stillness as
operationalized above; measures renamed honestly (floor_proximity,
bottom_band_share, mask area; no floor-contact area); association is
box IoU; UR Fall composites cropped to the RGB half (P1) with the
layout audit and gate re-measurement as conditions, both satisfied;
the per-view evidence model with the ceiling construction and the P3
safeguard composition (P2/P3); ceiling descent window derived from
the full cam1 diagnostics distribution; datasets and splits per D5;
metrics per D5; the gate rule (D1); the alert ladder (D2); the
adjudicator evidence form and its dev A/B/C selection (D3).

Still open, all pre-gate and none blocking the freeze: the Le2i
license (author's signature); the UP-Fall dev-split side-view fall
distribution check against the [0.4, 1.0] s window; the D3 evidence
A/B/C on dev; dev/test split assignment in the manifest; the D2
alert-ladder build; the SAM raster path the overlay evidence form
needs; the outstanding re-verification of the parse/features unit.

## Amendment 2026-10-27 (later): D3 scored evidence form adopted

The D3 A/B/C comparison ran on the UR Fall dev shakedown set (6 ceiling falls, 6 side-view ADL; every fall escalated to the adjudicator by the ceiling cap; 2 ADL escalations adjudicated). Adjudicator outcomes (usable 8/8 in every form; no fall called benign in any form):

- overlay (masks over blurred backgrounds + traces): falls 0 confirmed / 6 uncertain; ADL escalations 2/2 benign.
- raw frames + traces: falls 3 confirmed / 3 uncertain; ADL escalations 2/2 benign.
- traces only (no images): falls 3 confirmed / 3 uncertain; ADL escalations 2/2 benign.

Recall to a human (fall or uncertain, the D1 not-missed definition) is identical across forms. Images added nothing over traces on this evidence, and the overlay form confirmed nothing: from a ceiling view, a mask silhouette over a blurred background carries too little posture information for the adjudicator to commit. ADOPTED: the scored evidence form is **traces only** (form C). It ties the best confirmation rate, and it is the strongest privacy form of the three — no image data of any kind leaves the machine in the evidence pack. The overlay form remains implemented and recorded as a non-scored form.

Obligation carried forward: this set contains no side-view falls (UR Fall's confound). The A/B/C must be re-run on the UP-Fall dev split when it exists; if overlays confirm side-view falls materially better than traces there, a further dated amendment may adopt a per-view scored form before the gate run. The D1 gate runs under the form in force at that time, recorded on every result.

## Amendment 2026-10-28: P3 side-view descent window — lower bound 0.4 s → 0.15 s

The frozen text scheduled this check: the side-view window was "to be checked against UP-Fall dev-split fall distributions before the confirmation run — any change is a dated amendment made before that run, with the test split untouched." The check ran on dev data only: the UP-Fall Subject 1 fall timing measurement (2026-10-28), and the dev core measurements of the same date (Le2i-dev falls; UP-Fall Subject 1 hard negatives). The test split is untouched. ADOPTED: the side-view descent window is **[0.15, 1.0] s**. The upper bound is unchanged; the ceiling window [0.15, 1.35] s is untouched.

Derivation: the lower bound sits just below the minimum reliably descent-selected dev fall core (0.17 s, UP-Fall Subject 1) and equals the timing stage's existing lower selection bound (TIMING min_duration_s = 0.15 s). Timing-module fallback rows (cores 0.10-0.13 s) were excluded from fitting as measurement artifacts: a fallback value is what the timing module reports when it finds no qualifying interval, not a clean descent measurement.

Evidence (dev only):

- UP-Fall Subject 1 falls: reliably descent-selected cores span 0.17-0.63 s, median 0.30 s (23 of 30 clips; the other 7 are fallback rows). Under the old window 7/30 clips were in-window; under the amended window 23/30 are — the exclusions are exactly the fallback artifacts.
- Le2i-dev falls: median core 0.73 s, tail to 1.73 s (83 measured; 70 in-window under the amended bounds, 12 above 1.0 s, 1 fallback row). Falls above 1.0 s are not cleared by this window: they escalate via the P3 safeguard composition and are reported in the escalation rate, not as cleared negatives.
- Dev hard negatives (UP-Fall Subject 1 ADL): 9 of 18 clips produced no timing interval at all, including 5 of the 6 lie-down views, and the measured cores overlap the fall range. The window is therefore a calibration bound, not the discrimination mechanism; the posture and stillness phases carry the discrimination.

Basis: amend the lower bound only, and only after measurement (2026-10-28); the dev core measurement satisfied the measure-first condition.

Limitation, stated: descent-core distributions are dataset-dependent (UP-Fall fall median 0.30 s vs Le2i 0.73 s). The amended window covers the union of the dev evidence; confirmation reporting stays stratified by dataset, and a divergent confirmation distribution is reported, not re-tuned against.

Gate parameters: this changes src/jaga/config.py (RULES descent_min_s 0.4 → 0.15). config_hash d940d0c26c123909 → 6d7c03257b12ab00, recorded here; scored runs continue to stamp the hash they ran under.
