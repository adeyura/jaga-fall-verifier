# Visual re-audit (independent second pass) — 2026-10-29

Purpose: verify or refute a first auditor's claim that five dev-split Le2i clips carry
wrong dataset labels. This audit was performed without the first
audit's findings: frame sheets were extracted and
viewed independently (own sheets in `cache/visual_reaudit/`), without reading
`results/gate_d1_visual_audit.md` or `cache/visual_audit/`. Dev split only; no
test-split, Subject 2, or Coffee_room_02 content was opened. Evidence check only —
no scores change, no labels were edited.

## Method

- Frame sheets extracted with ffmpeg from the source clips: full clip at 0.5 s steps
  (0.2 s steps for the 5.8 s Coffee clip), timestamps burned into each frame, plus a
  0.2 s-step zoom over the Lecture video (2) descent. Sheets:
  `cache/visual_reaudit/{cal_fall_coffee01,cal_adl_upfall_a11,coffee30,lecture02,
  lecture02_zoom,lecture03,office06,office13}_*.png`.
- Calibration viewed first:
  - Known annotated fall, Coffee_room_01 video (1) (annotation file: fall frames
    48–80): man walks to a pre-positioned patterned crash mat, pitches forward at
    ~2.0 s, is fully prone on the mat by ~2.5 s (descent breaks briefly on hands/knee),
    then lies motionless to the end. This is the dataset's fall signature.
  - Known ADL, UP-Fall Subject1 Activity11 Trial1 Camera1 ("laying down"): the actor
    lies supine and essentially motionless on a mat for the entire ~59 s clip.
    Prolonged motionless lying therefore occurs in genuine ADL too, so stillness alone
    was NOT used as the fall criterion; the decisive feature in every judgment below
    is the descent: a rapid collapse (≲1 s, no held intermediate posture) onto the
    mat, versus a slow sequence of held, balanced postures (sit, kneel, lower).

## Findings per clip

### le2i_lecture-room_video-02 — dev label: ADL — judgment: LABEL-DOUBTFUL (claim verified)
- Posture sequence: empty lecture room with the patterned crash mat pre-positioned on
  the floor → man walks the room, stands beside the mat ~14.5 s → knees drop and the
  body pitches forward (0.2 s-step zoom: upright at 14.8 s, knees on the floor at
  ~15.0–15.2 s, torso horizontal at 15.4 s) → fully prone and extended on the mat by
  ~15.6 s → motionless on the mat to the end of the clip (20.2 s).
- Fall occurs: yes — a staged collapse-style fall onto the pre-positioned mat.
- Strongest evidence: less than a second separates the standing frame (14.8 s) from
  the fully prone frame (15.6 s), and he never rises again in the remaining ~4.6 s.
- Nuance: the descent passes through a brief knee contact rather than a free dive;
  the calibration fall (Coffee video 1) breaks its descent the same way, so this does
  not rescue the ADL label.

### le2i_lecture-room_video-03 — dev label: ADL — judgment: LABEL-DOUBTFUL (claim verified)
- Posture sequence: man enters, fetches a garment, drapes it over the chair beside the
  pre-positioned mat ~12.5–14.5 s → stands facing the room ~15–18 s → tips backward at
  18.5 s → at 19.0 s the body is fully horizontal in mid-descent with legs kicked up →
  lands supine on the mat at 19.5 s → motionless to the end (24.9 s).
- Fall occurs: yes — staged backward fall onto the pre-positioned mat.
- Strongest evidence: the 19.0 s frame, body airborne and horizontal with legs kicked
  up above the mat — an uncontrolled posture no deliberate lie-down passes through —
  followed by ~5 s of motionless supine lying.

### le2i_office_video-06 — dev label: ADL — judgment: LABEL-DOUBTFUL (claim verified)
- Posture sequence: man enters, sits on a chair in a controlled way ~5.5 s, rests
  leaning back (a genuine ADL segment), stands again ~11 s → steps away from the chair
  → at 12.5 s is mid-fall with heavy motion blur, body tipping backward toward the
  pre-positioned mat, arms flung → lands supine on the mat at 13.0 s, legs raised →
  motionless supine to the end (16.6 s).
- Fall occurs: yes — staged backward fall onto the pre-positioned mat. The clip
  contains an ADL prelude, but its terminal event is the fall and the actor ends lying
  motionless, which is what a clip-level fall/ADL label turns on.
- Strongest evidence: the motion-blurred 12.5 s frame (body already past horizontal,
  arms flung) followed immediately by the supine landing on the mat.

### le2i_office_video-13 — dev label: ADL — judgment: LABEL-DOUBTFUL (claim verified)
- Posture sequence: man enters ~4.5 s, takes a phone call standing at the table
  (~7–11 s), walks to the chair, sits and reads papers with legs crossed (~16–25 s) —
  a long genuine ADL prelude → stands at ~25.5 s and steps toward the pre-positioned
  mat → at 26.5 s is in a blurred forward collapse, one knee dropping, torso pitching →
  prone across the mat at 27.0 s, one leg still kicked up → motionless on the mat to
  the end (31.7 s).
- Fall occurs: yes — staged fall onto the pre-positioned mat, ending motionless.
- Strongest evidence: standing at 26.0 s, prone and extended on the mat at 27.0 s,
  with no intermediate held posture, and no movement in the final ~4 s.

### le2i_coffee-room-01_video-30 — dev label: fall — judgment: LABEL-DOUBTFUL (claim verified — the fall label is refuted)
- Posture sequence (0.2 s sampling; the dataset annotation marks "fall frames 80–104"
  = 3.2–4.16 s): man walks slowly across the room 0–3.0 s → at 3.2 s turns and lowers
  himself backward → at 3.4 s he is seated upright on the edge of the mat, legs
  stretched out on the floor in front of him, balanced and stable → transitions to
  kneeling beside the mat, hunched forward with head down and hands on the mat
  (3.6–3.8 s) → remains kneeling, hunched, to the end (5.8 s).
- Fall occurs: no. No rapid descent at any point; he never lies down. The lowering is
  a ~1.5 s sequence of held, balanced postures (stand → sit on mat edge → kneel),
  unlike the calibration fall's ~0.5 s upright-to-prone collapse.
- Strongest evidence: the 3.4 s frame — mid-way through the annotated "fall" interval
  he is sitting upright and stable on the mat's edge, and the clip ends with him
  kneeling, never prone or supine.

## Supporting claim: annotation files ship only with the fall rooms — CONFIRMED

Checked directly against the extracted dataset tree and the room zip listings:
- `Coffee_room_01.zip` contains an `Annotation_files/` folder with 48 per-video .txt
  files; `Home_01.zip` contains `Annotation_files/` with 30 .txt files. The extracted
  Coffee/Home trees likewise have `Videos/` + `Annotation_files/` structure,
  including per-video fall-interval files (e.g. Coffee_room_01 video (30).txt marks
  fall frames 80–104).
- `Lecture_room.zip` and `Office.zip` contain zero .txt files and no annotation
  folder at all; the extracted `Lecture room/` and `Office/` folders hold bare .avi
  files directly. Their dev-split ADL labels therefore could not have come from
  per-video annotation files — consistent with the split manifest's own note that
  these labels were inferred from room layout.

## Summary

| clip | dev label | fall on footage? | label judgment |
|---|---|---|---|
| le2i_lecture-room_video-02 | adl | yes (collapse to prone, ~15 s) | label-doubtful |
| le2i_lecture-room_video-03 | adl | yes (backward, ~19 s) | label-doubtful |
| le2i_office_video-06 | adl | yes (backward, ~12.5 s) | label-doubtful |
| le2i_office_video-13 | adl | yes (forward collapse, ~26.5 s) | label-doubtful |
| le2i_coffee-room-01_video-30 | fall | no (sit to mat edge, then kneel) | label-doubtful |

The first auditor's claim is verified on all five clips and on the supporting
annotation claim: the four Lecture/Office clips labeled ADL each show a staged fall
onto a pre-positioned crash mat ending with the actor lying motionless, and
Coffee_room_01 video (30), labeled a fall, shows only a controlled sit onto the mat
edge followed by kneeling.
