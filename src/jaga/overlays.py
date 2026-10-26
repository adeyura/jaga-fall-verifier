"""Overlay evidence rendering (SPEC D3): mask silhouettes over an
aggressively blurred, low-resolution background.

The adjudicator's scored evidence form never carries raw frames.
This module renders, for one keyframe, a PNG in which the person's
mask is a solid tint over a background that has been downscaled by
at least the configured factor (config.EVIDENCE, under the config
hash), box-blurred, and upscaled back — enough scene geometry to
judge a posture claim, not enough detail to identify anyone or
anything. The downscale guarantee holds at every frame width: the
target width is the smaller of the configured maximum and
width // min_downscale.

Pure functions over numpy arrays plus an ffmpeg-backed PNG reader
(the project has no image library; ffmpeg is already the frame
tool). PNG writing is a minimal zlib encoder — the same pattern the
regression suite uses for fixtures.
"""

from __future__ import annotations

import struct
import subprocess
import zlib

import numpy as np

from .config import EVIDENCE

# Background treatment and person tint live in config.EVIDENCE
# (frozen with the spec, under the config hash) — see config.py.


def read_png_rgb(path) -> np.ndarray:
    """Decode a PNG to an (H, W, 3) uint8 array via ffmpeg."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(path)], capture_output=True, text=True)
    if probe.returncode != 0:
        raise ValueError(f"ffprobe failed on {path}: {probe.stderr[:200]}")
    w, h = (int(x) for x in probe.stdout.strip().split(",")[:2])
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"], capture_output=True)
    if raw.returncode != 0:
        raise ValueError(f"ffmpeg could not decode {path}")
    arr = np.frombuffer(raw.stdout, dtype=np.uint8)
    if arr.size != w * h * 3:
        raise ValueError(f"decoded size mismatch for {path}: "
                         f"{arr.size} != {w * h * 3}")
    return arr.reshape(h, w, 3)


def _box_blur(img: np.ndarray, radius: int = 2) -> np.ndarray:
    """Separable box blur with edge padding, radius in pixels."""
    if radius < 1:
        return img
    x = img.astype(np.float32)
    for axis in (1, 0):
        pad = [(0, 0)] * x.ndim
        pad[axis] = (radius, radius)
        xp = np.pad(x, pad, mode="edge")
        c = np.cumsum(xp, axis=axis)
        k = 2 * radius + 1
        hi = np.take(c, range(k - 1, c.shape[axis]), axis=axis)
        lo = np.concatenate(
            [np.zeros_like(np.take(c, [0], axis=axis)),
             np.take(c, range(0, c.shape[axis] - k), axis=axis)],
            axis=axis)
        x = (hi - lo) / k
    return x


def blur_background(frame: np.ndarray, bg_width: int | None = None,
                    passes: int | None = None) -> np.ndarray:
    """Downscale (guaranteed factor), blur, upscale back to frame size.

    Nearest-neighbour resampling both ways: the blockiness is part of
    the privacy treatment, not an artifact to hide.
    """
    if bg_width is None:
        bg_width = EVIDENCE["bg_width"]
    if passes is None:
        passes = EVIDENCE["bg_blur_passes"]
    h, w = frame.shape[:2]
    target = max(8, min(bg_width, w // EVIDENCE["bg_min_downscale"]))
    if w <= target:
        small = frame.astype(np.float32)
    else:
        bh = max(1, round(h * target / w))
        yi = (np.linspace(0, h - 1, bh)).round().astype(int)
        xi = (np.linspace(0, w - 1, target)).round().astype(int)
        small = frame[yi][:, xi].astype(np.float32)
    for _ in range(passes):
        small = _box_blur(small, radius=EVIDENCE["bg_blur_radius"])
    yi = (np.linspace(0, small.shape[0] - 1, h)).round().astype(int)
    xi = (np.linspace(0, small.shape[1] - 1, w)).round().astype(int)
    return np.clip(small[yi][:, xi], 0, 255).astype(np.uint8)


def render_overlay(frame: np.ndarray,
                   masks: list[tuple[np.ndarray, tuple[int, int]]]) -> np.ndarray:
    """Tint each (raster, (left, top)) mask over the blurred frame.

    Rasters are box-sized boolean arrays placed at their box offset;
    a raster that would fall outside the frame raises — a mask that
    does not fit its frame is corrupt evidence, not a clip to trim.
    """
    h, w = frame.shape[:2]
    out = blur_background(frame).astype(np.float32)
    tint = np.array(EVIDENCE["tint"], dtype=np.float32)
    alpha = EVIDENCE["tint_alpha"]
    for raster, (left, top) in masks:
        mh, mw = raster.shape
        if left < 0 or top < 0 or left + mw > w or top + mh > h:
            raise ValueError(
                f"mask placement ({left},{top}) {mw}x{mh} outside "
                f"frame {w}x{h}")
        region = out[top:top + mh, left:left + mw]
        m = raster.astype(bool)[..., None]
        out[top:top + mh, left:left + mw] = np.where(
            m, region * (1 - alpha) + tint * alpha, region)
    return np.clip(out, 0, 255).astype(np.uint8)


def encode_png(rgb: np.ndarray) -> bytes:
    """Minimal PNG encoder for an (H, W, 3) uint8 array."""
    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
            or rgb.ndim != 3 or rgb.shape[2] != 3):
        raise ValueError(
            "encode_png needs a uint8 (H, W, 3) array, got "
            f"{getattr(rgb, 'dtype', type(rgb))} "
            f"{getattr(rgb, 'shape', None)}")
    h, w = rgb.shape[:2]
    rows = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
