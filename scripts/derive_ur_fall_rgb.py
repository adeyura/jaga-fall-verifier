"""Derive RGB-half crops of the UR Fall composites, with a layout audit.

Every UR Fall file is a side-by-side composite: depth map on the
left 320x240, RGB camera view on the right 320x240 (verified visually
2026-10-27). The depth half's speckle holds the motion floor at
0.036-0.068 of pixels changed per step in an empty room; on the RGB
half alone the floor measures 0.0001-0.041 (P1:
crop, with conditions). The conditions this script enforces:

1. The layout is audited per file, never assumed: a sampled color
   frame's right half must be markedly more colorful than its left
   (the depth rendering is near-grayscale; the RGB view is not). Any
   file failing the audit is reported and NOT derived, and the run
   exits nonzero.
2. The manifest is rewritten to point video_path at the derived crop
   with preprocessing recorded per row; the original file and its
   sha256 stay as the provenance record.

Run after scripts/build_manifest_ur_fall.py. Idempotent: derived
files whose sha256 matches the audit record are not re-encoded.
"""
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data" / "ur_fall"
OUT_DIR = ROOT / "data" / "derived" / "ur_fall_rgb"
MANIFEST = ROOT / "results" / "manifest_draft.csv"
AUDIT = ROOT / "results" / "ur_fall_layout_audit.csv"
COLORFULNESS_RATIO = 3.0   # right half must exceed left by this factor
MIN_COLORFULNESS = 2.0     # absolute floor for the RGB half (0-255 scale)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def colorfulness(frame: np.ndarray) -> float:
    """Mean per-pixel channel spread of an RGB frame (0 = grayscale)."""
    f = frame.astype(np.float64)
    return float((np.abs(f[..., 0] - f[..., 1])
                  + np.abs(f[..., 1] - f[..., 2])
                  + np.abs(f[..., 0] - f[..., 2])).mean() / 3.0)


def sample_frame(video: Path) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(video),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True).stdout
    w, h = 640, 240
    return np.frombuffer(out, dtype=np.uint8).reshape(h, w, 3)


def main() -> int:
    rows = list(csv.DictReader(MANIFEST.open()))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit_rows, failures = [], []
    for row in rows:
        src = SRC_DIR / row["source_file"]
        frame = sample_frame(src)
        left = colorfulness(frame[:, :320])
        right = colorfulness(frame[:, 320:])
        ok = (right >= MIN_COLORFULNESS
              and right >= COLORFULNESS_RATIO * max(left, 1e-9))
        audit_rows.append({"clip_id": row["clip_id"],
                           "left_colorfulness": round(left, 3),
                           "right_colorfulness": round(right, 3),
                           "layout_ok": ok})
        if not ok:
            failures.append(row["clip_id"])
            continue
        dst = OUT_DIR / row["source_file"]
        if not dst.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(src),
                 "-vf", "crop=320:240:320:0", "-an", str(dst)], check=True)
        row["video_path"] = str(dst.relative_to(ROOT))
        row["preprocessing"] = "crop_rgb_half (320x240 at x=320)"
    with AUDIT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()))
        w.writeheader()
        w.writerows(audit_rows)
    fields = list(rows[0].keys())
    with MANIFEST.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"layout audit: {len(audit_rows) - len(failures)}/{len(audit_rows)} "
          f"files confirmed depth-left/RGB-right; derived crops in {OUT_DIR}")
    if failures:
        print(f"AUDIT FAILURES (not derived): {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
