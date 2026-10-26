"""Regression checks for the Jaga pipeline units.

Run:  PYTHONPATH=<meta_sam_parser site-packages>:src \
        python3 tests/run_checks.py

Plain asserts, no framework: this file is the protection the frozen
run relies on, so it must run anywhere the pipeline runs. The SAM
stream fixture (a real captured response) is dataset-derived data and
is NOT committed; checks that need it look for it in the locations in
_FIXTURE_CANDIDATES or $JAGA_FIXTURE and skip with a notice when it is
absent. Every other check is self-contained.
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
_FIXTURE_CANDIDATES = [
    os.environ.get("JAGA_FIXTURE", ""),
    str(ROOT / "tests" / "fixtures" / "sam_stream_adl01.txt"),
    "/tmp/jaga-cache/hour3/sam_stream_adl01.txt",
]
FIXTURE = next((p for p in _FIXTURE_CANDIDATES if p and Path(p).exists()),
               None)

RESULTS = []


def check(name):
    def deco(fn):
        try:
            fn()
            RESULTS.append((name, "PASS", ""))
        except Exception as e:  # noqa: BLE001 - the harness reports, not hides
            RESULTS.append((name, "FAIL", f"{type(e).__name__}: {e}"))
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


def run_rules(spec, tm=None):
    tracks, _ = build_tracks(spec, W, H)
    return evaluate(tracks, W, H, timing=tm)


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


@check("rules: slow lie-down is negative (descent too slow)")
def _():
    assert run_rules(FALL_FRAMES, timing(0.2, 2.4)).label == "negative"


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
GOOD = ('{"for_fall": "a", "for_benign": "b", "data_quality": "c", '
        '"discriminator": "d", "verdict": "fall", "confidence": 0.8}')


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
if FIXTURE:
    stream = Path(FIXTURE).read_text()
    from jaga.sam_parse import parse_sam_stream

    @check("parse: real stream yields the two known instances")
    def _():
        insts, stats = parse_sam_stream(stream)
        assert sorted(i.mask_area_px for i in insts) == [4178, 4902]
        assert stats["boxes_without_masks"] == 0
        assert stats["tiny_instances"] == 0

    @check("parse: garbage SSE line raises")
    def _():
        try:
            parse_sam_stream("this is not an SSE line\n" + stream)
        except ValueError:
            return
        raise AssertionError("garbage line skipped")

    @check("parse: malformed data payload raises as ValueError")
    def _():
        try:
            parse_sam_stream("data: {broken\n" + stream)
        except ValueError:
            return
        raise AssertionError("malformed payload accepted")

    @check("parse: mask without a box raises")
    def _():
        import re as _re
        out, removed = [], 0
        for ln in stream.splitlines():
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
else:
    skip("parse: fixture checks", "no SAM stream fixture found")


# ------------------------------------------------------- runner
@check("runner: anomaly gate includes superseded masks and carries the run")
def _():
    import jaga.sam_runner as sr

    real_parse = sr.parse_sam_stream

    def fake_parse(text):
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
            runner = sr.SamRunner(Path(td), lambda b, p: "unused")
            try:
                runner.run_keyframes("clip", [(0.0, frame)])
            except sr.AnomalyError as e:
                assert e.run.anomalies["masks_superseded"] == 2
                assert e.run.model == "sam-3.1"
                return
            raise AssertionError("anomaly gate did not fire")
    finally:
        sr.parse_sam_stream = real_parse


def main() -> int:
    failed = 0
    for name, status, note in RESULTS:
        print(f"{status:4}  {name}" + (f"  — {note}" if note else ""))
        failed += status == "FAIL"
    print(f"\n{len(RESULTS)} checks, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
