# Offline example — one real clip, no API key

`run_example.py` replays the pinned output of one real scored clip
through this repository's own downstream code, entirely offline:

```bash
PYTHONPATH=src python3 examples/run_example.py
```

The clip is UP-Fall Subject 1, Activity 1, Trial 1, Camera 1 (event
`upfall:S1:A1:T1`, a staged fall), as processed by the scored D1 dev
gate run under config hash `6d7c03257b12ab00`.

## What is pinned, and where it came from

- `upfall_s1_a1t1_cam1/sam_keyframes.json` — the SAM 3.1 responses for
  the clip's 18 keyframes, in the parsed form the pipeline consumed
  them (per-instance box, mask area, elongation, axis tilt, base-band
  share), exported verbatim from the gate run's per-clip record. The
  run's recorded per-track centroid and floor-proximity values ride
  along so the mask-local centroid and bottom row can be reconstructed
  exactly; the replay checks the rebuilt features against the recorded
  ones and prints the maximum drift.
- `upfall_s1_a1t1_cam1/record.json` — the rest of that run's record:
  the motion gate's segment, the timing intervals, the recorded rules
  verdict and phases (the replay's live verdict must match them), and
  the dev gate full arm's recorded Spark adjudication.
- `upfall_s1_a1t1_cam1/expected_output.txt` — the verified output of
  the command above, for diffing.

## What runs live, and what is replayed

Live, in this repo's code: IoU track association and kinematics
(`jaga.features`), the frozen rules state machine (`jaga.rules`), the
traces evidence form (`jaga.traces`), and the alert-ladder tier
(`jaga.alerts`).

Replayed from the record, and labeled as replayed in the output: the
motion gate's segment bounds and the local timing intervals. Those two
stages read the video file itself, and dataset media never enters this
repository (see "Datasets" in the top-level README) — that policy, not
a technical limit, is why they are replayed rather than recomputed.
One reconstruction is documented in `record.json`: the harness record
stores the descent interval's core duration but not its core onset;
the pinned core onset is the run onset, and the verdict is verified
insensitive to that choice across the core's whole plausible range.

The adjudication printed at the end is the dev gate's recorded output,
kept for provenance. Muse Spark is **not** in the shipped
configuration (the D1 gate removed it; see the top-level README), and
this example does not call it.
