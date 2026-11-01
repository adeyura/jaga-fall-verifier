"""Regression checks for the Jaga pipeline units.

Run from a clean checkout:
        pip install -r requirements.txt
        python3 tests/run_checks.py

Plain asserts, no framework: this file is the protection the frozen
run relies on, so it must run anywhere the pipeline runs. Every
check is self-contained against committed fixtures: the synthetic
SAM stream (a real captured response to an AI-generated image — the
dataset-derived stream cannot be committed under its license, so
its scenarios are carried as fail-closed mutations of the synthetic
one) and a synthetic video. The scored configuration is the plain
invocation above: strict mode is the default (any SKIP fails the
run); JAGA_STRICT=0 opts out for exploratory runs only.
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from jaga.adjudicator import adjudicate, parse_verdict       # noqa: E402
from jaga.features import build_tracks, stillness            # noqa: E402
from jaga.rules import evaluate                              # noqa: E402
from jaga.sam_parse import Instance, _axis_features          # noqa: E402
from jaga.timing import Interval, TimingResult, analyze      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# Committed synthetic fixture: a real SAM stream elicited from an
# AI-generated mannequin image (no dataset content, no real person).
# Always present, so the parse protections are exercised in every
# checkout. (The dataset-derived stream used during development is
# uncommittable under its license; its error scenarios live here as
# mutations of this stream.)
SYNTH = ROOT / "tests" / "fixtures" / "sam_stream_synth.txt"
SYNTH_STREAM = SYNTH.read_text() if SYNTH.exists() else None

RESULTS = []

GOOD = ('{"for_fall": "a", "for_benign": "b", "data_quality": "c", '
        '"discriminator": "d", "verdict": "fall", "confidence": 0.8}')


def check(name):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, "PASS", ""))
        except Exception as e:  # noqa: BLE001 - the harness reports, not hides
            import traceback as _tb
            RESULTS.append((name, "FAIL", f"{type(e).__name__}: {e}\n"
                            + _tb.format_exc()))
        return fn
    return deco


def skip(name, why):
    RESULTS.append((name, "SKIP", why))


def inst(box, tilt, elong=2.8, oid="0"):
    w, h = box[2] - box[0], box[3] - box[1]
    return Instance(object_id=oid, box=box, mask_area_px=w * h // 2,
                    mask_width=w, mask_height=h, centroid_xy=(w / 2, h / 2),
                    bottom_y=h - 1, bottom_band_share=0.1,
                    elongation=elong, axis_tilt_deg=tilt)


W, H = 640, 240
UP = (100, 20, 150, 160)
MID = (95, 70, 185, 175)
HOR = (85, 130, 225, 180)
SEATED = (100, 60, 155, 180)


def timing(a, b, core=None):
    ca, cb = core if core is not None else (a, b)
    iv = Interval(onset_s=a, offset_s=b, duration_s=b - a,
                  core_onset_s=ca, core_offset_s=cb,
                  peak_area_frac=0.4, peak_energy=9.0, peak_vy_hps=0.8,
                  net_centroid_drop=0.2)
    return TimingResult([iv], iv, 0.01, 0.1, 30.0)


def run_rules(spec, tm=None, view="side"):
    tracks, _ = build_tracks(spec, W, H)
    return evaluate(tracks, W, H, timing=tm, view=view)


FALL_FRAMES = [(0.0, [inst(UP, 85)]), (0.5, [inst(UP, 85)]),
               (1.0, [inst(MID, 45)]), (1.5, [inst(HOR, 10)]),
               (2.0, [inst(HOR, 10)]), (2.5, [inst(HOR, 10)]),
               (3.0, [inst(HOR, 10)]), (3.5, [inst(HOR, 10)]),
               (4.0, [inst(HOR, 10)]), (4.5, [inst(HOR, 10)]),
               (5.0, [inst(HOR, 10)])]


# ---------------------------------------------------------------- timing
@check("timing: quiet clip yields no descent")
def _():
    e = np.full(300, 0.5)
    af = np.full(300, 0.01)
    cy = np.full(300, 0.45)
    r = analyze(e, af, cy, 30.0)
    assert r.descent is None and not r.intervals


@check("timing: 0.6 s burst recovered as a descent")
def _():
    e = np.concatenate([np.full(60, 0.5), np.full(18, 9.0), np.full(120, 0.5)])
    af = np.concatenate([np.full(60, 0.01), np.full(18, 0.45),
                         np.full(120, 0.01)])
    cy = np.concatenate([np.full(60, 0.45), np.linspace(0.35, 0.6, 18),
                         np.full(120, 0.45)])
    r = analyze(e, af, cy, 30.0)
    assert r.descent is not None
    assert abs(r.descent.duration_s - 0.6) <= 0.25
    assert abs(r.descent.onset_s - 2.0) <= 0.3


@check("timing: sustained walking is not a descent")
def _():
    e = np.concatenate([np.full(30, 0.5), np.full(120, 5.0), np.full(30, 0.5)])
    af = np.concatenate([np.full(30, 0.01), np.full(120, 0.3),
                         np.full(30, 0.01)])
    cy = np.full(180, 0.45)
    r = analyze(e, af, cy, 30.0)
    assert r.descent is None


# ------------------------------------------------------- axis honesty
@check("axis: degenerate masks report no axis, never a direction")
def _():
    assert _axis_features(np.array([5]), np.array([5])) == (None, None)
    xs = np.zeros(20, dtype=int)
    ys = np.arange(20)
    assert _axis_features(xs, ys) == (None, None), _axis_features(xs, ys)


# ------------------------------------------------------- features
@check("features: stillness known for dense still track")
def _():
    one = inst(UP, 85)
    spec = [(t * 0.5, [one]) for t in range(6)]
    tracks, _ = build_tracks(spec, W, H)
    assert stillness(tracks[0], W, H) == 0.0


@check("features: stillness unknown across an unobserved gap")
def _():
    one = inst(UP, 85)
    tracks, _ = build_tracks([(0.0, [one]), (2.6, [one])], W, H)
    assert stillness(tracks[0], W, H) is None


@check("features: stillness dimension mismatch raises")
def _():
    tracks, _ = build_tracks([(0.0, [inst(UP, 85)]),
                              (0.5, [inst(UP, 85)])], W, H)
    try:
        stillness(tracks[0], 320, 240)
    except ValueError:
        return
    raise AssertionError("mismatched dims accepted")


@check("features: NaN keyframe time raises")
def _():
    try:
        build_tracks([(float("nan"), [inst(UP, 85)])], W, H)
    except ValueError:
        return
    raise AssertionError("NaN time accepted")


@check("features: out-of-frame box raises")
def _():
    bad = inst((600, 20, 700, 160), 85)  # right edge beyond 640
    try:
        build_tracks([(0.0, [bad])], W, H)
    except ValueError:
        return
    raise AssertionError("out-of-frame box accepted")


@check("features: gap-spanning point is flagged with its dt")
def _():
    one = inst(HOR, 10)
    spec = [(0.0, [one]), (0.5, []), (1.0, [one]), (1.5, [one])]
    tracks, stats = build_tracks(spec, W, H)
    pts = tracks[0].frames
    assert pts[1].spans_gap is True and pts[1].dt_s == 1.0
    assert stats["points_spanning_gap"] == 1


# ------------------------------------------------------- rules
@check("rules: canonical fall is a candidate")
def _():
    v = run_rules(FALL_FRAMES, timing(0.7, 1.3))
    assert v.label == "fall_candidate" and v.config_hash


@check("rules: slow lie-down escalates under the duration safeguard (P3)")
def _():
    # Duration alone is no longer a veto: a slow descent whose other
    # phases are all fall-consistent escalates to the adjudicator
    # instead of reading as a confident negative (P3 safeguard).
    v = run_rules(FALL_FRAMES, timing(0.2, 2.4))
    assert v.label == "uncertain", (v.label, v.reasons)
    assert "outside" in v.reasons[0]


@check("rules: slow descent plus a posture contradiction stays negative (P3)")
def _():
    sit = [(0.0, [inst(UP, 85)]), (0.5, [inst(UP, 85)]),
           (1.0, [inst(SEATED, 80)]), (1.5, [inst(SEATED, 80)]),
           (2.0, [inst(SEATED, 80)]), (2.5, [inst(SEATED, 80)]),
           (3.0, [inst(SEATED, 80)]), (3.5, [inst(SEATED, 80)]),
           (4.0, [inst(SEATED, 80)])]
    v = run_rules(sit, timing(0.2, 2.4))
    assert v.label == "negative", (v.label, v.reasons)


@check("rules: fast sit-down is negative (never horizontal)")
def _():
    sit = [(0.0, [inst(UP, 85)]), (0.5, [inst(UP, 85)]),
           (1.0, [inst(SEATED, 80)]), (1.5, [inst(SEATED, 80)]),
           (2.0, [inst(SEATED, 80)]), (2.5, [inst(SEATED, 80)]),
           (3.0, [inst(SEATED, 80)]), (3.5, [inst(SEATED, 80)]),
           (4.0, [inst(SEATED, 80)])]
    assert run_rules(sit, timing(0.6, 1.1)).label == "negative"


@check("rules: truncated evidence is uncertain, not negative")
def _():
    assert run_rules(FALL_FRAMES[:4], timing(0.7, 1.3)).label == "uncertain"


@check("rules: a single frame is no_evidence")
def _():
    v = run_rules([(0.0, [inst(UP, 85)])], timing(0.7, 1.3))
    assert v.label == "no_evidence"


@check("rules: keyframe fallback cannot measure duration -> uncertain")
def _():
    # The fallback's "duration" is the sampling gap, not a measurement;
    # a fall-consistent clip judged on it caps at uncertain (H1).
    v = run_rules(FALL_FRAMES, None)
    assert v.label == "uncertain" and v.timing_source == "keyframes"
    assert v.phases["descent"].satisfied is None


@check("rules: merged recovery tail does not inflate the descent (H2)")
def _():
    # Envelope run 0.7-3.3 s (descent + recovery scramble) with a
    # 0.6 s core: the phase judges the core, brackets on the core.
    v = run_rules(FALL_FRAMES, timing(0.7, 3.3, core=(0.8, 1.4)))
    assert v.label == "fall_candidate", v.reasons


@check("rules: occluded descent (transition, no descent seen) -> uncertain (H3)")
def _():
    gradual = [(0.0, [inst(UP, 85)]),
               (0.5, [inst((100, 35, 150, 170), 80)]),
               (1.0, [inst((98, 55, 165, 178), 65)]),
               (1.5, [inst((92, 80, 200, 180), 40)]),
               (2.0, [inst(HOR, 10)]), (2.5, [inst(HOR, 10)]),
               (3.0, [inst(HOR, 10)]), (3.5, [inst(HOR, 10)])]
    v = run_rules(gradual, None)
    assert v.label == "uncertain", (v.label, v.reasons)


@check("rules: no descent and no transition -> negative (H3)")
def _():
    still_up = [(t * 0.5, [inst(UP, 85)]) for t in range(8)]
    v = run_rules(still_up, None)
    assert v.label == "negative", (v.label, v.reasons)


@check("rules: stillness is anchored at the descent, not the track end (M1)")
def _():
    # Still 1.5-4.0, then the (horizontal) person shifts at 4.5+:
    # the post-descent window [1.3, 4.3] is still -> candidate.
    shifted = (145, 130, 285, 180)
    frames = FALL_FRAMES[:9] + [(4.5, [inst(shifted, 10)]),
                                (5.0, [inst(shifted, 10)]),
                                (5.5, [inst(shifted, 10)]),
                                (6.0, [inst(shifted, 10)])]
    v = run_rules(frames, timing(0.7, 1.3))
    assert v.label == "fall_candidate", (v.label, v.reasons)


@check("rules: movement inside the post-descent window fails stillness (M1)")
def _():
    # Horizontal throughout after the descent, but the person shifts
    # at 2.5 s (inside [1.3, 4.3]) and is still afterwards.
    shifted = (145, 130, 285, 180)
    frames = [(0.0, [inst(UP, 85)]), (0.5, [inst(UP, 85)]),
              (1.0, [inst(MID, 45)]), (1.5, [inst(HOR, 10)]),
              (2.0, [inst(HOR, 10)]), (2.5, [inst(shifted, 10)]),
              (3.0, [inst(shifted, 10)]), (3.5, [inst(shifted, 10)]),
              (4.0, [inst(shifted, 10)]), (4.5, [inst(shifted, 10)]),
              (5.0, [inst(shifted, 10)]), (5.5, [inst(shifted, 10)]),
              (6.0, [inst(shifted, 10)])]
    v = run_rules(frames, timing(0.7, 1.3))
    assert v.label == "negative", (v.label, v.reasons)


@check("rules: a later interval can carry the fall (M2)")
def _():
    walk = [(t * 0.5, [inst((100 + int(t * 4), 20, 150 + int(t * 4), 160), 85)])
            for t in range(8)]                       # 0..3.5 walking
    stand = [(4.0 + t * 0.5, [inst(UP, 85)]) for t in range(8)]  # 4..7.5
    fall = [(8.0, [inst(MID, 45)]), (8.5, [inst(HOR, 10)]),
            (9.0, [inst(HOR, 10)]), (9.5, [inst(HOR, 10)]),
            (10.0, [inst(HOR, 10)]), (10.5, [inst(HOR, 10)]),
            (11.0, [inst(HOR, 10)]), (11.5, [inst(HOR, 10)])]
    spec = walk + stand + fall
    iv1 = Interval(onset_s=3.0, offset_s=3.6, duration_s=0.6,
                   core_onset_s=3.0, core_offset_s=3.6,
                   peak_area_frac=0.4, peak_energy=9.0,
                   peak_vy_hps=0.8, net_centroid_drop=0.0)
    iv2 = Interval(onset_s=7.9, offset_s=8.5, duration_s=0.6,
                   core_onset_s=7.9, core_offset_s=8.5,
                   peak_area_frac=0.3, peak_energy=9.0,
                   peak_vy_hps=0.8, net_centroid_drop=0.2)
    tm = TimingResult([iv1, iv2], iv2, 0.01, 0.1, 30.0)
    v = run_rules(spec, tm)
    assert v.label == "fall_candidate", (v.label, v.reasons)


@check("rules: a fragmented faller beats a longer bystander track (M3)")
def _():
    bystander = (400, 20, 450, 160)
    spec = [(t, [fl[0], inst(bystander, 85, oid="1")])
            for t, fl in FALL_FRAMES]
    v = run_rules(spec, timing(0.7, 1.3))
    assert v.label == "fall_candidate", (v.label, v.reasons)


@check("rules: ceiling fall caps at uncertain, pre unobservable (P2)")
def _():
    lying = (411, 26, 495, 182)
    spec = [(3.0, [inst((431, 1, 517, 105), 71, elong=1.1)]),
            (3.5, [inst(lying, 70, elong=2.86)]),
            (4.0, [inst(lying, 82, elong=2.3)]),
            (4.5, [inst(lying, 82, elong=2.2)]),
            (5.0, [inst(lying, 82, elong=2.24)]),
            (5.5, [inst(lying, 82, elong=2.24)]),
            (6.0, [inst(lying, 82, elong=2.24)]),
            (6.5, [inst(lying, 82, elong=2.24)])]
    tm = timing(2.9, 3.7, core=(3.0, 3.6))
    v = run_rules(spec, tm, view="ceiling")
    assert v.label == "uncertain", (v.label, v.reasons)
    assert v.phases["pre_posture"].satisfied is None
    assert v.phases["post_posture"].satisfied is True
    assert v.phases["stillness"].satisfied is True


@check("rules: ceiling mover after the burst is negative (P2)")
def _():
    lying = (411, 26, 495, 182)
    moved = (451, 26, 535, 182)  # 40 px shift: same track, real movement
    spec = [(3.0, [inst((431, 1, 517, 105), 71, elong=1.1)]),
            (3.5, [inst(lying, 70, elong=2.86)]),
            (4.0, [inst(lying, 82, elong=2.3)]),
            (4.5, [inst(lying, 82, elong=2.2)]),
            (5.0, [inst(moved, 82, elong=2.24)]),
            (5.5, [inst(moved, 82, elong=2.24)]),
            (6.0, [inst(moved, 82, elong=2.24)]),
            (6.5, [inst(moved, 82, elong=2.24)])]
    v = run_rules(spec, timing(2.9, 3.7, core=(3.0, 3.6)), view="ceiling")
    assert v.label == "negative", (v.label, v.reasons)


@check("rules: ceiling track fragmentation escalates, never dismisses (P2)")
def _():
    # An 80 px jump breaks box-IoU association; the fallen person's
    # stillness evidence fragments across two tracks. Fragmented
    # evidence is missing evidence: uncertain, not negative.
    lying = (411, 26, 495, 182)
    moved = (491, 26, 575, 182)
    spec = [(3.0, [inst((431, 1, 517, 105), 71, elong=1.1)]),
            (3.5, [inst(lying, 70, elong=2.86)]),
            (4.0, [inst(lying, 82, elong=2.3)]),
            (4.5, [inst(lying, 82, elong=2.2)]),
            (5.0, [inst(moved, 82, elong=2.24)]),
            (5.5, [inst(moved, 82, elong=2.24)]),
            (6.0, [inst(moved, 82, elong=2.24)]),
            (6.5, [inst(moved, 82, elong=2.24)])]
    v = run_rules(spec, timing(2.9, 3.7, core=(3.0, 3.6)), view="ceiling")
    assert v.label == "uncertain", (v.label, v.reasons)


@check("rules: ceiling elongated person, descent unseen -> uncertain (P2/H3)")
def _():
    lying = (411, 26, 495, 182)
    spec = [(3.0, [inst(lying, 70, elong=2.86)]),
            (3.5, [inst(lying, 82, elong=2.3)]),
            (4.0, [inst(lying, 82, elong=2.2)]),
            (4.5, [inst(lying, 82, elong=2.24)])]
    v = run_rules(spec, None, view="ceiling")
    assert v.label == "uncertain", (v.label, v.reasons)


@check("rules: a pocket-sized persistent track loses ties to the person (area)")
def _():
    # A 150 px artifact present in every keyframe and the actual
    # person both reach uncertain; the merged verdict must carry the
    # person's track, because downstream stages read its record.
    speck = (280, 0, 311, 8)
    lying = (111, 26, 195, 182)
    spec = [(3.0, [inst(speck, 5, elong=3.4, oid="0"),
                   inst((111, 1, 197, 105), 71, elong=1.1, oid="1")]),
            (3.5, [inst(speck, 5, elong=3.4, oid="0"),
                   inst(lying, 70, elong=2.86, oid="1")]),
            (4.0, [inst(speck, 5, elong=3.4, oid="0"),
                   inst(lying, 82, elong=2.3, oid="1")]),
            (4.5, [inst(speck, 5, elong=3.4, oid="0"),
                   inst(lying, 82, elong=2.2, oid="1")]),
            (5.0, [inst(speck, 5, elong=3.4, oid="0"),
                   inst(lying, 82, elong=2.24, oid="1")])]
    v = run_rules(spec, timing(2.9, 3.7, core=(3.0, 3.6)), view="ceiling")
    assert v.label == "uncertain", (v.label, v.reasons)
    person_tracks = [t for t in build_tracks(spec, W, H)[0]
                     if sum(f.area_px for f in t.frames) > 5000]
    assert v.track_id == person_tracks[0].track_id, (
        v.track_id, [t.track_id for t in build_tracks(spec, W, H)[0]])


@check("rules: ceiling fixture alone cannot author person-present (M1)")
def _():
    # Only the pocket-sized artifact track exists after the burst:
    # the post phase must read False (no person-sized mask), never
    # True on frame count alone.
    speck = (280, 0, 311, 8)
    spec = [(t * 0.5, [inst(speck, 5, elong=3.4)])
            for t in range(7, 14)]  # 3.5 .. 6.5
    spec = [(3.0, [inst(speck, 5, elong=3.4)])] + spec
    v = run_rules(spec, timing(2.9, 3.7, core=(3.0, 3.6)), view="ceiling")
    assert v.phases["post_posture"].satisfied is False, v.phases
    assert "person-sized" in v.phases["post_posture"].detail["note"]
    assert v.label == "negative", (v.label, v.reasons)


@check("rules: unmeasurable posture plus unseen descent is uncertain (M3)")
def _():
    round_mask = (100, 60, 160, 150)  # elongation ~1.1: axis abstains
    spec = [(t * 0.5, [inst(round_mask, 30, elong=1.1)])
            for t in range(6)]
    v = run_rules(spec, None)
    assert v.label == "uncertain", (v.label, v.reasons)
    assert v.phases["descent"].satisfied is None


@check("harness: adjudication labels never leak into the clip outcome (H1)")
def _():
    import csv as _csv
    from pathlib import Path as _Path
    from jaga.harness import run_clip
    from jaga.sam_runner import ClipRun

    root = ROOT
    row = {"clip_id": "tiny-fixture", "label": "adl", "view": "side",
           "video_path": "tests/fixtures/tiny.mp4"}
    tracks, _ = build_tracks(FALL_FRAMES, W, H)

    class StubRunner:
        def run_keyframes(self, clip_id, window):
            return ClipRun(clip_id=clip_id, tracks=tracks,
                           frame_w=W, frame_h=H)

    def fake_transport(body):
        return {"choices": [{"message": {"content": GOOD}}], "usage": {}}

    def picker(window, run):
        return ["data:image/png;base64,AAAA"], ["Keyframe at 0.0 s:"]

    rec = run_clip(root / row["video_path"], row, StubRunner(),
                   root / "cache",
                   adjudicate_labels=frozenset(
                       {"uncertain", "negative", "fall_candidate"}),
                   transport=fake_transport, image_picker=picker,
                   evidence_form="raw")
    from jaga.harness import _merge_labels
    expected = _merge_labels([s["rules_label"] for s in rec["segments"]])
    assert rec["outcome"] == expected, (rec["outcome"], expected)
    assert rec["outcome"] in ("fall_candidate", "uncertain", "negative",
                               "no_evidence")
    assert any(s.get("adjudication", {}).get("usable")
               for s in rec["segments"])


@check("timing: core duration excludes a merged low tail")
def _():
    e = np.concatenate([np.full(200, 0.5), np.full(18, 9.0),
                        np.full(60, 3.0), np.full(60, 0.5)])
    af = np.concatenate([np.full(200, 0.01), np.full(18, 0.45),
                         np.full(60, 0.10), np.full(60, 0.01)])
    cy = np.full(338, 0.45)
    r = analyze(e, af, cy, 30.0)
    assert r.descent is not None
    assert abs(r.descent.core_duration_s - 0.6) <= 0.2, r.descent
    assert r.descent.duration_s > 2.0, r.descent


@check("timing: a flat envelope carries no signal and says so")
def _():
    e = np.full(300, 0.5)
    af = np.array([0.0100, 0.0104] * 150)
    cy = np.full(300, 0.45)
    r = analyze(e, af, cy, 30.0)
    assert r.intervals == [] and r.descent is None


# ------------------------------------------------------- adjudicator


@check("adjudicator: well-formed verdict parses")
def _():
    v = adjudicate(lambda body: {"choices": [{"message": {"content": GOOD}}],
                                 "usage": {}}, "traces", [])
    assert v.usable and v.verdict == "fall" and v.confidence == 0.8


@check("adjudicator: transport failure is unusable, never an answer")
def _():
    def boom(body):
        raise TimeoutError("api timeout")
    v = adjudicate(boom, "x", [])
    assert not v.usable and v.verdict is None


@check("adjudicator: prose, bad enum, bad confidence are unusable")
def _():
    assert not parse_verdict("probably a fall").usable
    assert not parse_verdict('{"verdict": "maybe", "confidence": 0.5}').usable
    assert not parse_verdict('{"verdict": "fall", "confidence": 1.7}').usable
    assert not parse_verdict(None).usable


# ------------------------------------------------------- parse (fixture)
from jaga.sam_parse import parse_sam_stream


@check("parse: garbage SSE line raises")
def _():
    try:
        parse_sam_stream("this is not an SSE line\n" + SYNTH_STREAM)
    except ValueError:
        return
    raise AssertionError("garbage line skipped")


@check("parse: malformed data payload raises as ValueError")
def _():
    try:
        parse_sam_stream("data: {broken\n" + SYNTH_STREAM)
    except ValueError:
        return
    raise AssertionError("malformed payload accepted")


@check("parse: mask without a box raises")
def _():
    import re as _re
    out, removed = [], 0
    for ln in SYNTH_STREAM.splitlines():
        if ln.startswith("data:"):
            try:
                ev = json.loads(ln[5:])
            except Exception:
                out.append(ln)
                continue
            for key in ("delta", "text"):
                val = ev.get(key)
                if isinstance(val, str) and "<|box;" in val and removed == 0:
                    v2 = _re.sub(r"0<\|box;[^|]*\|>", "0", val, count=1)
                    if v2 != val:
                        ev[key] = v2
                        removed += 1
            out.append("data: " + json.dumps(ev))
        else:
            out.append(ln)
    assert removed == 1
    try:
        parse_sam_stream("\n".join(out))
    except ValueError:
        return
    raise AssertionError("boxless mask accepted")

# ------------------------------------------------------- runner
@check("runner: anomaly gate includes superseded masks and carries the run")
def _():
    import jaga.sam_runner as sr

    real_parse = sr.parse_sam_stream

    def fake_parse(text, **kwargs):
        return [], {"boxes_without_masks": 0, "text_records": 0,
                    "tiny_instances": 0, "masks_superseded": 2}
    sr.parse_sam_stream = fake_parse
    try:
        frame = ROOT / "tests" / "fixtures" / "frame.png"
        if not frame.exists():
            # any small PNG works; generate one with ffmpeg-free bytes
            import struct
            import zlib

            def chunk(tag, data):
                c = struct.pack(">I", len(data)) + tag + data
                return c + struct.pack(">I", zlib.crc32(tag + data))
            ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 0, 0, 0, 0)
            idat = zlib.compress(b"\x00" * (4 * 4 + 4))
            png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                   + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(png)
        with tempfile.TemporaryDirectory() as td:
            def transport(b, p):
                return "unused"
            transport.model_id = "sam-3.1"
            runner = sr.SamRunner(Path(td), transport)
            try:
                runner.run_keyframes("clip", [(0.0, frame)])
            except sr.AnomalyError as e:
                assert e.run.anomalies["masks_superseded"] == 2
                assert e.run.model == "sam-3.1"
                return
            raise AssertionError("anomaly gate did not fire")
    finally:
        sr.parse_sam_stream = real_parse


@check("runner: an undeclared transport stamps no model on the run")
def _():
    import jaga.sam_runner as sr
    import numpy as _np
    from jaga.overlays import encode_png as _enc
    with tempfile.TemporaryDirectory() as td:
        frame = Path(td) / "attr_frame.png"
        frame.write_bytes(
            _enc(_np.full((240, 320, 3), 90, dtype=_np.uint8)))
        runner = sr.SamRunner(Path(td), lambda b, p: SYNTH_STREAM)
        run = runner.run_keyframes("clip", [(0.0, frame)])
        assert run.model is None
        assert run.to_dict()["model_attribution"] == "undeclared"
        def declared(b, p):
            return SYNTH_STREAM
        declared.model_id = "sam-3.1"
        runner2 = sr.SamRunner(Path(td), declared)
        run2 = runner2.run_keyframes("clip", [(0.0, frame)])
        assert run2.model == "sam-3.1"
        assert run2.to_dict()["model_attribution"] == \
            "transport-declared"


def main() -> int:
    strict = os.environ.get("JAGA_STRICT") != "0"
    failed = 0
    for name, status, note in RESULTS:
        print(f"{status:4}  {name}" + (f"  — {note}" if note else ""))
        failed += status == "FAIL"
        if strict and status == "SKIP":
            failed += 1
    print(f"\n{len(RESULTS)} checks, {failed} failed"
          + (" (strict: skips fail)" if strict else ""))
    return 1 if failed else 0


@check("overlays: tint lands on the mask, background stays blurred")
def _():
    import numpy as _np
    from jaga.overlays import render_overlay, blur_background
    frame = _np.zeros((60, 80, 3), dtype=_np.uint8)
    frame[:, :40] = (200, 200, 200)
    frame[:, 40:] = (20, 20, 20)
    mask = _np.zeros((20, 10), dtype=bool)
    mask[5:15, 2:8] = True
    out = render_overlay(frame, [(mask, (30, 20))])
    assert out.shape == frame.shape and out.dtype == _np.uint8
    bg = blur_background(frame)
    assert bg.shape == frame.shape
    # Blur strength, measured with a bright disc probe: a 20-px feature
    # at dataset width and a 16-px feature
    # in a narrow 64-px frame must both lose most of their peak —
    # the narrow case is what the guaranteed downscale protects.
    def disc_peak(wdt, hgt, r):
        yy, xx = _np.mgrid[0:hgt, 0:wdt]
        img = _np.zeros((hgt, wdt, 3), dtype=_np.uint8)
        img[((xx - wdt // 2) ** 2 + (yy - hgt // 2) ** 2) <= r * r] = 255
        return int(blur_background(img).max())
    assert disc_peak(320, 240, 10) < 150, disc_peak(320, 240, 10)
    assert disc_peak(64, 48, 8) < 150, disc_peak(64, 48, 8)
    inside = out[30, 34].astype(int)   # inside the mask
    under = bg[30, 34].astype(int)     # the blurred background there
    outside = out[30, 5].astype(int)   # blurred background only
    # the tint must push the pixel red-ward of its own background
    assert (inside[0] - inside[1]) > (under[0] - under[1]) + 40, inside
    assert inside[0] > under[0], (inside, under)
    assert abs(int(outside[0]) - int(outside[2])) < 30, outside


@check("overlays: a mask that does not fit its frame raises")
def _():
    import numpy as _np
    from jaga.overlays import render_overlay
    frame = _np.zeros((40, 40, 3), dtype=_np.uint8)
    mask = _np.ones((10, 10), dtype=bool)
    try:
        render_overlay(frame, [(mask, (35, 0))])
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-frame mask placement did not raise")


@check("overlays: PNG encode/decode round-trips")
def _():
    import numpy as _np
    from jaga.overlays import encode_png, read_png_rgb
    img = _np.arange(4 * 5 * 3, dtype=_np.uint8).reshape(4, 5, 3)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "overlay_roundtrip.png"
        p.write_bytes(encode_png(img))
        back = read_png_rgb(p)
    assert back.shape == img.shape
    assert int(_np.abs(back.astype(int) - img.astype(int)).max()) <= 1


@check("parse: rasters retained only on request, and they add up")
def _():
    import numpy as _np
    insts, _ = parse_sam_stream(SYNTH_STREAM, keep_raster=True)
    assert insts and all(i.raster is not None for i in insts)
    for i in insts:
        assert i.raster.shape == (i.mask_height, i.mask_width)
        assert int(i.raster.sum()) == i.mask_area_px
    i = insts[0]
    ys, xs = _np.nonzero(i.raster)
    # the retained raster is the same raster the features came from:
    # no flip, no transpose (equal shape and sum would hide both)
    assert abs(float(xs.mean()) + 0.5 - i.centroid_xy[0]) < 1e-9
    assert abs(float(ys.mean()) + 0.5 - i.centroid_xy[1]) < 1e-9
    assert int(ys.max()) == i.bottom_y
    plain, _ = parse_sam_stream(SYNTH_STREAM)
    assert all(i.raster is None for i in plain)


@check("harness: overlay picker renders overlays and demands rasters")
def _():
    import base64 as _b64
    import numpy as _np
    from jaga.harness import overlay_picker
    from jaga.overlays import encode_png as _enc, read_png_rgb
    from jaga.sam_runner import ClipRun, KeyframeResult
    from jaga.sam_parse import Instance

    def make_frame(path, gray, mask_box):
        frame = _np.full((64, 64, 3), gray, dtype=_np.uint8)
        path.write_bytes(_enc(frame))
        raster = _np.zeros((mask_box[3] - mask_box[1],
                            mask_box[2] - mask_box[0]), dtype=bool)
        raster[2:-2, 2:-2] = True
        inst = Instance(object_id="0", box=mask_box,
                        mask_area_px=int(raster.sum()),
                        mask_width=raster.shape[1],
                        mask_height=raster.shape[0],
                        centroid_xy=(raster.shape[1] / 2,
                                     raster.shape[0] / 2),
                        bottom_y=raster.shape[0] - 3,
                        bottom_band_share=0.1, elongation=2.0,
                        axis_tilt_deg=80.0, raster=raster)
        return inst

    import tempfile as _tf
    d = Path(_tf.mkdtemp(prefix="jaga_picker_"))
    specs = [(0.0, 90, (4, 10, 20, 50)), (0.5, 130, (24, 10, 40, 50)),
             (1.0, 170, (44, 10, 60, 50))]
    window, kfs = [], []
    for t_s, gray, box in specs:
        pth = d / f"picker_frame_{int(t_s * 10)}.png"
        inst = make_frame(pth, gray, box)
        window.append((t_s, pth))
        kfs.append(KeyframeResult(t_s=t_s, instances=[inst],
                                  parse_stats={}, from_cache=True,
                                  images_billed=0))
    run = ClipRun(clip_id="x", keyframes=kfs, frame_w=64, frame_h=64)
    urls, labels = overlay_picker(window, run)
    assert len(urls) == 3 and "overlay" in labels[0]
    # decode the middle pick: the tint must sit at the MIDDLE
    # keyframe's mask (x 24-40), not the first keyframe's (x 4-20)
    mid_path = d / "picker_out_mid.png"
    mid_path.write_bytes(_b64.b64decode(urls[1].split(",", 1)[1]))
    mid = read_png_rgb(mid_path).astype(int)
    in_mask = mid[30, 32]     # inside the middle mask
    in_first = mid[30, 12]    # where the FIRST mask would be
    assert in_mask[0] - in_mask[1] > 40, in_mask
    assert abs(in_first[0] - in_first[1]) < 25, in_first
    # an empty keyframe renders as pure blurred background (no tint)
    empty = KeyframeResult(t_s=0.5, instances=[], parse_stats={},
                           from_cache=True, images_billed=0)
    run2 = ClipRun(clip_id="x", keyframes=[kfs[0], empty, kfs[2]],
                   frame_w=64, frame_h=64)
    urls2, _ = overlay_picker(window, run2)
    p2 = d / "picker_out_empty.png"
    p2.write_bytes(_b64.b64decode(urls2[1].split(",", 1)[1]))
    arr2 = read_png_rgb(p2).astype(int)
    assert int(_np.abs(arr2[..., 0] - arr2[..., 1]).max()) < 25
    # and a missing raster is a loud failure, never a raw frame
    kfs[1].instances[0].raster = None
    try:
        overlay_picker(window, run)
    except ValueError:
        pass
    else:
        raise AssertionError("missing raster did not raise")


@check("parse: synthetic stream yields the recorded instance")
def _():
    insts, stats = parse_sam_stream(SYNTH_STREAM)
    assert len(insts) == 1
    i = insts[0]
    assert i.box == (104, 20, 215, 228), i.box
    assert i.mask_area_px == 11972, i.mask_area_px
    assert stats["boxes_without_masks"] == 0


@check("parse: numbers recompute from the raster (spec alignment)")
def _():
    import numpy as _np
    from jaga.config import FEATURES as _F
    i = parse_sam_stream(SYNTH_STREAM, keep_raster=True)[0][0]
    ys, xs = _np.nonzero(i.raster)
    assert abs(i.centroid_xy[0] - (float(xs.mean()) + 0.5)) < 1e-9
    assert abs(i.centroid_xy[1] - (float(ys.mean()) + 0.5)) < 1e-9
    assert i.bottom_y == int(ys.max())
    band_top = i.mask_height * (1.0 - _F["bottom_band_frac"])
    assert abs(i.bottom_band_share
               - float((ys >= band_top).mean())) < 1e-9
    fp = (i.box[1] + i.bottom_y + 1) / 240
    assert abs(fp - (20 + int(ys.max()) + 1) / 240) < 1e-9
    assert 0.0 < fp <= 1.0


@check("parse: truncated streams raise, never read as results")
def _():
    for cut in (SYNTH_STREAM[:len(SYNTH_STREAM) // 2],
                SYNTH_STREAM[:SYNTH_STREAM.index("response.completed")]):
        try:
            parse_sam_stream(cut)
        except ValueError:
            continue
        raise AssertionError("truncated stream accepted")


@check("parse: [DONE] is a sufficient but not necessary terminator")
def _():
    stripped = SYNTH_STREAM.replace("data: [DONE]", "")
    assert stripped != SYNTH_STREAM  # the edit must actually happen
    insts, _ = parse_sam_stream(stripped)
    assert len(insts) == 1


@check("parse: inconsistent or corrupt stream content raises")
def _():
    box = "<|box;x1=104;y1=20;x2=214;y2=227;w=320;h=240|>"
    variants = [
        SYNTH_STREAM.replace("x2=214", "x2=224"),   # mask/box dims
        SYNTH_STREAM.replace("x2=214", "x2=104"),   # degenerate box
        SYNTH_STREAM.replace(box, box + box, 1),    # duplicate box
    ]
    i = SYNTH_STREAM.index("data=208")
    variants.append(SYNTH_STREAM[:i + 40] + "####" + SYNTH_STREAM[i + 44:])
    for v in variants:
        try:
            parse_sam_stream(v)
        except ValueError:
            continue
        raise AssertionError("corrupt stream variant accepted")


@check("runner: mismatched keyframe dimensions raise before any call")
def _():
    import jaga.sam_runner as sr

    def transport(b, p):
        raise RuntimeError("transport must not be called")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        runner = sr.SamRunner(Path(td), transport)
        frames = [(0.0, ROOT / "tests" / "fixtures" / "frame.png"),
                  (0.5, ROOT / "tests" / "fixtures" / "overlay_frame.png")]
        try:
            runner.run_keyframes("clip", frames)
        except ValueError:
            return
        raise AssertionError("mixed keyframe geometry accepted")


@check("runner: a transport serving another model is refused")
def _():
    import jaga.sam_runner as sr
    import tempfile

    def transport(b, p):
        raise RuntimeError("transport must not be called")
    transport.model_id = "sam-other"
    with tempfile.TemporaryDirectory() as td:
        runner = sr.SamRunner(Path(td), transport)
        try:
            runner.run_keyframes(
                "clip", [(0.0, ROOT / "tests" / "fixtures" / "frame.png")])
        except ValueError:
            return
        raise AssertionError("model-mismatched transport accepted")


@check("features: velocity across a missed keyframe is unmeasured")
def _():
    spec = [(0.0, [inst((100, 20, 150, 160), 40)]),
            (0.5, []),
            (1.0, [inst((100, 60, 150, 200), 40)])]
    tracks, _ = build_tracks(spec, W, H)
    assert len(tracks) == 1
    f = tracks[0].frames[-1]
    assert f.spans_gap is True and f.dt_s == 1.0
    assert f.vy_hps is None and f.speed_hps is None


@check("features: association is by box IoU")
def _():
    a = inst((100, 20, 150, 160), 40)
    b = inst((105, 25, 155, 165), 40)
    tracks, _ = build_tracks([(0.0, [a]), (0.5, [b])], W, H)
    assert len(tracks) == 1 and len(tracks[0].frames) == 2
    f = tracks[0].frames[-1]
    assert f.match_iou is not None and 0.5 < f.match_iou < 1.0


@check("features: incoherent producer geometry raises")
def _():
    bad = inst((100, 20, 150, 160), 40)
    bad.mask_area_px = 999999
    try:
        build_tracks([(0.0, [bad])], W, H)
    except ValueError:
        pass
    else:
        raise AssertionError("area larger than the box accepted")
    bad2 = inst((100, 20, 150, 160), 40)
    bad2.bottom_y = 999
    try:
        build_tracks([(0.0, [bad2])], W, H)
    except ValueError:
        return
    raise AssertionError("bottom_y outside the box accepted")


@check("stillness: a too-short observed span is unknown (direct)")
def _():
    from jaga.features import stillness as _still
    tracks, _ = build_tracks(
        [(0.0, [inst((100, 20, 150, 160), 40)]),
         (0.5, [inst((100, 20, 150, 160), 40)])], W, H)
    assert _still(tracks[0], W, H) is None


@check("rules: verdict carries the effective parameter snapshot")
def _():
    v = run_rules(FALL_FRAMES, timing(2.9, 3.7))
    assert v.params["view"] == "side"
    assert v.params["rules"]["descent_min_s"] == 0.15
    assert v.params["stillness"]["stillness_min_span_s"] == 2.5
    assert v.params["params_overridden"] is False
    tracks, _ = build_tracks(FALL_FRAMES, W, H)
    from jaga.rules import evaluate as _ev
    v2 = _ev(tracks, W, H, timing=timing(2.9, 3.7),
             params={"descent_min_s": 0.9})
    assert v2.params["rules"]["descent_min_s"] == 0.9
    assert v2.params["params_overridden"] is True


@check("rules: the fallback distrusts weakly associated fast steps")
def _():
    from jaga.features import KeyframeFeatures, Track
    from jaga.rules import evaluate

    def frame(t, cy, elong, tilt, vy=None, iou=None, gap=False):
        return KeyframeFeatures(
            t_s=t, object_id="0", box=(100, 50, 160, 200),
            area_px=5000, aspect=1.0, elongation=elong,
            axis_tilt_deg=tilt, centroid_x=0.4, centroid_y=cy,
            floor_proximity=cy + 0.2, bottom_band_share=0.1,
            speed_hps=vy, vy_hps=vy, dt_s=0.5, spans_gap=gap,
            match_iou=iou)

    def track(step_iou):
        frames = [frame(0.0, 0.30, 1.6, 85.0),
                  frame(0.5, 0.30, 1.6, 85.0, iou=0.95),
                  frame(1.0, 0.45, 1.8, 45.0, vy=0.1, iou=0.9),
                  frame(1.5, 0.75, 2.5, 10.0, vy=0.6, iou=step_iou)]
        frames += [frame(t, 0.75, 2.5, 10.0, vy=0.0, iou=0.95)
                   for t in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)]
        return Track(track_id=1, frames=frames)

    v = evaluate([track(0.9)], W, H)
    d = v.phases["descent"]
    assert d.detail.get("source") == "keyframes", (v.label, v.phases)
    assert d.detail.get("vy_hps") == 0.6
    assert d.detail.get("match_iou") == 0.9
    assert v.label == "uncertain"  # duration unmeasured by design

    v2 = evaluate([track(0.1)], W, H)
    d2 = v2.phases["descent"]
    assert d2.detail.get("source") != "keyframes", (v2.label, v2.phases)


@check("rules: a fast step spanning a gap never authors a fallback")
def _():
    from jaga.features import KeyframeFeatures, Track
    from jaga.rules import evaluate

    def frame(t, cy, elong, tilt, vy=None, gap=False):
        return KeyframeFeatures(
            t_s=t, object_id="0", box=(100, 50, 160, 200),
            area_px=5000, aspect=1.0, elongation=elong,
            axis_tilt_deg=tilt, centroid_x=0.4, centroid_y=cy,
            floor_proximity=cy + 0.2, bottom_band_share=0.1,
            speed_hps=vy, vy_hps=vy, dt_s=0.5 if not gap else 1.0,
            spans_gap=gap, match_iou=0.95)
    frames = [frame(0.0, 0.30, 1.6, 85.0),
              frame(0.5, 0.30, 1.6, 85.0),
              frame(1.5, 0.75, 2.5, 10.0, vy=0.9, gap=True),
              frame(2.0, 0.75, 2.5, 10.0, vy=0.0),
              frame(2.5, 0.75, 2.5, 10.0, vy=0.0),
              frame(3.0, 0.75, 2.5, 10.0, vy=0.0),
              frame(4.0, 0.75, 2.5, 10.0, vy=0.0),
              frame(5.0, 0.75, 2.5, 10.0, vy=0.0)]
    v = evaluate([Track(track_id=1, frames=frames)], W, H)
    d = v.phases["descent"]
    assert d.detail.get("source") != "keyframes", (v.label, v.phases)


@check("harness: a segment parse failure is pipeline_error, not a crash")
def _():
    import csv as _csv
    from jaga.harness import run_clip

    row = {"clip_id": "tiny-fixture", "label": "adl", "view": "side",
           "video_path": "tests/fixtures/tiny.mp4"}

    class BoomRunner:
        def run_keyframes(self, clip_id, window):
            raise ValueError("corrupt evidence")
    rec = run_clip(ROOT / row["video_path"], row, BoomRunner(),
                   ROOT / "cache")
    assert rec["outcome"] == "pipeline_error", rec["outcome"]
    assert "corrupt evidence" in rec["segments"][0]["pipeline_error"]

    class CrashRunner:
        def run_keyframes(self, clip_id, window):
            raise RuntimeError("SAM helper failed (1): boom")
    rec2 = run_clip(ROOT / row["video_path"], row, CrashRunner(),
                    ROOT / "cache")
    assert rec2["outcome"] == "pipeline_error", rec2["outcome"]
    assert "RuntimeError" in rec2["segments"][0]["pipeline_error"]


@check("features: mask dims, elongation, tilt ranges are enforced")
def _():
    from jaga.sam_parse import Instance

    def inst(**kw):
        base = dict(object_id="0", box=(10, 10, 60, 90),
                    mask_area_px=2000, mask_width=50, mask_height=80,
                    centroid_xy=(25.0, 40.0), bottom_y=70,
                    bottom_band_share=0.1, elongation=1.6,
                    axis_tilt_deg=80.0)
        base.update(kw)
        return Instance(**base)
    good = [(0.0, [inst()])]
    build_tracks(good, W, H)  # control: coherent geometry passes
    for bad in (dict(mask_width=49), dict(elongation=0.5),
                dict(elongation=60.0), dict(axis_tilt_deg=120.0)):
        try:
            build_tracks([(0.0, [inst(**bad)])], W, H)
        except ValueError:
            continue
        raise AssertionError(f"incoherent geometry accepted: {bad}")


@check("parse: a malformed parser result raises ValueError only")
def _():
    import meta_sam_parser as _msp
    from jaga.sam_parse import parse_sam_stream as _parse

    class _FakeParsed:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def final_result(self):
            return object()  # no .outcome, no .diagnostics

    real = _msp.parse_responses_stream
    _msp.parse_responses_stream = lambda events, fmt: _FakeParsed()
    try:
        try:
            _parse(SYNTH_STREAM)
        except ValueError:
            return
        except AttributeError:
            raise AssertionError("AttributeError escaped the contract")
        raise AssertionError("malformed result accepted")
    finally:
        _msp.parse_responses_stream = real


# ------------------------------------------------------- secret audit
def _audit_module():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "audit_history", ROOT / "scripts" / "audit_history.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _verified_value():
    # The amendment's first verified checksum, built from fragments so
    # this file's own text carries no literal 64-hex string.
    return "".join(["f968ee85b519ecc6", "9d9506b55f4ad659",
                    "02d49c49052e1d80", "b1b906b666607895"])


@check("audit: a labelled, verified checksum is suppressed (amendment)")
def _():
    audit = _audit_module()
    body = "  SHA-256: `" + _verified_value() + "`"
    context = "- `results/split_dev.csv` — 215 rows\n" + body
    assert audit.amendment_suppresses(body, context)


@check("audit: suppression also works by live recomputation")
def _():
    import hashlib as _hl
    audit = _audit_module()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "provenance.bin"
        p.write_bytes(b"jaga audit test fixture")
        value = _hl.sha256(b"jaga audit test fixture").hexdigest()
        body = "  SHA-256: `" + value + "`"
        context = "checksum of " + str(p) + "\n" + body
        assert audit.amendment_suppresses(body, context)


@check("audit: a labelled hash that does not recompute still fails")
def _():
    audit = _audit_module()
    body = "  SHA-256: `" + "a" * 64 + "`"
    context = "- `results/split_dev.csv` — 215 rows\n" + body
    assert not audit.amendment_suppresses(body, context)


@check("audit: an unlabelled 64-hex string still fails")
def _():
    audit = _audit_module()
    body = "  (" + "b" * 64 + ")."
    assert not audit.amendment_suppresses(body, body)


@check("audit: credential patterns are never exempted")
def _():
    audit = _audit_module()
    cred = "api" + "_key = " + '"' + "X" * 24 + '"'
    assert audit.credential_hit(cred)
    # even on a line that also carries a labelled, verified checksum
    mixed = "SHA-256: `" + _verified_value() + "` " + cred
    assert audit.credential_hit(mixed)


def _audit_main_on(files):
    """End-to-end classification (added 2026-10-30): build a
    throwaway git repo whose only commit adds `files` ({path: text}),
    run audit_history.main() inside it, return (exit_code, output).
    The unit checks above exercise amendment_suppresses() in isolation;
    these exercise the classification main() actually applies."""
    import contextlib as _ctx
    import io as _io
    import subprocess as _sp
    audit = _audit_module()
    with tempfile.TemporaryDirectory() as td:
        def _git(*args):
            _sp.run(["git", "-C", td, *args], check=True,
                    capture_output=True, text=True)
        _git("init", "-q")
        for rel, text in files.items():
            p = Path(td) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        _git("add", "-A")
        _git("-c", "user.name=Audit Checks",
             "-c", "user.email=audit-checks@example.invalid",
             "-c", "commit.gpgsign=false",
             "commit", "-q", "-m", "fixture")
        out = _io.StringIO()
        cwd = os.getcwd()
        try:
            os.chdir(td)
            with _ctx.redirect_stdout(out):
                rc = audit.main()
        finally:
            os.chdir(cwd)
        return rc, out.getvalue()


@check("audit main: a labelled non-matching hash in prose fails (D1)")
def _():
    rc, out = _audit_main_on({
        "notes.md": "The sha256 is " + "c" * 64 + " for this download.\n"})
    assert rc == 1 and "AUDIT FAILED" in out, out


@check("audit main: verified hash naming the wrong file fails (D2)")
def _():
    rc, out = _audit_main_on({
        "notes.md": "- `results/split_test.csv` — 68 rows\n"
                    "  SHA-256: `" + _verified_value() + "`\n"})
    assert rc == 1 and "AUDIT FAILED" in out, out


@check("audit main: verified hash with no file named fails (D2)")
def _():
    rc, out = _audit_main_on({
        "notes.md": "Recorded checksum, SHA-256: `"
                    + _verified_value() + "`\n"})
    assert rc == 1 and "AUDIT FAILED" in out, out


@check("audit main: verified hash, labelled, correct file, suppressed")
def _():
    rc, out = _audit_main_on({
        "notes.md": "- `results/split_dev.csv` — 215 rows\n"
                    "  SHA-256: `" + _verified_value() + "`\n"})
    assert rc == 0 and "SUPPRESSED" in out, out


@check("audit main: a credential pattern inside a results table fails")
def _():
    cred = "api" + "_key = " + '"' + "X" * 24 + '"'
    rc, out = _audit_main_on({
        "results/fixture.csv": "file,note\nSubject9.zip," + cred + "\n"})
    assert rc == 1 and "AUDIT FAILED" in out, out


# ------------------------------------------------------- alerts (D2)
@check("alerts: the full disposition table (D1 semantics, monotonic)")
def _():
    from jaga.alerts import Disposition, tier_for, TIER_CHECK, \
        TIER_NONE, TIER_URGENT
    A = dict(adjudicator_verdict=None, adjudicator_usable=False)
    F = dict(adjudicator_verdict="fall", adjudicator_usable=True)
    B = dict(adjudicator_verdict="benign", adjudicator_usable=True)
    U = dict(adjudicator_verdict="uncertain", adjudicator_usable=True)
    X = dict(adjudicator_verdict="fall", adjudicator_usable=False)
    U_, C, N = TIER_URGENT, TIER_CHECK, TIER_NONE
    table = {
        "fall_candidate": {**{"A": U_, "F": U_, "B": N, "U": U_, "X": U_}},
        "uncertain":      {**{"A": C, "F": U_, "B": N, "U": C, "X": C}},
        "negative":       {**{"A": N, "F": U_, "B": N, "U": C, "X": N}},
        "no_evidence":    {**{"A": C, "F": U_, "B": N, "U": C, "X": C}},
        "mystery_label":  {**{"A": C, "F": U_, "B": N, "U": C, "X": C}},
    }
    states = {"A": A, "F": F, "B": B, "U": U, "X": X}
    for rules_label, row in table.items():
        for state, want in row.items():
            got = tier_for(Disposition("c", rules_label,
                                       **states[state]))[0]
            assert got == want, (rules_label, state, got, want)
    # failure signals raise the floor to CHECK, never lower a tier
    assert tier_for(Disposition("c", "fall_candidate",
                                pipeline_error="x"))[0] == U_
    assert tier_for(Disposition("c", "negative", "fall", True,
                                pipeline_error="x"))[0] == U_
    t, reason = tier_for(Disposition("c", "negative",
                                     pipeline_error="SAM down"))
    assert t == C and "fail-safe" in reason
    assert tier_for(Disposition("c", "negative",
                                verification_failed=True))[0] == C
    assert tier_for(Disposition("c", "negative",
                                "benign", True,
                                verification_failed=True))[0] == C


@check("alerts: ack stops escalation; silence walks the whole ladder")
def _():
    from jaga.alerts import AlertLadder, Disposition
    now = [1000.0]
    ladder = AlertLadder(["nearby", "family", "service"],
                         ack_window_s=900.0, clock=lambda: now[0])
    a = ladder.dispatch(Disposition("clip1", "uncertain", "fall", True))
    b = ladder.dispatch(Disposition("clip2", "uncertain"))
    # duplicate dispatch of a live clip returns the same alert
    again = ladder.dispatch(Disposition("clip1", "uncertain"))
    assert again is a and a.events[-1]["kind"] == "duplicate_dispatch"
    now[0] += 901.0
    esc = ladder.tick()
    assert {x.alert_id for x in esc} == {a.alert_id, b.alert_id}
    assert a.events[-1]["to"] == "family"
    ladder.acknowledge(a.alert_id, "family")
    # multi-hop timing is from the LAST event, not from creation:
    # 899 s after the escalation nothing happens, at 900 s it hops
    now[0] += 899.0
    assert ladder.tick() == []
    now[0] += 1.0
    esc2 = ladder.tick()
    assert {x.alert_id for x in esc2} == {b.alert_id}
    assert b.events[-1]["to"] == "service"
    # final hop: exhaustion is a state, not a "someone notified" return
    now[0] += 901.0
    assert ladder.tick() == []
    assert b.state == "exhausted"
    # a late ack is recorded, not a crash
    ladder.acknowledge(b.alert_id, "service")
    assert b.state == "acknowledged"
    assert b.events[-1]["kind"] == "late_acknowledged"
    # an ack from a non-recipient and an unknown id are clean errors
    for bad_call in (lambda: ladder.acknowledge("nope", "family"),
                     lambda: ladder.acknowledge(a.alert_id, "stranger")):
        try:
            bad_call()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid acknowledgement accepted")
    none_alert = ladder.dispatch(Disposition("clip3", "negative"))
    assert none_alert is None and ladder.log[-1]["clip_id"] == "clip3"
    # the ladder state round-trips
    import json as _json
    restored = AlertLadder.from_dict(
        _json.loads(_json.dumps(ladder.to_dict())),
        clock=lambda: now[0])
    assert restored.get(a.alert_id).state == "acknowledged"
    assert restored.recipients == ["nearby", "family", "service"]


@check("alerts: the consent layer is a labeled mock, not wired in")
def _():
    from jaga.alerts import AlertLadder, ConsentProfile, Disposition
    profile = ConsentProfile(rooms=["living room"], recipients=["x"])
    d = profile.to_dict()
    assert d["status"] == "designed, not implemented"
    assert profile.implemented is False
    ladder = AlertLadder(["nearby"], clock=lambda: 0.0)
    a = ladder.dispatch(Disposition("clip", "uncertain", "fall", True))
    assert a is not None  # dispatch ignores the mock entirely


if __name__ == "__main__":
    sys.exit(main())
