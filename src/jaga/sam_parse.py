"""SAM 3.1 response parsing: streamed Responses output -> instance records.

Transport lives elsewhere (connector helper on the build VM, or a direct
API call with the author's own key). This module owns only the parse:
given the raw SSE stream text of one sam-3.1 image response, produce
per-instance boxes and decoded mask rasters with their pixel areas.

Fails loudly: a non-completed outcome, any parser diagnostic, or a mask
record whose raster does not decode raises. Nothing is dropped quietly.
"""
from __future__ import annotations

import asyncio
import json
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


async def _events_from_sse(text: str):
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                yield json.loads(line[5:])
            except json.JSONDecodeError:
                continue


def parse_sam_stream(text: str) -> list[Instance]:
    """Parse one completed SAM image response. Returns instances (may be [])."""
    from meta_sam_parser import (CompletedOutcome, SegmentationMaskRecord,
                                  decode_mask_to_raster,
                                  image_segmentation_format,
                                  parse_responses_stream)

    async def run():
        parsed = parse_responses_stream(_events_from_sse(text),
                                        image_segmentation_format())
        async with parsed:
            return await parsed.final_result()

    result = asyncio.run(run())
    if not isinstance(result.outcome, CompletedOutcome):
        raise ValueError(f"SAM response did not complete: {result.outcome}")
    if result.diagnostics:
        raise ValueError(f"SAM response carried diagnostics: {result.diagnostics}")

    boxes: dict[str, tuple[int, int, int, int]] = {}
    instances: list[Instance] = []
    for record in result.records:
        if record.__class__.__name__ == "SegmentationBoxRecord":
            boxes[str(record.object_id)] = (record.left, record.top,
                                            record.right, record.bottom)
        elif isinstance(record, SegmentationMaskRecord):
            raster = np.frombuffer(decode_mask_to_raster(record.mask),
                                   dtype=np.uint8)
            raster = raster.reshape(record.mask.height, record.mask.width)
            ys, xs = np.nonzero(raster)
            if len(xs) == 0:
                raise ValueError("SAM mask record decoded to zero pixels")
            oid = str(record.object_id)
            instances.append(Instance(
                object_id=oid,
                box=boxes.get(oid, (0, 0, record.mask.width, record.mask.height)),
                mask_area_px=int(len(xs)),
                mask_width=record.mask.width,
                mask_height=record.mask.height,
                centroid_xy=(float(xs.mean()), float(ys.mean())),
                bottom_y=int(ys.max()),
            ))
    return instances
