# Worked example — one event, both arms, fully traced

**Event:** `le2i_coffee-room-01_video-02`
**Dataset / stratum:** Le2i, Coffee_room_01 (dev split, side view)
**Label:** fall. Single-clip event; the clip is 12.24 s and the motion
gate produced one segment spanning 0.0–12.24 s.
**Dispositions:** shipped rules+SAM arm — **confirmed**.
No-SAM arm (v2, arm of record) — **escalated**.
(Under the v1/v2a stillness readings the no-SAM arm clears this event;
see the last section. The spread is the appendix sensitivity in
miniature, and it is reported rather than smoothed over.)

Sources: shipped side — the gate's per-clip record
(`cache/gate_d1/main/le2i_coffee-room-01_video-02.json`, config hash
`6d7c03257b12ab00`) and `results/gate_d1_dev_results.csv`. No-SAM
side — `clip_record/le2i_coffee-room-01_video-02.json` in this
directory. Nothing below is reconstructed; every number is read from
one of those records.

## The shared evidence (identical in both arms)

Both arms run the same motion gate and the same local timing. The
winning descent window is the same interval in both: envelope run
7.10–8.43 s, core 7.67–8.23 s, **core duration 0.57 s**, inside the
side-view descent window [0.15, 1.0] s. Descent phase: satisfied,
identically, from the motion signal alone.

## What the motion signal alone says (no-SAM arm)

- Descent: a 0.57 s core — a fall-shaped burst, satisfied.
- Post-descent motion: no new timing interval begins in the 3 s
  after the run ends ([8.43, 11.43]) — under the v2 reading, stillness
  satisfied. (The changed-area trace agrees the clip goes quiet: by
  9.23 s the changed-area fraction is 0.0005.)
- Posture: **nothing**. The motion signal contains no measurement of
  the person's orientation before or after the descent.

Composition, with the posture phases evidence-absent: "fall-consistent,
but unmeasured: pre_posture, post_posture" → **uncertain → escalated**.
That is the ceiling of what motion evidence can say about this event:
something fell-shaped happened and nothing contradicts it, so a human
should look.

## The SAM-derived feature the decisive rule reads

The shipped verdict's winning track record shows all four phases
satisfied, and the phase that exists only because of SAM is
**post_posture**: the principal-axis tilt of the person's mask
(`axis_tilt_deg`, gated by `elongation` ≥ 1.2) classifies the
post-descent keyframes as **horizontal on 7 of 7 classified keyframes**
(tilt ≤ 35°), against **upright on 16 of 16** classified keyframes
before the descent (tilt ≥ 55°). Stillness in the shipped arm is the
centroid form of the same evidence: mask-centroid displacement
0.0046 frame heights over the window, under the 0.03 ceiling.

The composition rule is mechanical: fall_candidate requires descent
+ upright-before + horizontal-after + stillness, all measured. Both
posture phases are SAM-derived inputs with no motion counterpart —
the upright reading before the descent (pre_posture) as well as the
tilt-derived horizontal reading after it (post_posture) — and it is
the absence of both phases, not of the horizontal reading alone,
that makes the difference between the two dispositions on this
event: with them, **confirmed**; without them, the verdict caps at
uncertain and the event **escalates**.

## The sensitivity, stated on the same event

Under the v1 and v2a stillness readings (changed-area level rules),
this event is **cleared** by the no-SAM arm: the energy trace reads
the descent's own tail and settling (peak changed-area fraction
0.0291 in the first moments after the core, against a clip activity
level of 0.0115) as "person moved after the descent", while the SAM
centroid over the same seconds moved 0.0046 frame heights. Which
no-SAM disposition this event gets is decided by the stillness
construction; that it cannot be *confirmed* without SAM is decided
by the posture phases and holds in every reading.
