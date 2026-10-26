"""Frame sampling for the Jaga pipeline.

Extracts frames from a video at a fixed rate using ffmpeg. Frames are a
local cache artifact only; they are never committed (see .gitignore).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def sample_frames(video: Path, out_dir: Path, fps: float) -> list[tuple[float, Path]]:
    """Extract frames at `fps` into out_dir; return [(timestamp_s, path)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "f_%05d.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video),
         "-vf", f"fps={fps}", str(pattern)],
        check=True,
    )
    frames = sorted(out_dir.glob("f_*.png"))
    return [(i / fps, p) for i, p in enumerate(frames)]


def probe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
