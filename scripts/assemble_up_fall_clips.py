"""Assemble UP-Fall clips from their per-trial PNG image sequences.

Each downloaded UP-Fall camera file is a zip of timestamp-named PNGs
(one per frame, 640x480, captured at 18 fps). The pipeline consumes
mp4 clips, so assembly is: verify the zip's sha256 against
results/up_fall_download_manifest.csv, sort the PNG names (the
timestamp names sort chronologically), renumber them as a plain
sequence, and encode with ffmpeg at the native 18 fps.

This script exists so the assembly the 2026-10-28 smoke clip was built
with is reproducible rather than a one-off shell command.
The output is checked: the mp4's
decoded frame count must equal the zip's PNG count, or the clip is
rejected and no partial file is left in place.

Usage:
  python scripts/assemble_up_fall_clips.py [--subjects 1] \
      [--activities 1,2,3,4,5] [--trials 1,2,3] [--cameras 1,2] \
      [--force]

Defaults assemble the Subject 1 fall set (activities 1-5, all trials,
both cameras, 30 clips). Existing clips are skipped unless --force.
Media lands under data/up_fall/clips/ (gitignored, never committed).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "results" / "up_fall_download_manifest.csv"
ZIP_DIR = ROOT / "data" / "up_fall"
CLIP_DIR = ZIP_DIR / "clips"
NATIVE_FPS = 18


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def select_rows(subjects: set[str], activities: set[str],
                trials: set[str], cameras: set[str]) -> list[dict]:
    rows = []
    with MANIFEST.open(newline="") as f:
        for r in csv.DictReader(f):
            if (r["subject"] in subjects and r["activity"] in activities
                    and r["trial"] in trials
                    and r["kind"] in {f"camera{c}" for c in cameras}):
                rows.append(r)
    rows.sort(key=lambda r: (int(r["activity"]), int(r["trial"]),
                             r["kind"]))
    return rows


def assemble_one(zip_path: Path, out_path: Path) -> int:
    """Assemble one clip; returns the frame count. Raises on failure."""
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist()
                       if n.lower().endswith(".png"))
        if not names:
            raise ValueError(f"{zip_path.name}: no PNG frames in zip")
        with tempfile.TemporaryDirectory(prefix="upfall-asm-") as td:
            seq_dir = Path(td)
            for i, name in enumerate(names):
                (seq_dir / f"{i:05d}.png").write_bytes(z.read(name))
            cmd = ["ffmpeg", "-v", "error", "-y",
                   "-framerate", str(NATIVE_FPS),
                   "-i", str(seq_dir / "%05d.png"),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-r", str(NATIVE_FPS), str(out_path)]
            subprocess.run(cmd, check=True, capture_output=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-count_frames", "-show_entries", "stream=nb_read_frames",
         "-of", "csv=p=0", str(out_path)],
        check=True, capture_output=True, text=True)
    n_frames = int(probe.stdout.strip())
    if n_frames != len(names):
        out_path.unlink(missing_ok=True)
        raise ValueError(
            f"{zip_path.name}: assembled {n_frames} frames, "
            f"zip holds {len(names)} PNGs; clip rejected")
    return n_frames


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", default="1")
    ap.add_argument("--activities", default="1,2,3,4,5")
    ap.add_argument("--trials", default="1,2,3")
    ap.add_argument("--cameras", default="1,2")
    ap.add_argument("--force", action="store_true",
                    help="reassemble clips that already exist")
    args = ap.parse_args()
    rows = select_rows(set(args.subjects.split(",")),
                       set(args.activities.split(",")),
                       set(args.trials.split(",")),
                       set(args.cameras.split(",")))
    if not rows:
        print("no manifest rows match the selection")
        return 1
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for r in rows:
        stem = Path(r["filename"]).stem
        zip_path = ZIP_DIR / r["filename"]
        out_path = CLIP_DIR / f"{stem}.mp4"
        if r["status"] != "ok":
            print(f"SKIP {stem}: manifest status is {r['status']!r}")
            failures += 1
            continue
        digest = sha256_of(zip_path)
        if digest != r["sha256"]:
            print(f"SKIP {stem}: sha256 mismatch "
                  f"(manifest {r['sha256'][:12]}…, disk {digest[:12]}…)")
            failures += 1
            continue
        if out_path.exists() and not args.force:
            print(f"OK   {stem}: clip already assembled")
            continue
        try:
            n = assemble_one(zip_path, out_path)
        except Exception as e:
            print(f"FAIL {stem}: {type(e).__name__}: {e}")
            failures += 1
            continue
        print(f"OK   {stem}: assembled {n} frames at {NATIVE_FPS} fps")
    print(f"done: {len(rows) - failures}/{len(rows)} clips in place, "
          f"{failures} skipped/failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
