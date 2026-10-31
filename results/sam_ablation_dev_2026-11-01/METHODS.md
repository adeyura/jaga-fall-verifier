# Post-hoc supplementary SAM ablation on the dev set — METHODS

Written 2026-11-01, before the run. This document defines the no-SAM arm
exactly as it was implemented. The driver is `run_nosam.py` in this
directory; per-event output is `nosam_dev_dispositions.csv`; the joined
comparison is `comparison.md`.

## Question

The D1 gate compared rules+SAM against rules+SAM+LLM. SAM evidence was
present in both arms, so the gate design cannot say whether SAM evidence
changes any disposition. This analysis asks that narrower question on
the dev set: holding the gate, the timing stage, the rules' thresholds,
and the scoring conventions fixed, what changes when the SAM-derived
evidence is removed and only motion-signal evidence remains?

## What "the shipped arm" means here

The comparator is the gate record itself: `results/gate_d1_dev_results.csv`,
column `rules_disposition` (event level, config hash `6d7c03257b12ab00`,
evidence form: traces). No SAM call is re-run and no shipped number is
recomputed. The join is on `event_id`, using the gate's own event
construction: a Le2i event is its clip; a UP-Fall event is
`upfall:S{subject}:A{activity}:T{trial}` (its two camera clips).

## The no-SAM arm, stage by stage

Identical to the shipped pipeline wherever the stage never used SAM:

1. **Motion gate** — `jaga.motion_gate.gate_clip`, unchanged. Same
   segments, same gate misses, by construction.
2. **Descent timing** — `jaga.timing.timing_from_video` (series +
   analyze), unchanged. Timing is computed from the frame-difference
   signal and never used SAM in the shipped pipeline either.
3. **Rules** — the shipped rules consume four phases per candidate
   descent window. In the no-SAM arm each phase is handled as follows:

   | Phase | Shipped evidence | No-SAM treatment |
   |---|---|---|
   | descent | core duration of a local timing interval (motion signal), or a SAM-centroid-velocity fallback | local timing intervals only — **identical where a local interval exists**; the keyframe fallback is SAM-derived and is removed |
   | pre_posture | majority mask posture (elongation + principal-axis tilt) before the descent | **evidence-absent (None)** — no motion-signal equivalent exists |
   | post_posture | majority mask posture after the descent | **evidence-absent (None)** — same |
   | stillness | SAM centroid displacement ≤ 0.03 frame heights over the 3 s window after the descent | **motion-energy equivalent** (defined below) |

   Ceiling-view phases (person-sized mask area) are SAM-derived and
   likewise evidence-absent; no dev clip is scored under the ceiling
   model anyway (the gate driver mapped every dev row to the side
   model, and this arm does the same).

4. **Window set** — per gate segment, the candidate windows are the
   clip's local timing intervals overlapping the observation span,
   using the shipped overlap test and 1.0 s slack. One substitution:
   the shipped span is the SAM track's keyframe span; the no-SAM span
   is the gate segment's span (there are no tracks). An interval whose
   core is not contained in the span is flagged `admitted_on_slack`,
   as in the shipped code.
5. **Stillness, motion form** — from the same 30 fps series the timing
   stage produces: let `af` be the changed-area fraction, smoothed
   exactly as `timing.analyze` smooths it, and let `low = floor +
   burst_low_frac * (p95 - floor)` be the clip's own activity level —
   the hysteresis level `timing.analyze` itself uses to delimit
   bursts (all values from the frozen TIMING config; no new threshold
   was fitted). Over the shipped stillness window
   `[core_offset, core_offset + 3.0 s]`, stillness is satisfied iff
   the smoothed `af` never exceeds `low` at any step in the window.
   It is unmeasurable (None) iff less than `stillness_min_span_s`
   (2.5 s) of series remains in the window — the same minimum-span
   rule the shipped measure applies. The shipped maximum-gap rule has
   no analog: the motion series is dense, every step is observed.
6. **Composition** — the shipped `_evaluate_window` logic with
   pre/post posture fixed at None:
   - descent measured outside [0.15, 1.0] s: negative iff another
     phase contradicts (only stillness can), otherwise uncertain;
   - descent in window: negative iff stillness contradicts ("person
     moved after the descent"); otherwise uncertain, because the
     posture phases are unmeasured;
   - **fall_candidate is unreachable in this arm by construction**:
     confirmation requires both posture phases satisfied, and posture
     is SAM evidence. The arm can escalate or clear; it can never
     confirm. This is a property of the definition, stated here so the
     confirmed-falls delta is read correctly: it measures what
     confirmation costs, not a tuning failure.
   - Windows within a segment are ranked exactly as the shipped code
     ranks them (label order, slack admission, progress).
   - A segment with no overlapping local interval takes the shipped
     no-descent branch's posture-unmeasurable outcome: **uncertain**
     ("descent unobserved and posture unmeasurable"). The SAM
     keyframe fallback and the upright-to-horizontal transition test
     are both SAM-derived and are absent.
   - The shipped `no_evidence` outcome (a segment whose SAM tracks
     were unusable) has no analog: with no SAM stage to return
     nothing, every gated segment yields uncertain or negative.
7. **Scoring** — the gate's frozen conventions, copied from
   `scripts/analyze_gate_d1_dev.py`: segment label → disposition
   (fall_candidate → confirmed, uncertain/no_evidence → escalated,
   negative → cleared); clip disposition is the most protective
   segment disposition; a clip with no gate segments is `gate_miss`;
   a clip whose video fails to process is `pipeline_error`; event
   disposition is the most protective across the event's clips
   (confirmed > escalated > pipeline_error > cleared > gate_miss).

## Known asymmetries (read the deltas with these in hand)

- **Confirmation is impossible without SAM** (above). Falls confirmed
  drops to zero structurally; the informative fall deltas are
  not-missed, escalated, and cleared.
- **Windows are tried against the segment span, not a track span.**
  A timing interval the shipped arm never tried (because no SAM track
  overlapped it) can be tried here, and vice versa. This can move a
  verdict in either direction on individual events.
- **Motion stillness is measurable more often** than SAM stillness
  (dense 30 fps series vs 2 fps keyframes with span/gap rules), and it
  measures a different physical quantity: changed area, not centroid
  displacement. A person who is centroid-still but fidgeting, or
  off-centroid but area-active, reads differently in the two arms.
- **No fallback descent.** Events the shipped arm escalated via the
  SAM keyframe fallback (a fast centroid drop with no local interval)
  take the no-descent branch here. Both paths escalate, so this
  asymmetry is mostly invisible at disposition level.
- **No no_evidence path.** A shipped segment that escalated because
  SAM returned nothing usable escalates here only via the
  no-descent/uncertain routes; a shipped segment cleared on a
  bystander track's negative has no counterpart distinction here.

## Caveats that must travel with any published number from this run

1. **Post-hoc.** The arm was defined on 2026-11-01, after the gate,
   the pivot, and the confirmation run were all known. It is a
   supplementary diagnostic, not a pre-registered comparison, and
   must always be described as post-hoc and supplementary.
2. **Dev is the design set.** The rules' thresholds were tuned on
   these clips. Absolute dev numbers are optimistic for BOTH arms;
   only the within-dev delta between arms is informative, and even it
   is a dev-set quantity.
3. **The frozen test was not touched** — not run, not read for
   scoring. The sealed subjects 3–5 were not touched. Headline
   numbers (confirmation run) are unchanged by this analysis.
4. **Zero SAM calls were made.** The shipped arm is the recorded gate
   output; the no-SAM arm needs no SAM by construction.
5. The no-SAM arm is a *counterfactual construction*, not a product:
   nobody proposes shipping a verifier that cannot confirm. Its
   purpose is attribution — which dispositions SAM evidence is
   carrying.
