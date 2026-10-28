"""Measure descent core durations on two dev-only groups (local stages).

Feeds the pending P3 side-window amendment decision with the two
distributions the decision turns on, and nothing else:

  A) UP-Fall Subject 1 ADL clips (activities 8, 9, 11; 18 clips) —
     the dev hard-negative descent cores.
  B) Le2i-dev fall clips (84 clips; rooms Coffee_room_01, Home_01,
     Home_02 — the test holdout room Coffee_room_02 is never read).

Measurement only, following scripts/measure_up_fall_s1_fall_timing.py
exactly: probe_duration, gate_clip (motion gate), timing_from_video
(local timing) — no SAM, no adjudicator, no Meta API use of any kind.
This script records numbers; it recommends nothing and changes no
window, config, or spec.

Conventions carried from the S1 fall measurement:
  - The recorded descent is TimingResult.descent (strongest interval
    whose core falls in the timing module's own selection bounds). If
    no interval qualifies but intervals exist, the strongest interval
    is recorded instead and the row is flagged fallback=yes, so the
    distribution is never silently truncated.
  - UP-Fall zips are sha256-verified against the download manifest
    before use; clips are assembled by assemble_up_fall_clips.py when
    missing. Le2i clips are already MP4/AVI files; each is
    sha256-verified against the frozen split's file_sha256.
  - In-window comparisons use the raw float core, as the rules stage
    compares it; the 2-decimal column is display only. A knife-edge
    note (core equal to a window bound in step terms but a hair off
    in float) is added when it occurs, as in the S1 CSV.

Timing runs at the pipeline's own series rate (TIMING decode_fps,
30 fps; see src/jaga/timing.py series_from_video) for every clip,
whatever the container's native rate; both rates are recorded per
row (fps_series, fps_native).

Output: results/dev_core_measurements.csv (one row per clip,
failures included as explicit rows) and
results/dev_core_measurements_summary.md.
"""
from __future__ import annotations

import csv
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jaga.frames import probe_duration  # noqa: E402
from jaga.motion_gate import gate_clip  # noqa: E402
from jaga.timing import timing_from_video  # noqa: E402

import assemble_up_fall_clips as asm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPLIT_DEV = ROOT / "results" / "split_dev.csv"
OUT_CSV = ROOT / "results" / "dev_core_measurements.csv"
OUT_MD = ROOT / "results" / "dev_core_measurements_summary.md"

WINDOWS = [("0.4_1.0", 0.4, 1.0), ("0.20_1.0", 0.20, 1.0),
           ("0.1_0.8", 0.1, 0.8)]

FIELDS = ["clip_id", "dataset", "group", "activity", "room_scene",
          "trial", "camera", "label", "fps_series", "fps_native",
          "gate_segments", "onset_s", "core_duration_s",
          "core_duration_s_disp", "full_run_s", "fallback", "status",
          "in_window_0.4_1.0", "in_window_0.20_1.0",
          "in_window_0.1_0.8", "note"]


def native_fps(path: Path) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=avg_frame_rate",
             "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True)
        num, _, den = out.stdout.strip().partition("/")
        fps = float(num) / float(den) if den else float(num)
        return f"{fps:g}"
    except Exception:
        return ""


def empty_rec(**kw) -> dict:
    rec = {f: "" for f in FIELDS}
    rec.update(kw)
    return rec


def measure_clip(rec: dict, clip: Path) -> dict:
    """Run gate + timing on an assembled/existing clip; fill rec."""
    try:
        duration = probe_duration(clip)
        segments, _stats = gate_clip(clip, duration)
        rec["gate_segments"] = len(segments)
        timing = timing_from_video(clip)
    except Exception as e:
        rec["status"] = "error"
        rec["note"] = f"error: {type(e).__name__}: {e}"
        return rec
    rec["fps_series"] = f"{timing.fps:g}"
    rec["fps_native"] = native_fps(clip)
    iv = timing.descent
    rec["fallback"] = "no"
    if iv is None and timing.intervals:
        iv = max(timing.intervals, key=lambda v: v.peak_area_frac)
        rec["fallback"] = "yes"
        rec["note"] = ("no interval inside the timing module's descent "
                       "selection bounds; strongest interval recorded")
    if iv is None:
        rec["status"] = "no_interval"
        rec["note"] = (rec["note"] + "; " if rec["note"] else "") + \
            "no timing interval found"
        return rec
    if not segments:
        rec["note"] = (rec["note"] + "; " if rec["note"] else "") + \
            "gate produced zero segments (gate miss); timing still measured"
    core = iv.core_duration_s
    # Knife-edge notes, as in the S1 fall CSV: a core equal to a
    # window bound in step terms but a hair off in float is counted
    # by the raw float; say so on the row.
    steps = round(core * timing.fps)
    if steps / timing.fps != core:
        for _name, lo, hi in WINDOWS:
            for bound in (lo, hi):
                if steps / timing.fps == bound:
                    side = "below" if core < bound else "above"
                    rec["note"] = (rec["note"] + "; " if rec["note"]
                                   else "") + \
                        (f"core is exactly {steps} steps of the "
                         f"{timing.fps:g} fps timing series = {bound:g} s "
                         f"in step terms; the float value sits a hair "
                         f"{side} the {bound:g} bound and is counted by "
                         f"the raw float, as the rules stage compares it")
    rec["status"] = "measured"
    rec["onset_s"] = f"{iv.onset_s:.2f}"
    rec["core_duration_s"] = repr(core)
    rec["core_duration_s_disp"] = f"{core:.2f}"
    rec["full_run_s"] = f"{iv.duration_s:.2f}"
    for name, lo, hi in WINDOWS:
        rec[f"in_window_{name}"] = "yes" if lo <= core <= hi else "no"
    return rec


def group_a(split_rows: list[dict]) -> list[dict]:
    """UP-Fall Subject 1 ADL: activities 8, 9, 11 from the manifest."""
    want = {r["clip_id"] for r in split_rows
            if r["dataset"] == "up_fall" and r["label"] == "adl"}
    rows = asm.select_rows({"1"}, {"8", "9", "11"}, {"1", "2", "3"},
                           {"1", "2"})
    have = {r["filename"] for r in rows}
    records = []
    for fn in sorted(want - have):
        records.append(empty_rec(
            clip_id=fn, dataset="up_fall", group="upfall_adl",
            label="adl", status="error",
            note="in split_dev.csv but no matching download-manifest row"))
    for row in rows:
        stem = Path(row["filename"]).stem
        rec = empty_rec(clip_id=row["filename"], dataset="up_fall",
                        group="upfall_adl", activity=row["activity"],
                        trial=row["trial"], camera=row["kind"],
                        label="adl")
        zip_path = asm.ZIP_DIR / row["filename"]
        if row["filename"] not in want:
            rec["status"] = "error"
            rec["note"] = "manifest row not present in split_dev.csv"
            records.append(rec)
            continue
        if row["status"] != "ok":
            rec["status"] = "error"
            rec["note"] = f"manifest status {row['status']!r}; not measured"
            records.append(rec)
            continue
        if asm.sha256_of(zip_path) != row["sha256"]:
            rec["status"] = "error"
            rec["note"] = "sha256 mismatch vs manifest; not measured"
            records.append(rec)
            continue
        clip = asm.CLIP_DIR / f"{stem}.mp4"
        try:
            if not clip.exists():
                asm.assemble_one(zip_path, clip)
        except Exception as e:
            rec["status"] = "error"
            rec["note"] = f"assembly failed: {type(e).__name__}: {e}"
            records.append(rec)
            continue
        records.append(measure_clip(rec, clip))
    return records


def group_b(split_rows: list[dict]) -> list[dict]:
    """Le2i-dev falls from the frozen split (existing video files)."""
    rows = [r for r in split_rows
            if r["dataset"] == "le2i" and r["label"] == "fall"]
    records = []
    for row in rows:
        room = row["sequence"].split("/")[0]
        rec = empty_rec(clip_id=row["clip_id"], dataset="le2i",
                        group="le2i_fall", room_scene=room,
                        camera=row["camera"], label="fall")
        path = ROOT / row["video_path"]
        if not path.exists():
            rec["status"] = "error"
            rec["note"] = f"video file missing: {row['video_path']}"
            records.append(rec)
            continue
        if asm.sha256_of(path) != row["file_sha256"]:
            rec["status"] = "error"
            rec["note"] = "sha256 mismatch vs split_dev file_sha256; " \
                          "not measured"
            records.append(rec)
            continue
        records.append(measure_clip(rec, path))
    return records


def quartiles(xs: list[float]) -> tuple[float, float, float, float, float]:
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return xs[0], q[0], statistics.median(xs), q[2], xs[-1]


def stats_block(title: str, cores: list[float]) -> list[str]:
    lo, q1, med, q3, hi = quartiles(cores)
    return [f"| {title} | {len(cores)} | {lo:.4f} | {q1:.4f} | "
            f"{med:.4f} | {q3:.4f} | {hi:.4f} |"]


def window_table(records: list[dict]) -> list[str]:
    lines = []
    for name, lo, hi in WINDOWS:
        n = sum(1 for r in records if r[f"in_window_{name}"] == "yes")
        lines.append(f"| [{lo:g}, {hi:g}] | {n} | {len(records)} |")
    return lines


def write_summary(records: list[dict]) -> None:
    a = [r for r in records if r["group"] == "upfall_adl"]
    b = [r for r in records if r["group"] == "le2i_fall"]
    a_m = [r for r in a if r["status"] == "measured"]
    b_m = [r for r in b if r["status"] == "measured"]
    a_cores = [float(r["core_duration_s"]) for r in a_m]
    b_cores = [float(r["core_duration_s"]) for r in b_m]
    a_clean = [float(r["core_duration_s"]) for r in a_m
               if r["fallback"] == "no"]
    b_clean = [float(r["core_duration_s"]) for r in b_m
               if r["fallback"] == "no"]
    failures = [r for r in records if r["status"] != "measured"]
    lines = [
        "# Dev core measurements — summary",
        "",
        "Descent core durations from the pipeline's local stages only",
        "(motion gate + timing; no SAM, no adjudicator, no Meta API).",
        "Measured 2026-10-28 for the pending P3 side-window amendment",
        "decision. Measurements only; this file recommends nothing.",
        "",
        "## Distribution of descent core durations (seconds)",
        "",
        "Quartiles use the inclusive method. 'All measured' includes",
        "fallback rows; 'descent-selected only' excludes them (see",
        "the fallback caveat under Methods).",
        "",
        "| group | n | min | Q1 | median | Q3 | max |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += stats_block("upfall_adl — all measured", a_cores)
    lines += stats_block("upfall_adl — descent-selected only", a_clean)
    lines += stats_block("le2i_fall — all measured", b_cores)
    lines += stats_block("le2i_fall — descent-selected only", b_clean)
    lines += [
        "",
        f"Fallback rows: upfall_adl "
        f"{sum(1 for r in a_m if r['fallback'] == 'yes')}/{len(a_m)}, "
        f"le2i_fall {sum(1 for r in b_m if r['fallback'] == 'yes')}"
        f"/{len(b_m)}.",
        "",
        "## In-window counts (raw float cores, as the rules stage compares them)",
        "",
        "### Group A — UP-Fall Subject 1 ADL (hard negatives)",
        "",
        "| window (s) | in-window | measured |",
        "|---|---|---|",
    ]
    lines += window_table(a_m)
    lines += [
        "",
        "### Group B — Le2i-dev falls",
        "",
        "| window (s) | in-window | measured |",
        "|---|---|---|",
    ]
    lines += window_table(b_m)
    lines += ["", "## Failures and non-measured rows", ""]
    if failures:
        for r in failures:
            lines.append(f"- {r['clip_id']} ({r['group']}): "
                         f"status={r['status']} — {r['note']}")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Methods",
        "",
        "- Stages: probe_duration, gate_clip (motion gate),",
        "  timing_from_video (local timing) — the same invocation as",
        "  src/jaga/harness.py and scripts/measure_up_fall_s1_fall_"
        "timing.py. No other pipeline stage ran.",
        "- The timing module decodes every clip at its own fixed",
        "  series rate (TIMING decode_fps = 30 fps), resampling the",
        "  container's native rate (UP-Fall assemblies 18 fps, Le2i",
        "  25 fps). fps_series and fps_native are recorded per row;",
        "  all durations are on the 30 fps series grid (~0.033 s",
        "  steps).",
        "- Recorded descent: TimingResult.descent — the strongest",
        "  interval whose core falls in the timing module's own",
        "  selection bounds.",
        "- Fallback caveat: when no interval qualifies but intervals",
        "  exist, the strongest interval is recorded and the row is",
        "  flagged fallback=yes. A fallback value is what the timing",
        "  module reports when it fails to find a qualifying",
        "  interval; it is not a clean descent measurement and must",
        "  not be read as one.",
        "- UP-Fall zips were sha256-verified against",
        "  results/up_fall_download_manifest.csv before assembly;",
        "  Le2i files were sha256-verified against the frozen",
        "  split's file_sha256. Clips failing verification were not",
        "  measured and appear above as failures.",
        "- Dev split only (results/split_dev.csv). Subject 2 and",
        "  the Le2i holdout room Coffee_room_02 were never read.",
        "- Core durations are stored unrounded in the CSV",
        "  (core_duration_s, full float repr) alongside a 2-decimal",
        "  display column; every count in this summary uses the raw",
        "  floats.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")


def main() -> int:
    split_rows = list(csv.DictReader(SPLIT_DEV.open(newline="")))
    records = []
    for name, fn in (("A: UP-Fall S1 ADL", lambda: group_a(split_rows)),
                     ("B: Le2i-dev falls", lambda: group_b(split_rows))):
        recs = fn()
        records += recs
        print(f"group {name}: {len(recs)} rows, "
              f"{sum(1 for r in recs if r['status'] == 'measured')} "
              f"measured")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(records)
    print(f"wrote {OUT_CSV} ({len(records)} rows)")
    write_summary(records)
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
