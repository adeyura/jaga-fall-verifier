# Jaga evaluation spec (DRAFT — freezes when the author approves it)

This document is the contract the implementation is built to. It is written
before results exist. Any change after the freeze is a dated commit with a
stated reason. The test set is run ONCE, after the freeze. All prompt and
threshold iteration happens on the dev split only.

## Datasets and scope

- Gate scope: UR Fall + Le2i. UP-Fall joins only after the gate decision.
- UR Fall as distributed (verified 2026-10-27): falls are the CEILING
  camera (cam1) only, ADL the floor-parallel camera (cam0) only — a
  class-conditional camera confound. UR Fall results are reported with
  views stated and are never pooled with Le2i's room-corner views.
- Target frozen set: ~90 clips — 30 falls, ~12 per hard-negative category
  (fast sit-down, bend to pick up, crouch, intentional lie-down,
  stumble-and-recover). Existing dataset labels only.
- Stumble-and-recover barely exists in these datasets. Shortfall is reported,
  not papered over. Any self-recorded supplements are labeled as such and
  kept out of benchmark numbers.
- Datasets enter the repo as download scripts + clip manifest + checksums.
  No media files are ever committed.

## Splits

- Dev/test split frozen in the manifest before the first scored run.
- Person/event independent where labels allow: frames or clips from the same
  recorded event never appear in both dev and test.
- UP-Fall's two camera views of one event count as ONE sample.

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
  3–5 fps; masks are associated across frames locally (IoU tracking).
- Mask-derived kinematics: bbox aspect ratio, centroid height/velocity,
  floor-contact area, post-event stillness.
- Rules state machine: upright → rapid descent (0.4–1.0 s) → horizontal →
  stillness >= 3 s. Tuned on DEV for ~100% fall recall; precision is the
  adjudicator's job.
- Candidate window: -2 s to +4 s around the event (the post-event segment is
  the most discriminative evidence). Tunable on dev only.
- Muse Spark adjudication: 6–10 non-uniformly sampled frames (sparse
  context, dense descent, 2–3 stillness frames), full frame plus one zoomed
  person crop, numeric kinematic traces included as text. Structured output
  (verdict, confidence, rationale), temperature 0, decision threshold frozen
  on dev.

## Metrics (all reported, none cherry-picked)

- End-to-end event-level recall (not stage-wise).
- Precision at dataset prevalence AND false alarms per hour of
  everyday-activity footage.
- Per-category results for falls and each hard-negative category.
- Adjudicator agreement rate: the adjudicator runs twice on the frozen set;
  agreement is reported (below 90% is a finding, not something to hide).
- Cost and latency per candidate clip, measured, including which SAM
  billing mode applies (video-frame vs per-image rate).

## The ablation and the gate rule — DECISION NEEDED (author)

Rules-only vs rules + Muse adjudication, same frozen set, rules baseline
tuned honestly on dev first (beating a strawman proves nothing).
Three positions are on the table:

1. Author's original: pivot to the fallback unless Muse clearly wins.
2. Pivot only if the Muse stage actively hurts (recall drop or
   added false alarms); a tie keeps Jaga.
3. Proceed iff Muse cuts false alarms by >= 40–50% relative at zero
   recall loss on the frozen test set, the rule written here before the
   first run, decision by hour ~36.

## Hour-3 feasibility gate (measured, not argued)

A 10-second candidate clip must process end to end in <= 60 s wall-clock and
<= $0.05 marginal cost, with person masks usable for tracking, and the actual
SAM billing mode identified from the first calls. Fail: pivot with evidence.

## Alert policy — DECISION NEEDED (author)

Binary (alert only on verified) vs tiered ladder:
urgent / check-now / log-only, where uncertainty escalates to a human check
instead of defaulting to silence, plus a fail-safe alert when cloud
verification is unavailable. (Recommendation: tiered.)

## Adjudicator evidence loop — DECISION NEEDED (author)

One-shot adjudication vs an evidence-gathering loop (the adjudicator may
request denser frames or a second, wider SAM look before deciding).
(Positions: build it; or one-sentence reframe only, spend no hours.)

## Claim discipline

- Every public number traces to the single results file in results/.
- Limitations stated wherever numbers appear: staged falls by young actors
  in lab rooms; dataset performance is not deployment performance.
- No deployment claim. No medical framing. The system is a verifier and a
  response workflow, never a medical device.
