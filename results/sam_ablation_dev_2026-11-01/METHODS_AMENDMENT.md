# Amendment to METHODS.md — 2026-11-01, after the v1 run, before any publication

The original METHODS.md text stands as written; this amendment is a
separate dated document (not a silent edit) and supersedes exactly one
element of it: the stillness definition (stage 3, item 5). Everything
else in the arm is unchanged.

## What v1 did

As defined and run, motion stillness was anchored at the descent
**core** offset — the shipped code's anchor — and read satisfied iff
the smoothed changed-area fraction never exceeded the clip's activity
level at any step of the 3 s window. V1 results are preserved
(`nosam_dev_dispositions_v1.csv`, `comparison_v1.md`): falls
not-missed 22/99 vs 71/99 shipped;
falls cleared 76/99 vs 27/99.

## The defect found in v1, from recorded data

The anchor does not survive the change of measure. The shipped
stillness reads a **position** trace (mask centroid), which is settled
by the core offset. The motion series is a **change** trace: by
construction of the timing hysteresis, the envelope run continues past
the core offset (the core is the width at half prominence; the run
ends only when the envelope falls to the low level), so the first
steps of a core-anchored window are the descent's own tail and exceed
the activity level essentially whenever a tail exists. V1 therefore
measured, in part, "the descent had a tail" — a property of nearly
every descent — and booked it as "person moved after the descent".

Concrete instance (event `le2i_coffee-room-01_video-02`, a fall the
shipped arm confirmed): the confirming window's descent run is
7.10–8.43 s (core 7.67–8.23 s). The shipped stillness over
[8.23, 11.23] read displacement 0.0046 frame heights — the person
essentially motionless. The v1 motion reading over the same window
peaked at 0.0291 against a low level of 0.0115, concentrated at
8.23–8.6 s (the run tail and immediate settling); by 9.23 s the
changed-area fraction is 0.0005. The tail, not post-descent movement,
produced the contradiction that cleared the event in v1.

## The corrected definition (v2, the arm of record)

The descent, in the motion signal's own terms, is the whole envelope
run. The stillness window is therefore anchored at the **run offset**
— the moment the motion signal itself says the descent ended — and
"the person moved after the descent" is read with the same frozen
hysteresis that defines descents in the first place:

> Stillness over `[run_offset, run_offset + 3.0 s]` is satisfied iff
> no timing interval begins inside the window; unmeasurable (None)
> iff less than `stillness_min_span_s` (2.5 s) of series remains in
> the window; otherwise unsatisfied.

A person who gets up, walks, or falls again inside the window starts
a new burst and fails the phase; sub-burst settling does not. Every
constant involved is a frozen TIMING/RULES/FEATURES value; no
threshold was fitted. (In the worked-example clip above, no interval
begins in [8.43, 11.43], so v2 reads stillness satisfied, agreeing
with the shipped displacement reading.)

Two intermediate readings are computed and stored per window for a
sensitivity appendix, so the construction-dependence is itself a
reported number, not a hidden choice:

- **v1**: core anchor, any step above the activity level (the
  original definition; preserved in full).
- **v2a**: run anchor, any step above the activity level (isolates
  the anchor change alone).
- **v2 (arm of record)**: run anchor, new-burst rule (above).

## What did not change

Gate, timing, descent phase, posture-as-absent, window set,
composition logic, scoring conventions, event construction — all as
in METHODS.md. The multi-track point is also recorded here for the
interpretation: the shipped arm merges verdicts across every SAM
track in a segment (a fragmented or bystander track can carry the
most protective verdict), while the no-SAM arm evaluates one
candidate per segment; this asymmetry is intrinsic to removing the
tracker and is part of what "no SAM" means in this pipeline.

## Why report all three readings

The spread across v1 / v2a / v2 is the honest answer to "how much of
the delta is the evidence, and how much is the construction of the
counterfactual?" The headline claims in comparison.md are made only
where they hold across the corrected definition, and the appendix
shows the full sensitivity.
