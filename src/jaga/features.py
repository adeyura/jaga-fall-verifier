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
    object_id: str
    box: tuple[int, int, int, int]
    area_px: int
    aspect: float
    elongation: float | None
    axis_tilt_deg: float | None
    centroid_x: float     # normalized 0..1 across frame width
    centroid_y: float     # normalized 0..1 down frame height
    floor_proximity: float  # mask bottom edge / frame height, 0..1
    bottom_band_share: float  # share of mask pixels in its base band
    speed_hps: float | None  # None on a track's first point
    vy_hps: float | None     # signed vertical speed, +down; None likewise
    dt_s: float | None       # gap since the track's previous point
    spans_gap: bool          # this point follows a missed keyframe
    match_iou: float | None  # winning association IoU; None at birth


@dataclass
class Track:
    track_id: int
    frame_w: int = 0
    frame_h: int = 0
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
    import math
    if not (math.isfinite(frame_w) and math.isfinite(frame_h)
            and frame_w > 0 and frame_h > 0):
        raise ValueError(
            f"frame dimensions must be positive and finite: "
            f"{frame_w}x{frame_h}")
    if iou_threshold is None:
        iou_threshold = FEATURES["iou_threshold"]
    if max_missed is None:
        max_missed = FEATURES["max_missed_keyframes"]
    if not (0.0 < iou_threshold <= 1.0) or max_missed < 0:
        raise ValueError(
            f"invalid association parameters: iou_threshold="
            f"{iou_threshold}, max_missed={max_missed}")
    for t_s, instances in keyframes:
        for inst in instances:
            left, top, right, bottom = inst.box
            if right <= left or bottom <= top:
                raise ValueError(
                    f"degenerate box for instance {inst.object_id}: "
                    f"{inst.box}")
            if left < 0 or top < 0 or right > frame_w or bottom > frame_h:
                raise ValueError(
                    f"box for instance {inst.object_id} lies outside "
                    f"the {frame_w}x{frame_h} frame: {inst.box}")
    tracks: list[Track] = []
    next_id = 0
    prev_t: float | None = None
    n_instances = 0
    n_matched = 0
    n_gap_points = 0
    for t_s, instances in keyframes:
        if not math.isfinite(t_s):
            raise ValueError(f"keyframe time is not finite: {t_s}")
        if prev_t is not None and t_s < prev_t:
            raise ValueError(
                f"keyframe times go backwards: {prev_t} then {t_s}")
        prev_t = t_s
        n_instances += len(instances)
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
        assignment: dict[int, tuple[Track, float]] = {}
        by_id = {t.track_id: t for t in open_tracks}
        for v, ii, tid in pairs:
            if ii in used_inst or tid in used_track:
                continue
            used_inst.add(ii)
            used_track.add(tid)
            assignment[ii] = (by_id[tid], v)
        for tr in open_tracks:
            if tr.track_id not in used_track:
                tr.missed += 1
                if tr.missed > max_missed:
                    tr.closed = True
        for ii, inst in enumerate(instances):
            got = assignment.get(ii)
            match_iou: float | None = None
            spans_gap = False
            dt_s: float | None = None
            if got is None:
                tr = Track(track_id=next_id, frame_w=frame_w,
                           frame_h=frame_h)
                next_id += 1
                tracks.append(tr)
            else:
                tr, match_iou = got
                n_matched += 1
                spans_gap = tr.missed > 0
                dt_s = t_s - tr.last_t
                if spans_gap:
                    n_gap_points += 1
            cx = (inst.box[0] + inst.centroid_xy[0]) / frame_w
            cy = (inst.box[1] + inst.centroid_xy[1]) / frame_h
            if not (math.isfinite(cx) and math.isfinite(cy)):
                raise ValueError(
                    f"non-finite centroid for instance {inst.object_id} "
                    f"at t={t_s}")
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
                object_id=inst.object_id,
                box=inst.box,
                area_px=inst.mask_area_px,
                aspect=(inst.box[2] - inst.box[0]) / max(1, inst.box[3] - inst.box[1]),
                elongation=inst.elongation,
                axis_tilt_deg=inst.axis_tilt_deg,
                centroid_x=cx, centroid_y=cy,
                floor_proximity=(inst.box[1] + inst.bottom_y + 1) / frame_h,
                bottom_band_share=inst.bottom_band_share,
                speed_hps=speed,
                vy_hps=vy,
                dt_s=dt_s,
                spans_gap=spans_gap,
                match_iou=match_iou,
            ))
            tr.last_box = inst.box
            tr.last_t = t_s
            tr.missed = 0
    live = [t for t in tracks if t.frames]
    stats = {
        "tracks_total": len(live),
        "single_keyframe_tracks": sum(1 for t in live if len(t.frames) == 1),
        "instances_total": n_instances,
        "instances_matched": n_matched,
        "instances_new_tracks": n_instances - n_matched,
        "points_spanning_gap": n_gap_points,
        "iou_threshold": iou_threshold,
        "max_missed_keyframes": max_missed,
    }
    return live, stats


def stillness(track: Track, frame_w: int | None = None,
              frame_h: int | None = None,
              window_s: float | None = None,
              min_span_s: float | None = None,
              max_gap_s: float | None = None,
              after_s: float | None = None) -> float | None:
    """Max pairwise centroid displacement (frame heights) in the window.

    The window is the trailing window_s of the track, optionally
    restricted to frames at or after after_s. The restriction matters:
    stillness is a claim about the period after an event, and a window
    that reaches back across the descent itself would read the fall as
    movement and condemn every real fall on a short track.

    Returns None when the evidence cannot support a stillness claim:
    fewer than two observations, an observed span shorter than
    min_span_s, or an unobserved gap longer than max_gap_s inside the
    span (two identical centroids with an unobserved interval between
    them prove nothing about the interval). Unknown is reported as
    unknown: a fragmented or newborn track must never read as still.
    Frame dimensions default to the ones the track was built with; a
    caller passing different dimensions raises, because silently
    rescaling evidence is how plausible wrong numbers are born.
    Displacement is in frame-height units, the same scaling as speed.
    Window defaults come from config.FEATURES.
    """
    from .config import FEATURES
    import math
    if frame_w is None:
        frame_w = track.frame_w
    if frame_h is None:
        frame_h = track.frame_h
    if track.frame_w and (frame_w != track.frame_w
                          or frame_h != track.frame_h):
        raise ValueError(
            f"stillness called with {frame_w}x{frame_h} but the track "
            f"was built at {track.frame_w}x{track.frame_h}")
    if not (frame_w and frame_h and frame_w > 0 and frame_h > 0):
        raise ValueError("stillness needs positive frame dimensions")
    if window_s is None:
        window_s = FEATURES["stillness_window_s"]
    if min_span_s is None:
        min_span_s = FEATURES["stillness_min_span_s"]
    if max_gap_s is None:
        max_gap_s = FEATURES["stillness_max_gap_s"]
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
    for a, b in zip(pts, pts[1:]):
        if b[2] - a[2] > max_gap_s:
            return None
    best = 0.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) ** 0.5
            if not math.isfinite(d):
                raise ValueError("non-finite centroid in stillness window")
            best = max(best, d)
    return best
