"""Kinematic features from per-keyframe SAM instances.

The honest label for what this pipeline measures (SPEC.md): person
segmentation plus mask-derived kinematics. There is no pose estimation
anywhere in this system. Features per tracked instance, per keyframe:

- mask area, bounding-box aspect ratio, principal-axis elongation and
  tilt (image-space body-extent measures)
- centroid position, normalized to the frame
- floor proximity: the mask's lowest point relative to the frame height
- centroid speed between keyframes (frame heights per second), or None
  on a track's first point, where no speed exists yet
- stillness over a trailing window, or None when the window does not
  hold enough real observation to say anything

View caveat, stated once and binding on every downstream threshold:
these are image-space measures. Their physical meaning depends on the
camera view. A floor-proximity value from a side view and the same value
from a ceiling view are not the same physical quantity, and thresholds
must be fit and reported per view, never pooled.

Association across keyframes is global greedy matching by box IoU
(highest pairs first), and a track survives one missed keyframe before
closing. Tracks are evidence, not identities: no claim is made that a
track is the same person after an occlusion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sam_parse import Instance


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


@dataclass
class KeyframeFeatures:
    t_s: float
    area_px: int
    aspect: float
    elongation: float
    axis_tilt_deg: float
    centroid_x: float     # normalized 0..1 across frame width
    centroid_y: float     # normalized 0..1 down frame height
    floor_proximity: float  # mask bottom / frame height, 0..1
    bottom_band_share: float  # share of mask pixels in its base band
    speed_hps: float | None  # None on a track's first point
    vy_hps: float | None     # signed vertical speed, +down; None likewise


@dataclass
class Track:
    track_id: int
    frames: list[KeyframeFeatures] = field(default_factory=list)
    last_box: tuple[int, int, int, int] = (0, 0, 0, 0)
    last_t: float = 0.0
    missed: int = 0        # consecutive keyframes with no match
    closed: bool = False   # missed too many keyframes to match again


def build_tracks(keyframes: list[tuple[float, list[Instance]]],
                 frame_w: int, frame_h: int,
                 iou_threshold: float | None = None,
                 max_missed: int | None = None) -> tuple[list[Track], dict]:
    """Associate instances across keyframes into tracks.

    Thresholds default to config.FEATURES, which is part of the frozen
    spec and its hash. Returns (tracks, stats). The stats count track
    births and single-keyframe tracks so fragmentation is a reported
    number, not a hidden property of the run. Keyframe times must be
    nondecreasing; a backwards clock raises rather than fabricating
    speeds.
    """
    from .config import FEATURES
    if iou_threshold is None:
        iou_threshold = FEATURES["iou_threshold"]
    if max_missed is None:
        max_missed = FEATURES["max_missed_keyframes"]
    tracks: list[Track] = []
    next_id = 0
    prev_t: float | None = None
    for t_s, instances in keyframes:
        if prev_t is not None and t_s < prev_t:
            raise ValueError(
                f"keyframe times go backwards: {prev_t} then {t_s}")
        prev_t = t_s
        open_tracks = [t for t in tracks if not t.closed]
        pairs = []
        for ii, inst in enumerate(instances):
            for tr in open_tracks:
                v = _iou(inst.box, tr.last_box)
                if v >= iou_threshold:
                    pairs.append((v, ii, tr.track_id))
        pairs.sort(reverse=True)
        used_inst: set[int] = set()
        used_track: set[int] = set()
        assignment: dict[int, Track] = {}
        by_id = {t.track_id: t for t in open_tracks}
        for _v, ii, tid in pairs:
            if ii in used_inst or tid in used_track:
                continue
            used_inst.add(ii)
            used_track.add(tid)
            assignment[ii] = by_id[tid]
        for tr in open_tracks:
            if tr.track_id not in used_track:
                tr.missed += 1
                if tr.missed > max_missed:
                    tr.closed = True
        for ii, inst in enumerate(instances):
            tr = assignment.get(ii)
            if tr is None:
                tr = Track(track_id=next_id)
                next_id += 1
                tracks.append(tr)
            cx = (inst.box[0] + inst.centroid_xy[0]) / frame_w
            cy = (inst.box[1] + inst.centroid_xy[1]) / frame_h
            speed: float | None = None
            vy: float | None = None
            if tr.frames:
                prev = tr.frames[-1]
                dt = t_s - tr.last_t
                if dt > 0:
                    dx_h = (cx - prev.centroid_x) * (frame_w / frame_h)
                    dy_h = cy - prev.centroid_y
                    speed = (dx_h * dx_h + dy_h * dy_h) ** 0.5 / dt
                    vy = dy_h / dt
            tr.frames.append(KeyframeFeatures(
                t_s=t_s,
                area_px=inst.mask_area_px,
                aspect=(inst.box[2] - inst.box[0]) / max(1, inst.box[3] - inst.box[1]),
                elongation=inst.elongation,
                axis_tilt_deg=inst.axis_tilt_deg,
                centroid_x=cx, centroid_y=cy,
                floor_proximity=(inst.box[1] + inst.bottom_y) / frame_h,
                bottom_band_share=inst.bottom_band_share,
                speed_hps=speed,
                vy_hps=vy,
            ))
            tr.last_box = inst.box
            tr.last_t = t_s
            tr.missed = 0
    live = [t for t in tracks if t.frames]
    stats = {
        "tracks_total": len(live),
        "single_keyframe_tracks": sum(1 for t in live if len(t.frames) == 1),
    }
    return live, stats


def stillness(track: Track, frame_w: int, frame_h: int,
              window_s: float | None = None,
              min_span_s: float | None = None,
              after_s: float | None = None) -> float | None:
    """Max pairwise centroid displacement (frame heights) in the window.

    The window is the trailing window_s of the track, optionally
    restricted to frames at or after after_s. The restriction matters:
    stillness is a claim about the period after an event, and a window
    that reaches back across the descent itself would read the fall as
    movement and condemn every real fall on a short track.

    Returns None when the window holds fewer than two observations or
    they span less than min_span_s of real time. Unknown is reported as
    unknown: a fragmented or newborn track must never read as still.
    Displacement is in frame-height units, the same scaling as speed.
    Window defaults come from config.FEATURES.
    """
    from .config import FEATURES
    if window_s is None:
        window_s = FEATURES["stillness_window_s"]
    if min_span_s is None:
        min_span_s = FEATURES["stillness_min_span_s"]
    if not track.frames:
        return None
    end_t = track.frames[-1].t_s
    start_t = end_t - window_s
    if after_s is not None:
        start_t = max(start_t, after_s)
    pts = [(f.centroid_x * (frame_w / frame_h), f.centroid_y, f.t_s)
           for f in track.frames if f.t_s >= start_t]
    if len(pts) < 2 or pts[-1][2] - pts[0][2] < min_span_s:
        return None
    best = 0.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) ** 0.5
            best = max(best, d)
    return best
