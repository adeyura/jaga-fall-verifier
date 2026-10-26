"""SAM 3.1 response parsing: streamed Responses output -> instance records.

Transport lives elsewhere (connector helper on the build VM, or a direct
API call with the author's own key). This module owns only the parse:
given the raw SSE stream text of one sam-3.1 image response, produce
per-instance boxes and decoded mask rasters with their pixel areas.

Strictness contract, enforced not promised. Every failure of this
module is a ValueError; no other exception type escapes.
- A non-completed outcome, or any parser diagnostic, raises. Completion
  is enforced by the outcome check; a stream truncated before the
  completed event cannot produce a plausible subset.
- SSE lines are whitelisted: `data:`, `event:`, `id:`, `retry:`,
  comments, and blanks. A malformed `data:` payload raises. The
  `[DONE]` terminator and blank payloads are the only non-JSON data
  payloads allowed. The transport is assumed to deliver one JSON
  object per `data:` line, as the Meta stream observably does.
- An unrecognized record type raises; the parse never silently drops a
  record class it does not know.
- Boxes and masks are collected in two passes. A mask whose object_id
  has no box record raises (no box is ever fabricated), a duplicate box
  raises, and a degenerate box (non-positive extent) raises.
- Duplicate masks for one object keep the highest revision; revisions
  must be mutually comparable (same type) or the parse raises.
  Superseded duplicates are counted in the stats.
- A mask raster whose dimensions differ from its box raises, and the
  raster's value set must be binary (0/1 or 0/255 encodings).
- Masks smaller than config's min_mask_area_px are segmentation noise:
  they are excluded from the instances and counted in the stats, never
  silently treated as people and never silently vanished either.
- Axis features are honest about degeneracy: elongation and tilt are
  None when the mask is too small or too collinear for a principal
  axis to mean anything. None is never encoded as a direction.

Coordinates: pixel centers. A centroid is the mean of (index + 0.5);
bottom_y is the maximum mask row index, and consumers computing a
frame-space bottom edge add 1 (see features.floor_proximity).

This module is synchronous (it drives the parser with asyncio.run);
do not call it from inside a running event loop.
"""
from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass, field

import numpy as np

_SSE_FIELDS = ("data:", "event:", "id:", "retry:", ":")


@dataclass
class Instance:
    object_id: str
    box: tuple[int, int, int, int]          # left, top, right, bottom
    mask_area_px: int
    mask_width: int
    mask_height: int
    centroid_xy: tuple[float, float]        # mask-local, pixel centers
    bottom_y: int                           # lowest mask row, mask-local
    bottom_band_share: float                # share of pixels in base band
    elongation: float | None                # principal-axis ratio, >= 1
    axis_tilt_deg: float | None             # 0 = horizontal, 90 = vertical
    # Box-sized boolean mask, retained only when the caller asks
    # (parse_sam_stream(keep_raster=True)) for overlay rendering.
    # Never serialized; features never read it.
    raster: np.ndarray | None = field(default=None, repr=False,
                                      compare=False)


async def _events_from_sse(text: str):
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(_SSE_FIELDS):
            raise ValueError(
                f"unrecognized SSE line, refusing to skip it: {line[:60]!r}")
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed SSE data line: {e}") from e


def _axis_features(xs: np.ndarray, ys: np.ndarray
                   ) -> tuple[float | None, float | None]:
    """Principal-axis elongation and tilt, or (None, None).

    The axis is reported only when it means something: enough pixels
    and a non-degenerate spread on both axes.
    """
    if len(xs) < 10:
        return None, None
    cov = np.cov(np.stack([xs.astype(float), ys.astype(float)]))
    evals, evecs = np.linalg.eigh(cov)
    lam_min, lam_max = float(evals[0]), float(evals[1])
    if lam_max <= 1e-9:
        return None, None
    vx, vy = float(evecs[0, 1]), float(evecs[1, 1])
    tilt = math.degrees(math.atan2(abs(vy), abs(vx)))  # folds axis to [0, 90]
    if lam_min <= 1e-9:
        # Collinear: a direction exists on paper, but a one-pixel-wide
        # mask carries no body-axis evidence. Report no axis at all
        # rather than a precise-looking tilt built on nothing.
        return None, None
    # Cap the ratio: past ~50 the axis is a line for every consumer
    # this project has, and an uncapped value (hundreds, from a
    # near-degenerate minor axis) is false precision in the record.
    return min(math.sqrt(lam_max / lam_min), 50.0), tilt


def _normalize(fn):
    """Run fn under the module's one-failure-type contract.

    ValueError passes through. Anything else is walked down its cause
    chain: if one of this module's own ValueErrors is inside (the
    stream parser wraps source errors in its own types), that error is
    re-raised so the specific reason survives; otherwise the failure is
    normalized to a ValueError carrying the original as its cause.
    """
    try:
        return fn()
    except ValueError:
        raise
    except Exception as e:
        cur, seen = e, set()
        while cur is not None and id(cur) not in seen:
            seen.add(id(cur))
            if isinstance(cur, ValueError):
                raise cur
            cur = cur.__cause__ or cur.__context__
        raise ValueError(f"SAM stream parse failed: {e}") from e


def parse_sam_stream(text: str, keep_raster: bool = False) -> tuple[list[Instance], dict]:
    """Parse one completed SAM image response.

    Returns (instances, stats). Instances may be empty (a genuine "no
    person segmented" result). Stats surface everything that did not
    become an instance: boxes without masks, text records, superseded
    duplicate masks, and sub-threshold tiny masks, plus the effective
    feature parameters used. A response carrying text records but no
    masks raises, because it cannot be told apart from an error or a
    refusal.
    """
    from meta_sam_parser import (CompletedOutcome, SegmentationBoxRecord,
                                  SegmentationMaskRecord,
                                  SegmentationTextRecord,
                                  decode_mask_to_raster,
                                  image_segmentation_format,
                                  parse_responses_stream)

    async def run():
        parsed = parse_responses_stream(_events_from_sse(text),
                                        image_segmentation_format())
        async with parsed:
            return await parsed.final_result()

    result = _normalize(lambda: asyncio.run(run()))
    if not isinstance(result.outcome, CompletedOutcome):
        raise ValueError(f"SAM response did not complete: {result.outcome}")
    # Termination is evidenced in the stream text, not delegated to
    # the library's say-so: a stream cut before its completion event
    # must not be readable as a completed (possibly empty) result.
    if ('"type":"response.completed"' not in text
            and "data: [DONE]" not in text):
        raise ValueError(
            "SAM stream carries no completion evidence (no "
            "response.completed event and no [DONE] sentinel); "
            "refusing to read a possibly truncated stream as a result")
    if result.diagnostics:
        raise ValueError(f"SAM response carried diagnostics: {result.diagnostics}")

    def collect() -> tuple[list[Instance], dict]:
        boxes: dict[str, tuple[int, int, int, int]] = {}
        masks: dict[str, tuple[object, object]] = {}
        n_text_records = 0
        n_superseded = 0
        for record in result.records:
            if isinstance(record, SegmentationTextRecord):
                n_text_records += 1
            elif isinstance(record, SegmentationBoxRecord):
                oid = str(record.object_id)
                if oid in boxes:
                    raise ValueError(f"duplicate box record for object {oid}")
                if record.right <= record.left or record.bottom <= record.top:
                    raise ValueError(
                        f"degenerate box for object {oid}: "
                        f"{(record.left, record.top, record.right, record.bottom)}")
                boxes[oid] = (record.left, record.top,
                              record.right, record.bottom)
            elif isinstance(record, SegmentationMaskRecord):
                oid = str(record.object_id)
                revision = getattr(record, "revision", None)
                if oid not in masks:
                    masks[oid] = (revision, record)
                    continue
                prev_revision, _ = masks[oid]
                if (revision is None or prev_revision is None
                        or type(revision) is not type(prev_revision)):
                    raise ValueError(
                        f"duplicate mask for object {oid} with revisions "
                        "that cannot be ordered")
                if revision == prev_revision:
                    raise ValueError(
                        f"duplicate mask for object {oid} at the same "
                        f"revision {revision!r}")
                n_superseded += 1
                if revision > prev_revision:
                    masks[oid] = (revision, record)
            else:
                raise ValueError(
                    f"unrecognized SAM record type: {type(record).__name__}")

        if n_text_records and not masks:
            raise ValueError(
                f"SAM response carried {n_text_records} text record(s) and "
                "no masks; refusing to read it as an empty segmentation")

        from .config import FEATURES
        band_frac = FEATURES["bottom_band_frac"]
        min_area = FEATURES["min_mask_area_px"]
        instances: list[Instance] = []
        n_tiny = 0
        for oid, (_, record) in masks.items():
            if oid not in boxes:
                raise ValueError(f"mask for object {oid} has no box record")
            box = boxes[oid]
            box_w, box_h = box[2] - box[0], box[3] - box[1]
            if (record.mask.width, record.mask.height) != (box_w, box_h):
                raise ValueError(
                    f"mask dims {record.mask.width}x{record.mask.height} do "
                    f"not match box dims {box_w}x{box_h} for object {oid}")
            raster = np.frombuffer(decode_mask_to_raster(record.mask),
                                   dtype=np.uint8)
            raster = raster.reshape(record.mask.height, record.mask.width)
            values = set(np.unique(raster).tolist())
            if not values <= {0, 1} and not values <= {0, 255}:
                raise ValueError(
                    f"mask raster for object {oid} is not binary: "
                    f"values {sorted(values)[:6]}")
            ys, xs = np.nonzero(raster)
            if len(xs) == 0:
                raise ValueError("SAM mask record decoded to zero pixels")
            if len(xs) < min_area:
                n_tiny += 1
                continue
            elongation, tilt = _axis_features(xs, ys)
            band_top = record.mask.height * (1.0 - band_frac)
            instances.append(Instance(
                object_id=oid,
                box=box,
                mask_area_px=int(len(xs)),
                mask_width=record.mask.width,
                mask_height=record.mask.height,
                centroid_xy=(float(xs.mean()) + 0.5, float(ys.mean()) + 0.5),
                bottom_y=int(ys.max()),
                bottom_band_share=float((ys >= band_top).mean()),
                elongation=elongation,
                axis_tilt_deg=tilt,
                raster=(raster > 0) if keep_raster else None,
            ))
        stats = {
            "boxes_without_masks": len(set(boxes) - set(masks)),
            "text_records": n_text_records,
            "masks_superseded": n_superseded,
            "tiny_instances": n_tiny,
            "bottom_band_frac": band_frac,
            "min_mask_area_px": min_area,
        }
        return instances, stats

    return _normalize(collect)
