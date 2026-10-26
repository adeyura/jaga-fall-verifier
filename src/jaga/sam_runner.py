"""SAM keyframe runner: keyframes -> SAM 3.1 -> instances -> tracks.

Transport is injected: any callable (image_bytes, prompt) -> raw SSE
stream text. On the build VM the default transport shells out to the
Meta Model API connector helper; the helper is a build-machine detail,
never a pipeline dependency. Prompts and the model name are part of the
cache key, so changing either re-bills honestly instead of silently
reusing a response produced under different conditions.

Caching: a response is written to the cache only after it parses
cleanly, so a bad response can never poison a rerun. A cache entry that
fails to parse raises, loudly, rather than being silently re-billed.

Cost accounting is an estimate from the published rate ($0.0025 per
image) times the images the API reports processing; cache hits bill
zero. The estimate is labeled as such wherever it is reported.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .features import Track, build_tracks
from .sam_parse import Instance, parse_sam_stream

Transport = Callable[[bytes, str], str]

SAM_IMAGE_USD = 0.0025   # published rate, per image processed
DEFAULT_MODEL = "sam-3.1"
DEFAULT_PROMPT = "person"


def helper_transport(helper: Path) -> Transport:
    """Transport that calls the build VM's Meta Model API helper."""
    def _call(image_bytes: bytes, prompt: str) -> str:
        with tempfile.TemporaryDirectory(prefix="jaga-sam-") as td:
            img = Path(td) / "frame.png"
            out = Path(td) / "stream.txt"
            img.write_bytes(image_bytes)
            proc = subprocess.run(
                ["python3", str(helper), "sam-image", "--image", str(img),
                 "--prompt", prompt, "--out", str(out)],
                capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"SAM helper failed ({proc.returncode}): "
                    f"{(proc.stderr or proc.stdout)[-400:]}")
            return out.read_text()
    return _call


def _png_size(path: Path) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"keyframe is not a PNG: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def _images_processed(stream_text: str) -> int:
    m = re.search(r'"images_processed"\s*:\s*(\d+)', stream_text)
    return int(m.group(1)) if m else 1


@dataclass
class KeyframeResult:
    t_s: float
    instances: list[Instance]
    parse_stats: dict
    from_cache: bool
    images_billed: int


@dataclass
class ClipRun:
    clip_id: str
    keyframes: list[KeyframeResult] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    track_stats: dict = field(default_factory=dict)
    frame_w: int = 0
    frame_h: int = 0

    @property
    def anomalies(self) -> dict:
        """Evidence the API returned that did not become instances.

        Boxes without masks, text records, and sub-threshold tiny
        masks. In the scored path any nonzero total fails the clip
        loudly (see SamRunner.fail_on_anomaly): a keyframe where SAM
        saw a person but delivered no usable mask must never be
        scored as "no person."
        """
        out = {"boxes_without_masks": 0, "text_records": 0,
               "tiny_instances": 0}
        for k in self.keyframes:
            for key in out:
                out[key] += k.parse_stats.get(key, 0)
        return out

    @property
    def anomaly_total(self) -> int:
        return sum(self.anomalies.values())

    @property
    def api_calls(self) -> int:
        return sum(1 for k in self.keyframes if not k.from_cache)

    @property
    def cache_hits(self) -> int:
        return sum(1 for k in self.keyframes if k.from_cache)

    @property
    def images_billed(self) -> int:
        return sum(k.images_billed for k in self.keyframes)

    @property
    def est_cost_usd(self) -> float:
        return self.images_billed * SAM_IMAGE_USD

    @property
    def empty_keyframes(self) -> int:
        return sum(1 for k in self.keyframes if not k.instances)

    def to_dict(self) -> dict:
        from .config import config_hash

        def _r(x, n):
            return None if x is None else round(x, n)

        return {
            "clip_id": self.clip_id,
            "config_hash": config_hash(),
            "anomalies": self.anomalies,
            "frame_w": self.frame_w,
            "frame_h": self.frame_h,
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
            "images_billed": self.images_billed,
            "est_cost_usd": round(self.est_cost_usd, 4),
            "empty_keyframes": self.empty_keyframes,
            "track_stats": self.track_stats,
            "keyframes": [{
                "t_s": k.t_s,
                "from_cache": k.from_cache,
                "images_billed": k.images_billed,
                "parse_stats": k.parse_stats,
                "instances": [{
                    "object_id": i.object_id, "box": i.box,
                    "area_px": i.mask_area_px,
                    "elongation": _r(i.elongation, 3),
                    "axis_tilt_deg": _r(i.axis_tilt_deg, 1),
                    "bottom_band_share": round(i.bottom_band_share, 3),
                } for i in k.instances],
            } for k in self.keyframes],
            "tracks": [{
                "track_id": t.track_id,
                "frames": [{
                    "t_s": f.t_s, "area_px": f.area_px,
                    "object_id": f.object_id, "box": f.box,
                    "aspect": round(f.aspect, 3),
                    "elongation": _r(f.elongation, 3),
                    "axis_tilt_deg": _r(f.axis_tilt_deg, 1),
                    "centroid_x": round(f.centroid_x, 4),
                    "centroid_y": round(f.centroid_y, 4),
                    "floor_proximity": round(f.floor_proximity, 4),
                    "bottom_band_share": round(f.bottom_band_share, 3),
                    "speed_hps": f.speed_hps,
                    "vy_hps": f.vy_hps,
                    "dt_s": f.dt_s,
                    "spans_gap": f.spans_gap,
                    "match_iou": f.match_iou,
                } for f in t.frames],
            } for t in self.tracks],
        }


class SamRunner:
    def __init__(self, cache_dir: Path, transport: Transport,
                 model: str = DEFAULT_MODEL, prompt: str = DEFAULT_PROMPT,
                 fail_on_anomaly: bool = True):
        self.cache_dir = Path(cache_dir) / "sam"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.transport = transport
        self.model = model
        self.prompt = prompt
        self.fail_on_anomaly = fail_on_anomaly

    def _cache_path(self, image_bytes: bytes) -> Path:
        key = hashlib.sha256(
            self.model.encode() + b"\0" + self.prompt.encode()
            + b"\0" + image_bytes).hexdigest()
        return self.cache_dir / f"{key}.sse"

    def run_keyframes(self, clip_id: str,
                      frames: list[tuple[float, Path]]) -> ClipRun:
        if not frames:
            raise ValueError("run_keyframes needs at least one frame")
        frame_w, frame_h = _png_size(frames[0][1])
        run = ClipRun(clip_id=clip_id, frame_w=frame_w, frame_h=frame_h)
        track_input: list[tuple[float, list[Instance]]] = []
        for t_s, path in frames:
            image_bytes = path.read_bytes()
            cache_path = self._cache_path(image_bytes)
            if cache_path.exists():
                stream = cache_path.read_text()
                instances, stats = parse_sam_stream(stream)
                run.keyframes.append(KeyframeResult(
                    t_s=t_s, instances=instances, parse_stats=stats,
                    from_cache=True, images_billed=0))
            else:
                stream = self.transport(image_bytes, self.prompt)
                instances, stats = parse_sam_stream(stream)
                cache_path.write_text(stream)
                run.keyframes.append(KeyframeResult(
                    t_s=t_s, instances=instances, parse_stats=stats,
                    from_cache=False,
                    images_billed=_images_processed(stream)))
            track_input.append((t_s, instances))
        run.tracks, run.track_stats = build_tracks(
            track_input, frame_w, frame_h)
        if self.fail_on_anomaly and run.anomaly_total:
            raise ValueError(
                f"{clip_id}: SAM returned evidence that did not become "
                f"instances: {run.anomalies}. Refusing to score this "
                "clip as if that evidence did not exist.")
        return run
