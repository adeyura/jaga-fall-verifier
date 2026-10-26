"""Local motion gate: frame differencing before any API call.

Design intent (SPEC.md): most footage never leaves the home. The gate
decodes small grayscale frames and marks candidate segments using two
channels:
- consecutive-frame difference (fast movement), and
- background difference against a rolling reference (slow descents and
  collapses that spread their change across steps and would slip under a
  consecutive-only threshold).

Segments are padded by the spec's candidate window (-2 s / +4 s) before
being handed downstream, because the post-event stillness window is the
most discriminative evidence and must not be amputated at this stage.

Denominator discipline: per-clip gate statistics are always returned
(segments kept, short runs dropped, seconds flagged, zero-candidate
flag). A fall clip that yields zero candidates is a visible gate miss,
never a silent system negative. A video that cannot be decoded raises.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import GATE
from .frames import probe_duration


def _decode(video: Path, fps: float, width: int, height: int) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video),
        "-vf", f"fps={fps},scale={width}:{height},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    frame_bytes = width * height
    n = len(raw) // frame_bytes
    if n < 2:
        raise ValueError(f"{video}: decoded {n} frames, need >= 2")
    # Reconcile against the container duration: ffmpeg can exit 0 while
    # skipping corrupt packets, which would shorten the series and bury
    # every later event. A GROSS mismatch raises. The tolerance (max of 2
    # frames or 10%) is a VFR allowance, named as an accepted risk in
    # SPEC.md — it is not a guarantee against small tail losses.
    expected = probe_duration(video) * fps
    if abs(n - expected) > max(2, 0.1 * expected):
        raise ValueError(
            f"{video}: decoded {n} frames at {fps} fps, expected ~{expected:.0f}; "
            "refusing a silently shortened motion series")
    frames = np.frombuffer(raw[: n * frame_bytes], dtype=np.uint8)
    return frames.reshape(n, frame_bytes).astype(np.float32)


def motion_series(video: Path, fps: float = GATE["sample_fps"]) -> np.ndarray:
    """Consecutive-frame mean absolute difference per step."""
    frames = _decode(video, fps, GATE["width"], GATE["height"])
    return np.abs(np.diff(frames, axis=0)).mean(axis=1)


def background_series(video: Path, fps: float = GATE["sample_fps"],
                      ref_window_s: float = GATE["bg_ref_window_s"]) -> np.ndarray:
    """Per-step difference of each new frame vs a rolling-median reference.

    Catches slow, spread-out motion (a slide or collapse) whose per-step
    change never crosses the consecutive threshold on its own. Aligned
    with motion_series: entry i describes the step from frame i to i+1,
    comparing frame i+1 against the median of the frames before it.
    """
    frames = _decode(video, fps, GATE["width"], GATE["height"])
    win = max(1, int(ref_window_s * fps))
    out = np.zeros(len(frames) - 1, dtype=np.float32)
    for i in range(len(frames) - 1):
        lo = max(0, i + 1 - win)
        ref = np.median(frames[lo:i + 1], axis=0)
        out[i] = np.abs(frames[i + 1] - ref).mean()
    return out


@dataclass
class Segment:
    start_s: float
    end_s: float
    peak: float


@dataclass
class GateStats:
    segments_kept: int = 0
    runs_dropped_short: int = 0
    seconds_flagged: float = 0.0
    zero_candidate: bool = True
    peak_motion: float = 0.0


def _runs(above: np.ndarray, fps: float, merge_gap_s: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
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
        runs.append((i, last_on))
        i = j
    return runs


def candidate_segments(
    series: np.ndarray, fps: float,
    threshold: float = GATE["diff_threshold"],
    min_len_s: float = GATE["min_len_s"],
    merge_gap_s: float = GATE["merge_gap_s"],
    pad_pre_s: float = GATE["pad_pre_s"],
    pad_post_s: float = GATE["pad_post_s"],
    *,
    duration_s: float,
) -> tuple[list[Segment], GateStats]:
    """Above-threshold runs, padded by the candidate window, overlaps merged.

    Returns (segments, stats). Dropped short runs are counted in stats,
    never silently discarded. Note: the minimum-length test measures the
    full run span including merged quiet gaps, so two short bursts joined
    by a merge pass jointly — a deliberate choice, since the gate's job is
    generous candidate selection, not precise event boundaries.
    """
    stats = GateStats(peak_motion=float(series.max()) if len(series) else 0.0)
    segs: list[Segment] = []
    for (a, b) in _runs(series > threshold, fps, merge_gap_s):
        if (b - a + 1) / fps < min_len_s:
            stats.runs_dropped_short += 1
            continue
        start = max(0.0, a / fps - pad_pre_s)
        end = min((b + 1) / fps + pad_post_s, duration_s)
        peak = float(series[a:b + 1].max())
        if segs and start <= segs[-1].end_s:  # overlap after padding: merge
            segs[-1].end_s = max(segs[-1].end_s, end)
            segs[-1].peak = max(segs[-1].peak, peak)
        else:
            segs.append(Segment(start, end, peak))
    stats.segments_kept = len(segs)
    stats.seconds_flagged = sum(s.end_s - s.start_s for s in segs)
    stats.zero_candidate = len(segs) == 0
    return segs, stats


def gate_clip(video: Path, duration_s: float) -> tuple[list[Segment], GateStats]:
    """Full gate for one clip: a step is a candidate if EITHER channel fires.

    Each channel is normalized by its own threshold, so a combined value
    above 1.0 means at least one channel crossed its frozen threshold.
    """
    fps = GATE["sample_fps"]
    consec = motion_series(video, fps) / GATE["diff_threshold"]
    bg = background_series(video, fps) / GATE["bg_threshold"]
    if len(consec) != len(bg):
        raise ValueError(
            f"{video}: channel length mismatch ({len(consec)} vs {len(bg)}); "
            "refusing to silently truncate the candidate tail")
    combined = np.maximum(consec, bg)
    return candidate_segments(combined, fps, threshold=1.0,
                              duration_s=duration_s)
