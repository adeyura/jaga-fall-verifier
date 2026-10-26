"""Dense local descent timing from the motion signal.

Why this module exists: the fall rules discriminate partly on descent
duration (roughly 0.4 to 1.0 s for a real descent, slower for an
intentional lie-down), and SAM keyframes at 2 fps put zero to two
samples inside that window. Descent duration cannot be measured at
keyframe rate. It is measured here, locally, from the shape of the
motion envelope at up to 30 fps.

What the signal actually is (v2, after v1 was falsified on real clips):
the primary series is the changed-area fraction: the share of pixels
whose absolute frame difference exceeds a gray-level threshold. A fall
is a fast, large-area change: the envelope spikes and collapses. A walk
is sustained moderate area; a lie-down is a longer, lower hump. Descent
onset, offset, and duration come from a hysteresis run over that
envelope, with thresholds set relative to the clip's own floor
(median) and 95th percentile, because real clips have a nonzero noise
floor and rarely contain true stillness.

The difference-weighted centroid height is carried as a diagnostic
trace only. It is NOT a body centroid: it sits wherever change is
concentrated, moves mostly horizontally for a walking person, and in
ceiling views need not move downward during a fall at all. It never
gates an interval. Posture evidence comes from SAM keyframes bracketing
the interval, not from this module.

Intervals are reported, not verdicts; the rules stage decides what an
interval means. Timing estimates must be validated against annotated
clips before any number from this module is quoted (SPEC.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import GATE, TIMING
from .motion_gate import _decode


def series_from_video(video: Path,
                      fps: float = TIMING["decode_fps"]
                      ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Per-step (energy, changed-area fraction, centroid_y) at decode rate.

    Step i describes the change from frame i to frame i+1; its time is
    (i + 1) / fps. centroid_y is normalized 0..1 down the frame and is
    NaN on steps with zero motion.
    """
    frames = _decode(video, fps, GATE["width"], GATE["height"])
    frames = frames.reshape(len(frames), GATE["height"], GATE["width"])
    diffs = np.abs(np.diff(frames, axis=0))
    energy = diffs.mean(axis=(1, 2))
    area_frac = (diffs > TIMING["area_diff_threshold"]).mean(axis=(1, 2))
    rows = np.arange(GATE["height"], dtype=np.float32)
    row_mass = diffs.sum(axis=2)                       # (steps, height)
    total = row_mass.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        centroid_y = (row_mass @ rows) / np.maximum(total, 1e-9) \
            / GATE["height"]
    centroid_y = np.where(total > 0, centroid_y, np.nan)
    return energy, area_frac, centroid_y, fps


def _smooth(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x.copy()
    # Edge padding, never zero padding: a zero-pulled edge would fake a
    # signal spike at both ends of every clip.
    pad = win // 2
    padded = np.pad(x, (pad, win - 1 - pad), mode="edge")
    kernel = np.ones(win, dtype=np.float64) / win
    return np.convolve(padded, kernel, mode="valid")


@dataclass
class Interval:
    onset_s: float
    offset_s: float
    duration_s: float
    peak_area_frac: float
    peak_energy: float
    peak_vy_hps: float      # diagnostic only, never a gate
    net_centroid_drop: float  # diagnostic only, never a gate


@dataclass
class TimingResult:
    intervals: list[Interval]
    descent: Interval | None    # strongest interval in duration bounds
    floor: float
    scale_p95: float
    fps: float


def analyze(energy: np.ndarray, area_frac: np.ndarray,
            centroid_y: np.ndarray, fps: float,
            params: dict | None = None) -> TimingResult:
    """Find descent candidate intervals in a per-step motion series."""
    p = dict(TIMING)
    if params:
        p.update(params)
    n = len(area_frac)
    if n == 0:
        return TimingResult([], None, 0.0, 0.0, fps)
    win = max(1, int(round(p["smooth_s"] * fps)))
    af = _smooth(area_frac.astype(np.float64), win)
    e = _smooth(energy.astype(np.float64), win)
    cy = centroid_y.astype(np.float64).copy()
    known = ~np.isnan(cy)
    if known.any():
        idx = np.arange(n)
        cy = _smooth(np.interp(idx, idx[known], cy[known]), win)
        vy = np.gradient(cy) * fps
    else:
        vy = np.zeros(n)
    floor = float(np.median(af))
    scale = float(np.percentile(af, 95))
    span = scale - floor
    if span <= 0:
        return TimingResult([], None, floor, scale, fps)
    high = floor + p["burst_high_frac"] * span
    low = floor + p["burst_low_frac"] * span
    active = af > low
    intervals: list[Interval] = []
    i = 0
    while i < n:
        if not active[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and active[j + 1]:
            j += 1
        if af[i:j + 1].max() > high:
            intervals.append(Interval(
                onset_s=i / fps, offset_s=(j + 1) / fps,
                duration_s=(j + 1 - i) / fps,
                peak_area_frac=float(af[i:j + 1].max()),
                peak_energy=float(e[i:j + 1].max()),
                peak_vy_hps=float(vy[i:j + 1].max()),
                net_centroid_drop=float(cy[j] - cy[i])))
        i = j + 1
    in_bounds = [iv for iv in intervals
                 if p["min_duration_s"] <= iv.duration_s
                 <= p["max_duration_s"]]
    descent = max(in_bounds, key=lambda iv: iv.peak_area_frac, default=None)
    return TimingResult(intervals, descent, floor, scale, fps)


def timing_from_video(video: Path) -> TimingResult:
    energy, area_frac, centroid_y, fps = series_from_video(video)
    return analyze(energy, area_frac, centroid_y, fps)
