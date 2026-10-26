"""Kinematic features from per-keyframe SAM instances.

The honest label for what this pipeline measures (SPEC.md): person
segmentation plus mask-derived kinematics. There is no pose estimation
anywhere in this system. Features per tracked instance, per keyframe:

- mask area and bounding-box aspect ratio (width / height)
- centroid position, normalized to the frame
- floor proximity: the mask's lowest point relative to the frame height
- centroid speed between keyframes (normalized frame heights per second)
- stillness: maximum centroid displacement inside a trailing window

Instance association across keyframes is local IoU matching on boxes.
An instance that disappears ends its track; a new one starts a new
track. Tracks are evidence, not identities: no claim is made that a
track is the same person after a long occlusion.
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
    centroid_x: float     # normalized 0..1 across frame width
    centroid_y: float     # normalized 0..1 down frame height
    floor_proximity: float  # mask bottom / frame height, 0..1
    speed_hps: float      # centroid speed, frame-heights per second


@dataclass
class Track:
    track_id: int
    frames: list[KeyframeFeatures] = field(default_factory=list)
    last_box: tuple[int, int, int, int] = (0, 0, 0, 0)
    last_t: float = 0.0


def build_tracks(keyframes: list[tuple[float, list[Instance]]],
                 frame_w: int, frame_h: int,
                 iou_threshold: float = 0.2) -> list[Track]:
    """Associate instances across keyframes into tracks by box IoU."""
    tracks: list[Track] = []
    next_id = 0
    for t_s, instances in keyframes:
        unmatched = set(range(len(tracks)))
        for inst in instances:
            best, best_iou = None, iou_threshold
            for i in unmatched:
                v = _iou(inst.box, tracks[i].last_box)
                if v > best_iou:
                    best, best_iou = i, v
            if best is None:
                tracks.append(Track(track_id=next_id))
                next_id += 1
                best = len(tracks) - 1
            else:
                unmatched.discard(best)
            tr = tracks[best]
            cx = (inst.box[0] + inst.centroid_xy[0]) / frame_w
            cy = (inst.box[1] + inst.centroid_xy[1]) / frame_h
            speed = 0.0
            if tr.frames:
                prev = tr.frames[-1]
                dt = t_s - tr.last_t
                if dt > 0:
                    # Displacement in frame-height units, so x and y are
                    # comparable: dx is width-normalized, scale it by the
                    # frame aspect to express it in heights.
                    dx_h = (cx - prev.centroid_x) * (frame_w / frame_h)
                    dy_h = cy - prev.centroid_y
                    speed = (dx_h * dx_h + dy_h * dy_h) ** 0.5 / dt
            tr.frames.append(KeyframeFeatures(
                t_s=t_s,
                area_px=inst.mask_area_px,
                aspect=(inst.box[2] - inst.box[0]) / max(1, inst.box[3] - inst.box[1]),
                centroid_x=cx, centroid_y=cy,
                floor_proximity=(inst.box[1] + inst.bottom_y) / frame_h,
                speed_hps=speed,
            ))
            tr.last_box = inst.box
            tr.last_t = t_s
    return [t for t in tracks if t.frames]


def stillness(track: Track, frame_w: int, frame_h: int,
              window_s: float = 3.0) -> float:
    """Max centroid displacement (frame heights) inside the last window.

    Low stillness values mean the instance barely moved: the post-event
    stillness the rules stage looks for after a descent. Displacement is
    measured in frame-height units, the same scaling as centroid speed.
    """
    if not track.frames:
        return 0.0
    end_t = track.frames[-1].t_s
    aspect = frame_w / frame_h
    pts = [(f.centroid_x * aspect, f.centroid_y) for f in track.frames
           if f.t_s >= end_t - window_s]
    if len(pts) < 2:
        return 0.0
    return max(((x - pts[0][0]) ** 2 + (y - pts[0][1]) ** 2) ** 0.5
               for x, y in pts)
