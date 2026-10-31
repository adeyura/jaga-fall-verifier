# Split freeze — 2026-10-29

Frozen under SPEC D5 (two-split protocol) and the evaluation plan of
2026-10-28 for evaluation sequencing (approved 22:03 JST). Dev is for
all iteration, including the D1 gate. The test
split receives exactly ONE confirmation run after the freeze.

## Frozen files

- `results/split_dev.csv` — 215 rows (216 lines with header)
  SHA-256: `f968ee85b519ecc69d9506b55f4ad65902d49c49052e1d80b1b906b666607895`
- `results/split_test.csv` — 68 rows (69 lines with header)
  SHA-256: `6006c2fa9d4e3aaae03d5d4c80bf3b3dc67385582bab8a62fa22846851d0ac03`

No clip appears in both files (verified by clip_id set intersection,
empty).

## Counting convention (settled 2026-10-29)

- Counts are **events, not clips**. UP-Fall's two camera views of one
  trial are one event (SPEC D5: "UP-Fall's two views of one event
  count as one sample"). A UP-Fall event is keyed by
  (subject, activity, trial).
- Le2i clips are single-view recordings; each clip is one event.
- Subject 1 = 24 events (15 fall + 9 ADL). Subject 2 = 24 events
  (15 fall + 9 ADL). Confirmation results are reported at event level
  with Wilson intervals; dev and confirmation numbers are labeled and
  never pooled.

## Dev split — 215 clips / 191 events

### UP-Fall Subject 1 (48 files / 24 events; all 48 downloaded, status ok)

| Activity | Class | Files | Events |
|---|---|---|---|
| 1 | fall | 6 | 3 |
| 2 | fall | 6 | 3 |
| 3 | fall | 6 | 3 |
| 4 | fall | 6 | 3 |
| 5 | fall | 6 | 3 |
| 8 | ADL | 6 | 3 |
| 9 | ADL | 6 | 3 |
| 11 | ADL | 6 | 3 |

Fall subtotal 30 files / 15 events; ADL subtotal 18 files / 9 events.

### Le2i-dev (167 clips = 167 events)

| Room / scene group | Fall | ADL |
|---|---|---|
| Coffee_room_01 | 47 | 0 |
| Home_01 | 30 | 0 |
| Home_02 | 7 | 23 |
| Office | 0 | 33 |
| Lecture room | 0 | 27 |

Fall subtotal 84; ADL subtotal 83. Dev keeps falls from 3 rooms and
ADL from 3 rooms.

### Dev totals

Fall 114 files / 99 events. ADL 101 files / 92 events.

## Test (confirmation) split — 68 clips / 44 events

### UP-Fall Subject 2 (48 files / 24 events)

Same activity structure as Subject 1: activities 1–5 fall
(30 files / 15 events), activities 8, 9, 11 ADL (18 files / 9 events).

Download state at freeze: 32 files on the VM (status ok — all 30 fall
files plus Activity 8 Trial 1, both cameras). 16 files are still in
transfer and are frozen by identity (filename + Drive ID); they are
all ADL: Activity 8 Trials 2–3, Activity 9 Trials 1–3, Activity 11
Trials 1–3 (8 ADL events).

**Quarantine:** Subject 2 is reserved test data. These rows are
manifest entries only; no Subject 2 clip content has been opened,
assembled, inspected, or run through any pipeline stage, and none
will be before the confirmation run.

### Le2i holdout (20 clips = 20 events)

Coffee_room_02: 12 fall + 8 ADL.

### Test totals

Fall 42 files / 27 events. ADL 26 files / 17 events. Total 44 events.

**D5 fallback-threshold check:** SPEC abandons the split if the
frozen test would fall under ~25 events. The test split holds 44
events in total and 27 fall events, so it clears the threshold under
either reading. The split stands.

## Le2i room-split rule

Le2i is split by whole room / scene group (the room prefix of the
manifest's `sequence` field), never by random clips, so no scene
appears on both sides. The holdout is exactly one whole room:
**Coffee_room_02**. It is the only room group that both contains both
classes and lifts the confirmation set over the fall-event target:
15 (Subject 2) + 12 (Coffee_room_02) = 27 fall events. Every other
Le2i row with a fall/ADL label is dev. Rationale for not choosing
another room: Office (33 ADL) and Lecture room (27 ADL) contain no
falls and would leave confirmation falls at 15; Home_02 (7 fall)
would reach only 22; Home_01 (30 fall) and Coffee_room_01 (47 fall)
contain no ADL and would strip a fall room from dev entirely.

## Schema harmonization (the only transformation applied)

The two source manifests have different schemas and one colliding
column name, so the split files use one unified schema that carries
every source column:

- `label` means the class (fall / adl) for both datasets. Le2i values
  are verbatim from `le2i_manifest.csv`. UP-Fall's source manifest has
  no class column (its `label` holds the camera string); the class is
  derived from the activity number (falls = activities 1–5, ADL =
  8/9/11, per `FALL_ACTIVITIES` / `NEGATIVE_ACTIVITIES` in
  `scripts/download_up_fall.py`), and the original camera label is
  preserved verbatim in `source_label` (the camera is also in `kind`).
- UP-Fall's `sha256` is carried as `file_sha256` (Le2i's native name).
- `clip_id` for UP-Fall rows is the manifest's filename, its unique
  key. `dataset` is `up_fall` for UP-Fall rows (the source manifest
  has no dataset column) and `le2i` as recorded for Le2i rows.
- `split` is filled (`dev` / `test`) on every row. All other values
  are carried unchanged; source-specific columns are blank where they
  do not apply. `negative_category` is blank on every row, exactly as
  in both source manifests (see shortfalls).

## Exclusions (dated rule, 2026-10-29)

- **UP-Fall Subjects 3–5** (144 manifest rows) are in neither split:
  the approved plan assigns Subject 1 to dev and Subject 2 to test,
  and unavailable subjects are excluded rather than partially used.
  Download state at freeze: Subject 3: 0/48 ok; Subject 4: 0/48 ok;
  Subject 5: 1/48 ok. The plan's flip condition (Subject 3 complete
  by Oct 29 evening, enabling dev = S1+S2 / test = S3) is therefore
  **not** met at freeze time.
- **Le2i undetermined clips** (3) are in neither scored set, because
  they carry no fall/ADL label in the source manifest:
  `le2i_coffee-room-01_video-26` (Coffee_room_01),
  `le2i_coffee-room-02_video-50` and `le2i_coffee-room-02_video-52`
  (Coffee_room_02).

## Ambiguities and shortfalls, stated plainly

1. **UP-Fall class is derived, not recorded.** The download manifest
   records camera in `label` and has no class column. The fall/ADL
   assignment comes from the activity sets in
   `scripts/download_up_fall.py` and agrees with the recorded
   counts (30 fall files / 18 ADL files per subject), but it is a
   derivation, documented here, not a manifest fact.
2. **Activity 8 vs 9 naming is unverified.** The downloader's
   docstring originally named the hard negatives 8, 9, and 11 with
   English labels (removed 2026-11-01; numeric IDs only). Nothing in the manifests
   confirms the 8/9 name assignment against the dataset paper
   (Martínez-Villaseñor et al., Sensors 2019). The class split
   (fall vs ADL) is unaffected, but the 8/9 names must be verified
   against the paper before any public per-category claim. The split
   CSVs therefore leave `negative_category` blank rather than
   encoding an unverified name.
3. **The 16 in-transfer test files have no reference hash yet.** In
   the source manifest their `sha256` and `bytes` fields are blank
   (the VM download route failed on quota; the manifest status reads
   `failed`, which describes the VM download attempt, not the files'
   existence — the files exist on the user's laptop and are being
   relayed). They enter this freeze by filename + Drive ID only.
   Their SHA-256 must be recorded from the verified transfer copies
   before the confirmation run; the success criterion for the
   transfer is all 16 files sha256-verified.
4. **Le2i has no hard-negative categories.** `negative_category` is
   blank for all 190 Le2i rows in the source manifest, so Le2i ADL is
   an undifferentiated everyday-activity pool; no per-category Le2i
   breakdown exists or can be computed from the manifest.
5. **Hard-negative depth is thin.** Against SPEC's target of ~12 per
   hard-negative category, UP-Fall provides exactly 3 events per ADL
   activity in each split (activities 8, 9, 11). Stumble-and-recover
   does not exist as a labeled category in either dataset (SPEC
   already records this shortfall), and neither does crouch.
6. **Le2i is room×class confounded.** Coffee_room_01 and Home_01 are
   fall-only; Office and Lecture room are ADL-only; only
   Coffee_room_02 and Home_02 contain both classes. The holdout
   Coffee_room_02 is a different physical room and camera from dev's
   Coffee_room_01 but the same scene type (a coffee room), and the
   Le2i confirmation result is a single room's result. Together with
   the single test subject in UP-Fall, the confirmation run bounds
   generalization; it does not establish it.
7. **Split sizes diverge from SPEC's ~90-clip target.** SPEC D5 set
   a target frozen set of ~90 clips; the approved 2026-10-28 plan
   instead assigns the full Subject 1 + Le2i-dev (215 clips) to dev
   and 68 clips to confirmation. Recorded here as an adopted
   divergence, not an oversight.
