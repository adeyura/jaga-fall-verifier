#!/usr/bin/env python3
"""Render the worked example's per-keyframe evidence trace figure.

Reads the dev-set gate run's per-clip record for
``le2i_coffee-room-01_video-02`` (the same record
``results/sam_ablation_dev_2026-11-01/worked_example.md`` traces) and
plots what the rules actually read on the winning track: the SAM
mask's axis tilt and bounding-box aspect at each recorded keyframe,
with the frozen posture thresholds, the measured descent core, and
the stillness window that follows it.

Every plotted point is a recorded value. Nothing is interpolated
between keyframes (the connecting lines are a reading aid), nothing
is synthesized, and no API is called. The script refuses to render
if the record does not reproduce the phase evidence the gate
recorded (16 of 16 keyframes upright before the descent, 7 of 7
horizontal after it, under the record's own thresholds): a figure
that disagrees with the recorded phases must fail loudly here, not
ship.

Usage:
    python3 scripts/render_worked_example_trace.py [RECORD_JSON] [OUT_PNG]

Defaults: RECORD_JSON is the gate record in the local run cache;
OUT_PNG is docs/assets/worked_example_trace.png.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
DEFAULT_RECORD = (REPO / "cache" / "gate_d1" / "main"
                  / "le2i_coffee-room-01_video-02.json")
DEFAULT_OUT = REPO / "docs" / "assets" / "worked_example_trace.png"
EVENT_ID = "le2i_coffee-room-01_video-02"

# Canvas and palette: plain chart furniture on white, one dark series
# (tilt, the decisive feature) and one light series (aspect).
W, H = 1600, 930
LEFT, RIGHT, TOP, BOTTOM = 130, 130, 150, 110
BG = (255, 255, 255)
GRID = (221, 221, 221)
AXIS = (68, 68, 68)
TEXT = (34, 34, 34)
TILT_COLOR = (32, 69, 110)
ASPECT_COLOR = (150, 150, 150)
THRESH_COLOR = (176, 58, 46)
DESCENT_FILL = (246, 219, 160)
STILL_FILL = (201, 214, 232)

TILT_MAX = 95.0
ASPECT_MAX = 2.0
TIME_MAX = 12.5


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> int:
    record_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RECORD
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    if not record_path.exists():
        print(f"record not found: {record_path}", file=sys.stderr)
        return 1
    rec = json.loads(record_path.read_text())
    if rec["clip_id"] != EVENT_ID:
        print(f"record is for {rec['clip_id']}, not {EVENT_ID}",
              file=sys.stderr)
        return 1
    seg = rec["segments"][0]
    rules = seg["rules_params"]["rules"]
    still = seg["rules_params"]["stillness"]
    descent = seg["rules_phases"]["descent"]["detail"]
    d_on, d_off = descent["onset_s"], descent["offset_s"]
    still_span = (d_off, d_off + still["stillness_window_s"])

    # The winning track: the one the rules evaluated. It is the long
    # track; the only other track in this record has a single frame.
    track = max(seg["run"]["tracks"], key=lambda t: len(t["frames"]))
    frames = sorted(track["frames"], key=lambda f: f["t_s"])

    # Reproduce the recorded phase evidence before drawing anything.
    def posture(f):
        if f["elongation"] < rules["min_elongation"]:
            return None
        if f["axis_tilt_deg"] >= rules["upright_tilt_min_deg"]:
            return "upright"
        if f["axis_tilt_deg"] <= rules["horizontal_tilt_max_deg"]:
            return "horizontal"
        return None

    pre = [posture(f) for f in frames if f["t_s"] < d_on]
    post = [posture(f) for f in frames if f["t_s"] > d_off]
    recorded_pre = seg["rules_phases"]["pre_posture"]["detail"]["postures"]
    recorded_post = seg["rules_phases"]["post_posture"]["detail"]["postures"]
    if pre != recorded_pre or post != recorded_post:
        print("posture reproduction mismatch: "
              f"pre {pre} vs recorded {recorded_pre}; "
              f"post {post} vs recorded {recorded_post}",
              file=sys.stderr)
        return 1

    plot_w = W - LEFT - RIGHT
    plot_h = H - TOP - BOTTOM

    def x(t: float) -> float:
        return LEFT + plot_w * (t / TIME_MAX)

    def y_tilt(v: float) -> float:
        return TOP + plot_h * (1 - v / TILT_MAX)

    def y_aspect(v: float) -> float:
        return TOP + plot_h * (1 - v / ASPECT_MAX)

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f_tick = load_font(25)
    f_axis = load_font(28, bold=True)
    f_label = load_font(25)
    f_span = load_font(24)

    # Phase spans, behind everything.
    dr.rectangle([x(d_on), TOP, x(d_off), TOP + plot_h],
                 fill=DESCENT_FILL)
    dr.rectangle([x(still_span[0]), TOP, x(still_span[1]), TOP + plot_h],
                 fill=STILL_FILL)

    # Gridlines and tick labels: tilt (left), aspect (right), time.
    for v in range(0, 91, 15):
        y = y_tilt(v)
        dr.line([LEFT, y, LEFT + plot_w, y], fill=GRID, width=1)
        dr.text((LEFT - 14, y), f"{v}", font=f_tick, fill=TEXT,
                anchor="rm")
    for v in (0.0, 0.5, 1.0, 1.5, 2.0):
        y = y_aspect(v)
        dr.text((LEFT + plot_w + 14, y), f"{v:.1f}", font=f_tick,
                fill=ASPECT_COLOR, anchor="lm")
    for t in range(0, 13, 2):
        xx = x(t)
        dr.line([xx, TOP + plot_h, xx, TOP + plot_h + 8], fill=AXIS,
                width=2)
        dr.text((xx, TOP + plot_h + 16), f"{t}", font=f_tick, fill=TEXT,
                anchor="ma")

    # Posture thresholds the frozen rules apply to the tilt series.
    # Dashes are drawn now; the labels are drawn after the series so
    # no line or marker can cross the text.
    thresh_labels = []
    for v, label in ((rules["upright_tilt_min_deg"],
                      "upright: tilt at or above "
                      f"{rules['upright_tilt_min_deg']:.0f} deg"),
                     (rules["horizontal_tilt_max_deg"],
                      "horizontal: tilt at or below "
                      f"{rules['horizontal_tilt_max_deg']:.0f} deg")):
        y = y_tilt(v)
        dash = 16
        xx = LEFT
        while xx < LEFT + plot_w:
            dr.line([xx, y, min(xx + dash, LEFT + plot_w), y],
                    fill=THRESH_COLOR, width=2)
            xx += dash * 2
        thresh_labels.append((y, label))

    # Aspect series first (light), then tilt (the decisive feature).
    pts_aspect = [(x(f["t_s"]), y_aspect(f["aspect"])) for f in frames]
    dr.line(pts_aspect, fill=ASPECT_COLOR, width=2)
    for px, py in pts_aspect:
        dr.ellipse([px - 4, py - 4, px + 4, py + 4], outline=ASPECT_COLOR,
                   width=2)
    pts_tilt = [(x(f["t_s"]), y_tilt(f["axis_tilt_deg"])) for f in frames]
    dr.line(pts_tilt, fill=TILT_COLOR, width=3)
    for px, py in pts_tilt:
        dr.ellipse([px - 6, py - 6, px + 6, py + 6], fill=TILT_COLOR)

    # Frame of the plot area.
    dr.rectangle([LEFT, TOP, LEFT + plot_w, TOP + plot_h], outline=AXIS,
                 width=2)
    for y, label in thresh_labels:
        # The horizontal label starts a little further right: the
        # aspect series' first keyframe sits almost on its line.
        lx = LEFT + (40 if label.startswith("horizontal") else 10)
        dr.text((lx, y - 8), label, font=f_label,
                fill=THRESH_COLOR, anchor="ls")

    # Span labels above the plot, on separate rows: the descent span
    # is narrow, so a shared row would collide.
    dr.text(((x(d_on) + x(d_off)) / 2, TOP - 82),
            f"descent core, {d_on:.2f} to {d_off:.2f} s", font=f_span,
            fill=TEXT, anchor="ma")
    dr.text(((x(still_span[0]) + x(still_span[1])) / 2, TOP - 42),
            f"stillness window, {still_span[0]:.2f} to "
            f"{still_span[1]:.2f} s", font=f_span, fill=TEXT, anchor="ma")

    # Axis titles and series legend.
    dr.text((LEFT, 34), "mask axis tilt (deg)", font=f_axis,
            fill=TILT_COLOR, anchor="la")
    dr.text((LEFT + plot_w, 34), "box aspect", font=f_axis,
            fill=ASPECT_COLOR, anchor="ra")
    dr.text((LEFT + plot_w / 2, H - 52), "time (s)", font=f_axis,
            fill=TEXT, anchor="ma")
    # Legend sits in the empty band between the two threshold lines,
    # clear of both series.
    lx, ly = LEFT + 18, y_tilt(49)
    dr.line([lx, ly + 10, lx + 52, ly + 10], fill=TILT_COLOR, width=3)
    dr.ellipse([lx + 20, ly + 4, lx + 32, ly + 16], fill=TILT_COLOR)
    dr.text((lx + 64, ly), "axis tilt per keyframe", font=f_label,
            fill=TEXT, anchor="la")
    dr.line([lx, ly + 44, lx + 52, ly + 54], fill=ASPECT_COLOR, width=2)
    dr.ellipse([lx + 22, ly + 48, lx + 30, ly + 56],
               outline=ASPECT_COLOR, width=2)
    dr.text((lx + 64, ly + 44), "box aspect per keyframe", font=f_label,
            fill=TEXT, anchor="la")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"wrote {out_path} from {record_path}")
    print(f"track {track['track_id']}: {len(frames)} keyframes, "
          f"t {frames[0]['t_s']}..{frames[-1]['t_s']} s")
    print(f"tilt: {[f['axis_tilt_deg'] for f in frames]}")
    print(f"aspect: {[f['aspect'] for f in frames]}")
    print(f"descent core {d_on}..{d_off} s; stillness window "
          f"{still_span[0]}..{still_span[1]} s; postures reproduced: "
          f"{len(pre)} pre, {len(post)} post")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
