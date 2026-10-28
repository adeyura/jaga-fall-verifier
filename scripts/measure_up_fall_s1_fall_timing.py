"""Measure UP-Fall Subject 1 fall descent durations vs the P3 window.

SPEC P3 freezes the side-view descent window at [0.4, 1.0] s and
carries an obligation: the window must be checked against the UP-Fall
dev-split fall distribution before the confirmation run. SPEC D4:
descent timing is measured locally at native frame rate from the
motion signal, never from keyframes.

This unit is that check, measurement only. For every Subject 1 fall
clip (activities 1-5, trials 1-3, cameras 1-2; 30 clips) it runs ONLY
the pipeline's local stages, exactly as src/jaga/harness.py invokes
them — probe_duration, gate_clip (motion gate), timing_from_video
(local timing) — and records the selected descent interval's onset,
core duration, and full envelope run. No SAM calls, no adjudicator,
no Meta API use of any kind. Nothing here changes the window, the
config, or SPEC.md; any amendment is a separate decision.

Zips are sha256-verified against results/up_fall_download_manifest.csv
before use; clips are assembled by scripts/assemble_up_fall_clips.py
when missing. Output: results/up_fall_s1_fall_timing.csv with one row
per clip. The "descent" is TimingResult.descent (the strongest
interval whose core falls in the timing module's own selection
bounds); if no interval qualifies but intervals exist, the strongest
interval is recorded instead and the row's note says so, so the
distribution is never silently truncated.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jaga.frames import probe_duration  # noqa: E402
from jaga.motion_gate import gate_clip  # noqa: E402
from jaga.timing import timing_from_video  # noqa: E402

import assemble_up_fall_clips as asm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "up_fall_s1_fall_timing.csv"
WINDOW_LO, WINDOW_HI = 0.4, 1.0  # frozen P3 side window, SPEC.md


def measure(row: dict) -> dict:
    stem = Path(row["filename"]).stem
    rec = {"filename": row["filename"], "activity": row["activity"],
           "trial": row["trial"], "camera": row["kind"],
           "gate_segments": "", "onset_s": "", "core_duration_s": "",
           "full_run_s": "", "in_window": "", "note": ""}
    zip_path = asm.ZIP_DIR / row["filename"]
    if row["status"] != "ok":
        rec["note"] = f"manifest status {row['status']!r}; not measured"
        return rec
    if asm.sha256_of(zip_path) != row["sha256"]:
        rec["note"] = "sha256 mismatch vs manifest; not measured"
        return rec
    clip = asm.CLIP_DIR / f"{stem}.mp4"
    try:
        if not clip.exists():
            asm.assemble_one(zip_path, clip)
        duration = probe_duration(clip)
        segments, _stats = gate_clip(clip, duration)
        rec["gate_segments"] = len(segments)
        timing = timing_from_video(clip)
    except Exception as e:
        rec["note"] = f"error: {type(e).__name__}: {e}"
        return rec
    iv = timing.descent
    if iv is None and timing.intervals:
        iv = max(timing.intervals, key=lambda v: v.peak_area_frac)
        rec["note"] = ("no interval inside the timing module's descent "
                       "selection bounds; strongest interval recorded")
    if iv is None:
        rec["note"] = (rec["note"] + "; " if rec["note"] else "") + \
            "no timing interval found"
        return rec
    if not segments:
        rec["note"] = (rec["note"] + "; " if rec["note"] else "") + \
            "gate produced zero segments (gate miss); timing still measured"
    core = iv.core_duration_s
    steps = round(core * timing.fps)
    if steps / timing.fps == WINDOW_LO and core != steps / timing.fps:
        # Knife-edge: the core is exactly `steps` steps of the timing
        # series (0.40 s in step terms), but float subtraction leaves
        # it a hair off the bound. Count it by the raw float — that is
        # what the rules stage compares — and say so on the row.
        side = "below" if core < WINDOW_LO else "above"
        rec["note"] = (rec["note"] + "; " if rec["note"] else "") + \
            (f"core is exactly {steps} steps of the {timing.fps:g} fps "
             f"timing series = 0.40 s in step terms; the float value "
             f"sits a hair {side} the 0.4 bound and is counted by the "
             f"raw float, as the rules stage compares it")
    rec["onset_s"] = f"{iv.onset_s:.2f}"
    rec["core_duration_s"] = f"{core:.2f}"
    rec["full_run_s"] = f"{iv.duration_s:.2f}"
    rec["in_window"] = "yes" if WINDOW_LO <= core <= WINDOW_HI else "no"
    return rec


def main() -> int:
    rows = asm.select_rows({"1"}, {"1", "2", "3", "4", "5"},
                           {"1", "2", "3"}, {"1", "2"})
    print(f"measuring {len(rows)} Subject 1 fall clips "
          f"(local stages only: gate + timing)")
    records = []
    for row in rows:
        rec = measure(row)
        records.append(rec)
        print(f"  {rec['filename']}: segments={rec['gate_segments']} "
              f"onset={rec['onset_s']} core={rec['core_duration_s']} "
              f"run={rec['full_run_s']} in_window={rec['in_window']} "
              f"{rec['note']}")
    fields = ["filename", "activity", "trial", "camera", "gate_segments",
              "onset_s", "core_duration_s", "full_run_s", "in_window",
              "note"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)
    print(f"wrote {OUT} ({len(records)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
