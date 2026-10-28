# Visual audit of gate-discordant dev cases — 2026-10-29

Purpose: eyeball the actual footage behind the D1 gate cases where the arms
disagreed with each other or with the dataset label, to catch dataset label
errors and characterize failure modes. **This audit changes no score and no
verdict. The frozen gate results stand regardless of anything below; every
judgment here is an audit observation, not a rescoring.**

Scope: dev split only. No test-split, Subject 2, or Coffee_room_02 content
was opened. Method: frames extracted with ffmpeg into
`cache/visual_audit/<case>/` and assembled into labeled contact sheets;
each case below was viewed directly. Frame timestamps are seconds into the
clip. Sources: `results/gate_d1_dev_discordants.csv`,
`results/gate_d1_dev_results.csv`, per-clip gate records in
`cache/gate_d1/main/`, `results/dev_core_measurements.csv`,
`results/up_fall_s1_fall_timing.csv`, `results/le2i_manifest.csv`.

16 events audited. Label judgments: **label-supported 11, label-doubtful 5,
cannot-tell 0.**

## Subset 1 — the 4 "false alarms" (ADL label, both scoring arms confirmed a fall)

Standing context for all four: the Lecture room and Office clips carry no
per-clip annotation in the dataset as shipped; their ADL labels were
inferred from the room layout when the manifest was built (see
`results/le2i_manifest.csv` notes). All four rooms have a crash mat
pre-positioned on the floor, visible from the first frame.

### le2i_lecture-room_video-02 (rules descent 15.07–15.63 s)
Corner view of a lecture room; a crash mat lies mid-room throughout. The man
stands by the table at 13.8 s, is captured mid-descent toward the mat at
15.2 s, and from 16.3 s to the end of the clip lies prone across the mat,
motionless. The movement that "mimics" a fall is not a mimic: it is a rapid
descent from standing to prone on the mat followed by sustained stillness,
structurally identical to the annotated fall trials in the Coffee and Home
rooms.
**Judgment: label-doubtful.** The ADL label rests on room-level inference,
and the footage shows the dataset's fall protocol, not an everyday activity.

### le2i_lecture-room_video-03 (rules descent 19.53–19.83 s)
Same room and mat. The man walks mid-room at 17.8 s, is already horizontal
and rolling across the mat at 19.6 s, and lies on the mat and floor,
motionless, from 20.7 s to the end at 24.6 s. Again a staged descent onto
the crash mat with a post-fall lying phase, matching the fall pattern the
adjudicator described (abrupt tilt collapse, then near-zero motion).
**Judgment: label-doubtful**, on the same grounds as video-02.

### le2i_office_video-06 (rules descent 12.53–13.10 s)
Office view, crash mat center-frame. The man stands bent slightly beside
the mat at 11.2 s, is blurred mid-drop onto it at 12.8 s, and lies on his
back across the mat from 13.9 s to the end, one arm raised then resting. A
fast backward/sideways descent onto the mat followed by sustained lying —
the fall protocol again, not office ADL.
**Judgment: label-doubtful.**

### le2i_office_video-13 (rules descent 26.33–27.07 s)
Same office. The man sits on the chair at 24.8 s, walks (motion-blurred) at
26.6 s, and is lying prone on the mat at 27.7 s, remaining prone and still
through the end at 31.4 s. Between the walking frame and the next he goes
from upright gait to prone on the mat inside the rules' fired window.
**Judgment: label-doubtful.**

## Subset 2 — the motion-gate-missed fall

### le2i_home-01_video-16 (label: fall, frames 186–199 ≈ 7.75–8.29 s; gate: 0 segments kept)
Dim living room from a high corner camera. The man sits at the left beside
a sofa at 0.5 s, leans forward over a floor mat at 4.0 s, is bent double
over the mat at 7.0–7.8 s, and is lying prone on it at 8.3 s, remaining
lying through the end. A fall does visibly occur inside the labeled
interval: he sinks from a bent-over posture to fully prone. The descent is
slow and low-amplitude — it starts from a crouch rather than standing
height, the silhouette is small and dark in a dim room, the dining table
and chair partially occlude him, and the motion blends into the preceding
lean-forward; the gate record shows the one motion run was dropped as too
short.
**Judgment: label-supported.** A genuine, if gentle, fall; the miss is a
motion-gate sensitivity limit, not a label error.

## Subset 3 — sample of the 27 falls both arms cleared

Selection: the 6 events with the shortest measured descent cores across
both datasets (event ranked by its shortest clip core; ties included in
rank order). Next in line were the 0.47 s events. Fallback rows — where the
timing module found no qualifying descent and recorded its strongest
interval instead — are flagged; two of the six are fallback cases.

### le2i_coffee-room-01_video-30 — core 0.10 s (fallback row)
Coffee room, mat center-frame. The man walks to the mat (2.7 s), sits on
its edge with legs stretched on the floor at 3.4 s, and from 4.0 s to the
end kneels and crouches over the mat, hands on it, still active. The
labeled fall interval (frames 80–104 ≈ 3.2–4.2 s) covers the sit-down.
He never becomes horizontal and never lies still.
**Judgment: label-doubtful.** What visibly occurs is a controlled sit onto
the mat edge followed by kneeling — no fall. Consistent with the timing
module finding no genuine descent in this clip.

### upfall:S1:A3:T1 — cores 0.13 s (Camera 1, fallback row) / 0.17 s (Camera 2)
Side view (Camera 1): the man stands beside the mattress at 0.4 s, is
falling onto it with legs swinging up at 1.8 s, lies on his back with legs
in the air at 2.4 s, and lies flat and still from 3.2 s to the end. The
frontal view (Camera 2) shows the same: standing, then supine on the
mattress with legs vertical at 2.0–2.6 s, then flat. An unambiguous fall
onto the mattress inside the first three seconds.
**Judgment: label-supported.** The pipeline miss is mechanical: a rotating,
leg-swing descent, landing on a raised mattress, with the subject low and
partly cropped at the frame's bottom edge in Camera 1 afterward.

### le2i_coffee-room-01_video-44 — core 0.30 s
The man stands beside the mat (0.4–1.7 s), is caught blurred and rotating
backward onto it at 2.5 s, and lies flat on his back on the mat from 3.3 s
to the end, arms crossed. The labeled interval (frames 54–86 ≈ 2.2–3.4 s)
brackets the descent exactly.
**Judgment: label-supported.** A clean backward fall; clearing it is a
plain pipeline miss with no label ambiguity.

### upfall:S1:A4:T1 — cores 0.30 s / 0.30 s
Camera 1: the man stands at the mattress edge (0.25–0.7 s), is lying
sideways across the mattress at 1.3 s, and lies still, half-cropped at the
bottom-left of the frame, from 2.2 s to the end. The fall completes between
0.7 and 1.3 s, matching the measured onsets (0.50 / 0.70 s). After the
fall the subject sits at the very edge of the frame, which thins the pose
evidence available to either arm.
**Judgment: label-supported.**

### le2i_coffee-room-01_video-07 — core 0.43 s
A woman walks in (0.4–3.3 s), kneels upright beside the mat with her hands
on it at 4.2 s, and from 5.0 s to the end lies curled on her side across
the mat, head off its end, motionless. The labeled interval (frames
96–126 ≈ 3.8–5.0 s) covers the kneel-to-lying transition. A descent to a
sustained lying position does occur in the labeled window, but it is
staged through a kneeling intermediate rather than a collapse, which is
why a descent-driven rule set can clear it.
**Judgment: label-supported**, with the note that this is a low-energy,
two-stage descent — a hard case by construction, not a mislabeled one.

### le2i_coffee-room-01_video-15 — core 0.43 s
The man stands facing away (0.4–1.5 s), bends forward with hands reaching
toward the mat at 2.2 s, and lies face-down lengthwise on the mat from
2.9 s to the end. The labeled interval (frames 48–73 ≈ 1.9–2.9 s) covers
the bend-to-prone transition. The descent starts from a bent-over reach,
so it is low and forward, but it ends fully prone and still.
**Judgment: label-supported.**

## Subset 4 — the 5 arm-disagreement events (characterization)

All five are labeled falls and all five visibly are falls
(label-supported in each case). The disagreements share a shape: the
descent contains an intermediate posture or an ambiguous landing surface,
so the phase rules and the trace-reading adjudicator weigh the same
footage differently.

### le2i_coffee-room-01_video-27 — rules confirmed → full escalated
The man sits drinking on the bench (0.5 s), stands bent forward at 5.7 s,
lunges forward at 6.5 s with a hand planted on the mat, and ends lying
with his torso on the mat and legs extended on the floor (7.3 s to end).
The forward pitch is broken by a hand-plant mid-descent, and the final
position straddles mat and floor — exactly the floor-contact ambiguity the
adjudicator's own discriminator cites for its "uncertain." The flip is
traceable to a hand-braked descent onto a split landing surface.

### upfall:S1:A1:T1 — rules confirmed → full escalated
Forward fall in two stages: the man leans forward with arms extended at
3.4 s, lands on hands and knees on the mattress at 4.2 s, and only then
lowers to prone, lying still from 6.0 s to the end. The arm-braked catch
phase makes the second half of the descent read as controlled lowering,
which is what the adjudicator hesitated over; the rules fired on the
initial pitch (onset 3.17 s, core 0.30 s).

### upfall:S1:A1:T2 — rules confirmed → full escalated
A fast, clean forward fall: standing at 0.5 s, already prone on the
mattress at 1.9 s, lying still to the end. Nothing in the action is
ambiguous; what is thin is the evidence geometry — the subject lands low
in the frame and lies partly cropped at the bottom-left edge from 1.9 s
onward. This flip reads as weak pose evidence at the frame edge rather
than a genuinely borderline movement.

### upfall:S1:A3:T2 — rules confirmed → full escalated
The descent passes through a distinct seated intermediate: the man sits on
the mattress edge, hand planted, at 1.4 s, then rolls backward to supine
with legs kicked up at 2.2 s, lying flat thereafter. The sit-then-roll
staging gives the adjudicator a "controlled sit, then lie" reading to
weigh against the rules' descent detection (onset 1.00 s, core 0.47 s).

### upfall:S1:A5:T2 — rules escalated → full confirmed (the reverse flip)
Both cameras show the same trajectory: standing (0.2–0.6 s), bending and
sitting toward the mattress (1.2–1.5 s), then supine on the mattress with
knees bent and arms raised at 2.2 s, lying flat and still to the end.
Activity 5 is a fall that begins as a sit-down; the seated intermediate
interrupts the rules' descent-to-horizontal phase chain (hence escalate),
while the adjudicator, reading the traces as one continuous event ending
horizontal and still, confirmed. The disagreement is the mirror image of
A3:T2: same staged shape, opposite arm persuaded.

## Closing summary (audit observations only)

Across the 16 audited events: **11 label-supported, 5 label-doubtful,
0 cannot-tell.**

- All 5 doubtful labels sit in the ADL stratum, and 4 of the 5 are the
  gate's four "false alarms." Every one of those four clips shows a staged
  descent onto a pre-positioned crash mat followed by sustained lying —
  the dataset's fall protocol — under an ADL label that was inferred from
  the room, because the Lecture room and Office zips ship no annotation
  files. As an observation: the dev hard-negative pool's Lecture/Office
  stratum appears contaminated with genuine fall trials, which inflates
  the measured false-alarm counts for every arm. The frozen numbers are
  not changed by this observation.
- The fifth doubtful label is a fall label (coffee-room-01 video-30)
  where the footage shows a controlled sit and kneel, and no fall; it is
  also the clip where the timing module independently found no genuine
  descent (fallback row).
- The remaining cleared falls in the sample (5 of 6) are genuine falls.
  Their misses share mechanics rather than label problems: rotating or
  leg-swing descents, descents staged through kneeling or sitting
  intermediates, hand-braked forward falls, and landings at the frame edge
  or split between mat and floor.
- The gate-missed fall (home-01 video-16) is genuine: a slow, low,
  partially occluded sink in a dim room — a sensitivity limit of the
  motion gate.
- The five arm disagreements are all genuine falls whose descents are
  staged or split (hand-plant, sit-then-roll, mat/floor straddle), plus
  one clean fall (A1:T2) whose subject lands cropped at the frame edge.
  The two arms diverge exactly where a descent has an intermediate posture
  or an ambiguous floor contact, and in both directions (4 escalations
  against the rules, 1 confirmation against them).
