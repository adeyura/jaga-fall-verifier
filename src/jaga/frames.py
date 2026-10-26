"""Frame sampling for the Jaga pipeline.

Extracts frames from a video at a fixed rate using ffmpeg. Extracted
frames are derivative media: they belong only in the ignored cache
(see .gitignore), never loose in the repo. This module enforces that.

Fails loudly: zero extracted frames, or a frame count far from
duration x fps (decoder drops compressing the timeline), raises.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _check_cache_dir(out_dir: Path) -> None:
    resolved = out_dir.resolve()
    parts = set(resolved.parts)
    if "cache" not in parts and "tmp" not in parts:
        raise ValueError(
            f"refusing to extract frames outside a cache/ or tmp/ path: {out_dir}")
    # sample_frames clears its target before extracting, so the target must
    # be a dedicated per-clip leaf, never a shared cache root itself.
    if resolved.name in ("cache", "tmp"):
        raise ValueError(
            f"refusing to clear a shared cache root: {out_dir}; "
            "pass a per-clip subdirectory")
    if resolved.exists() and any(p.is_dir() for p in resolved.iterdir()):
        raise ValueError(
            f"refusing to clear {out_dir}: it contains subdirectories, "
            "so it does not look like a dedicated per-clip directory")


def sample_frames(video: Path, out_dir: Path, fps: float) -> list[tuple[float, Path]]:
    """Extract frames at `fps` into a FRESH out_dir; return [(timestamp_s, path)].

    Timestamps come from frame index at the requested rate; the count
    assertion below bounds the drift this can hide. Callers aligning to
    ground truth must treat timestamps as approximate to one sample step.
    """
    _check_cache_dir(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)  # no stale frames from earlier runs, ever
    out_dir.mkdir(parents=True)
    pattern = out_dir / "f_%05d.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video),
         "-vf", f"fps={fps}", str(pattern)],
        check=True,
    )
    frames = sorted(out_dir.glob("f_*.png"),
                    key=lambda p: int(p.stem.split("_")[1]))
    if not frames:
        raise ValueError(f"{video}: extraction produced zero frames")
    expected = probe_duration(video) * fps
    if abs(len(frames) - expected) > max(2, 0.1 * expected):
        raise ValueError(
            f"{video}: extracted {len(frames)} frames, expected ~{expected:.0f}; "
            "decoder drops or VFR would corrupt the timeline")
    return [(i / fps, p) for i, p in enumerate(frames)]


def probe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
