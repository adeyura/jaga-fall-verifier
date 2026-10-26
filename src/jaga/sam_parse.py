"""SAM 3.1 response parsing: streamed Responses output -> instance records.

Transport lives elsewhere (connector helper on the build VM, or a direct
API call with the author's own key). This module owns only the parse:
given the raw SSE stream text of one sam-3.1 image response, produce
per-instance boxes and decoded mask rasters with their pixel areas.

Strictness contract, enforced not promised:
- A non-completed outcome, or any parser diagnostic, raises.
- A malformed `data:` line raises. The stream's `[DONE]` terminator and
  blank payloads are the only non-JSON lines allowed.
- Boxes and masks are collected in two passes. A mask whose object_id
  has no box record raises (no box is ever fabricated), and a duplicate
  box for one object raises.
- Duplicate masks for one object keep the highest revision. Duplicates
  with no revision, or tied revisions, raise.
- A mask raster whose dimensions differ from its box raises, because
  every frame-space feature depends on the raster being the box crop.
"""
from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Instance:
    object_id: str
    box: tuple[int, int, int, int]          # left, top, right, bottom
    mask_area_px: int
    mask_width: int
    mask_height: int
    centroid_xy: tuple[float, float]        # in mask-local pixel coords
    bottom_y: int                           # lowest mask row, mask-local
    bottom_band_share: float                # share of pixels in the base band
    elongation: float                       # principal-axis ratio, >= 1
    axis_tilt_deg: float                    # 0 = horizontal, 90 = vertical


async def _events_from_sse(text: str):
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed SSE data line: {e}") from e


def _axis_features(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Principal-axis elongation and tilt from mask pixel coordinates."""
    if len(xs) < 2:
        return 1.0, 0.0
    cov = np.cov(np.stack([xs.astype(float), ys.astype(float)]))
    evals, evecs = np.linalg.eigh(cov)
    lam_min, lam_max = float(evals[0]), float(evals[1])
    elongation = math.sqrt(lam_max / lam_min) if lam_min > 1e-9 else float("inf")
    vx, vy = float(evecs[0, 1]), float(evecs[1, 1])
    tilt = math.degrees(math.atan2(abs(vy), abs(vx)))  # folds axis to [0, 90]
    return elongation, tilt


def parse_sam_stream(text: str) -> tuple[list[Instance], dict]:
    """Parse one completed SAM image response.

    Returns (instances, stats). Instances may be empty (a genuine "no
    person segmented" result). Stats surface what did not become an
    instance: boxes that arrived without masks, and text records. A
    response carrying text records but no masks raises, because it
    cannot be told apart from an error or refusal.
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

    try:
        result = asyncio.run(run())
    except ValueError:
        raise
    except Exception as e:
        # The parser wraps source errors, including this module's own
        # ValueError from _events_from_sse, in its error types. Unwrap
        # ours if it is in the chain; normalize anything else to
        # ValueError, so callers handle exactly one failure type.
        cur, seen = e, set()
        while cur is not None and id(cur) not in seen:
            seen.add(id(cur))
            if isinstance(cur, ValueError):
                raise cur
            cur = cur.__cause__ or cur.__context__
        raise ValueError(f"SAM stream parse failed: {e}") from e
    if not isinstance(result.outcome, CompletedOutcome):
        raise ValueError(f"SAM response did not complete: {result.outcome}")
    if result.diagnostics:
        raise ValueError(f"SAM response carried diagnostics: {result.diagnostics}")

    boxes: dict[str, tuple[int, int, int, int]] = {}
    masks: dict[str, tuple[int, object]] = {}   # object_id -> (revision, record)
    n_text_records = 0
    for record in result.records:
        if isinstance(record, SegmentationTextRecord):
            n_text_records += 1
        elif isinstance(record, SegmentationBoxRecord):
            oid = str(record.object_id)
            if oid in boxes:
                raise ValueError(f"duplicate box record for object {oid}")
            boxes[oid] = (record.left, record.top, record.right, record.bottom)
        elif isinstance(record, SegmentationMaskRecord):
            oid = str(record.object_id)
            revision = getattr(record, "revision", None)
            if oid not in masks:
                masks[oid] = (revision, record)
                continue
            prev_revision, _ = masks[oid]
            if revision is None or prev_revision is None or revision == prev_revision:
                raise ValueError(
                    f"duplicate mask for object {oid} with no usable revision")
            if revision > prev_revision:
                masks[oid] = (revision, record)

    if n_text_records and not masks:
        raise ValueError(
            f"SAM response carried {n_text_records} text record(s) and no "
            "masks; refusing to read it as an empty segmentation")

    from .config import FEATURES
    band_frac = FEATURES["bottom_band_frac"]
    instances: list[Instance] = []
    for oid, (_, record) in masks.items():
        if oid not in boxes:
            raise ValueError(f"mask for object {oid} has no box record")
        box = boxes[oid]
        box_w, box_h = box[2] - box[0], box[3] - box[1]
        if (record.mask.width, record.mask.height) != (box_w, box_h):
            raise ValueError(
                f"mask dims {record.mask.width}x{record.mask.height} do not "
                f"match box dims {box_w}x{box_h} for object {oid}")
        raster = np.frombuffer(decode_mask_to_raster(record.mask),
                               dtype=np.uint8)
        raster = raster.reshape(record.mask.height, record.mask.width)
        ys, xs = np.nonzero(raster)
        if len(xs) == 0:
            raise ValueError("SAM mask record decoded to zero pixels")
        elongation, tilt = _axis_features(xs, ys)
        band_top = record.mask.height * (1.0 - band_frac)
        instances.append(Instance(
            object_id=oid,
            box=box,
            mask_area_px=int(len(xs)),
            mask_width=record.mask.width,
            mask_height=record.mask.height,
            centroid_xy=(float(xs.mean()), float(ys.mean())),
            bottom_y=int(ys.max()),
            bottom_band_share=float((ys >= band_top).mean()),
            elongation=elongation,
            axis_tilt_deg=tilt,
        ))
    stats = {
        "boxes_without_masks": len(set(boxes) - set(masks)),
        "text_records": n_text_records,
    }
    return instances, stats
