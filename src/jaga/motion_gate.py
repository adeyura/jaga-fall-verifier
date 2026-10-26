"""Local motion gate: frame differencing before any API call.

Design intent (SPEC.md): most footage never leaves the home. The gate
decodes small grayscale frames, computes mean absolute difference between
consecutive frames, and marks candidate segments where motion exceeds a
threshold. Only candidate segments are worth SAM calls downstream.

Fails loudly: a video that cannot be decoded raises, it is never skipped
silently (denominator integrity starts here).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_W, _H = 160, 90  # gate resolution; small on purpose, this is a pre-filter


def motion_series(video: Path, fps: float = 5.0) -> np.ndarray:
    """Mean absolute pixel difference per frame step, at `fps` sampling."""
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video),
        "-vf", f"fps={fps},scale={_W}:{_H},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    frame_bytes = _W * _H
    n = len(raw) // frame_bytes
    if n < 2:
        raise ValueError(f"{video}: decoded {n} frames, need >= 2")
    frames = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8)
    frames = frames.reshape(n, frame_bytes).astype(np.float32)
    return np.abs(np.diff(frames, axis=0)).mean(axis=1)


@dataclass
class Segment:
    start_s: float
    end_s: float
    peak: float


def candidate_segments(
    series: np.ndarray, fps: float, threshold: float,
    min_len_s: float = 0.4, merge_gap_s: float = 0.6,
) -> list[Segment]:
    """Contiguous above-threshold runs, short gaps merged, short runs dropped."""
    above = series > threshold
    segs: list[Segment] = []
    i = 0
    while i < len(above):
        if not above[i]:
            i += 1
            continue
        j = i
        last_on = i
        while j < len(above) and (above[j] or (j - last_on) / fps <= merge_gap_s):
            if above[j]:
                last_on = j
            j += 1
        if (last_on - i + 1) / fps >= min_len_s:
            segs.append(Segment(i / fps, (last_on + 1) / fps,
                                float(series[i:last_on + 1].max())))
        i = j
    return segs
