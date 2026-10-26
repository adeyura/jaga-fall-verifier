"""Rules state machine: does this candidate look like a fall?

The shape is the SPEC's: upright, then a rapid descent of 0.4 to 1.0 s,
then horizontal, then still for at least 3 s. The rules stage is tuned
for recall; precision is the adjudicator's job. What this module owes
the rest of the system is not a bare label but an evidence record:
every phase reports what was measured, and missing evidence is a
distinct outcome, never a quiet negative.

Labels:
- fall_candidate: all four phases satisfied.
- uncertain: a descent and a horizontal posture are present but a
  required measurement is missing (classically stillness, when the
  track ends before the stillness window can be observed). Uncertainty
  escalates to a human or to the adjudicator; it never defaults to
  silence.
- negative: the evidence contradicts a phase (no descent, descent too
  slow, never horizontal, or the person is up and moving afterwards).
- no_evidence: no track with at least two keyframes covers the window,
  so there is nothing to judge. Distinct from negative by design.

Descent timing comes from the dense local timing module when it is
provided; the provenance is recorded on the verdict. The keyframe
fallback (centroid velocity between SAM keyframes) is quantized by the
keyframe rate and is labeled as such wherever the verdict travels.

Posture per keyframe comes from the mask's principal axis: tilt near
90 degrees is upright, near 0 is horizontal, and below a minimum
elongation the axis is ill-defined and the keyframe abstains.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import RULES
from .features import Track, stillness
from .timing import TimingResult


def _posture(frame, p: dict) -> str:
    if (frame.elongation is None or frame.axis_tilt_deg is None
            or frame.elongation < p["min_elongation"]):
        return "abstain"
    if frame.axis_tilt_deg >= p["upright_tilt_min_deg"]:
        return "upright"
    if frame.axis_tilt_deg <= p["horizontal_tilt_max_deg"]:
        return "horizontal"
    return "ambiguous"


def _phase_from_postures(frames, p: dict, target: str) -> PhaseEvidence:
    """Majority posture over a phase's keyframes.

    Satisfied when at least half of the classified (non-abstaining)
    keyframes show the target posture; None when no keyframe in the
    phase could be classified at all.
    """
    postures = [_posture(f, p) for f in frames]
    classified = [x for x in postures if x != "abstain"]
    if not classified:
        return PhaseEvidence(None, {"postures": postures})
    hits = postures.count(target)
    return PhaseEvidence(hits * 2 >= len(classified),
                         {"postures": postures})


@dataclass
class PhaseEvidence:
    satisfied: bool | None      # None = could not be measured
    detail: dict = field(default_factory=dict)


@dataclass
class RulesVerdict:
    label: str                  # fall_candidate | uncertain | negative |
                                # no_evidence
    track_id: int | None
    timing_source: str | None   # "local" | "keyframes" | None
    phases: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    config_hash: str = ""       # the frozen-config hash this verdict
                                # was produced under (config.config_hash)


def _evaluate(tracks: list[Track], frame_w: int, frame_h: int,
             timing: TimingResult | None = None,
             params: dict | None = None) -> RulesVerdict:
    p = dict(RULES)
    if params:
        p.update(params)
    usable = [t for t in tracks if len(t.frames) >= 2]
    if not usable:
        return RulesVerdict("no_evidence", None, None,
                            reasons=["no track with >= 2 keyframes"])
    track = max(usable, key=lambda t: (len(t.frames),
                                       sum(f.area_px for f in t.frames)))
    frames = track.frames
    t_first, t_last = frames[0].t_s, frames[-1].t_s

    # --- descent: locate the descent window --------------------------
    fallback_gap_points = 0
    descent_iv = None
    timing_source = None
    if timing is not None and timing.descent is not None:
        d = timing.descent
        if d.offset_s >= t_first - 1.0 and d.onset_s <= t_last + 1.0:
            descent_iv = (d.onset_s, d.offset_s, d.duration_s)
            timing_source = "local"
    if descent_iv is None:
        # Keyframe fallback. A velocity measured across a missed-
        # keyframe gap is an average over the gap, not a descent
        # sample: such points are skipped as descent evidence and the
        # skip is counted in the phase record.
        best = None
        gap_points = 0
        for a, b in zip(frames, frames[1:]):
            if b.vy_hps is None or b.vy_hps < p["descent_vy_min_hps"]:
                continue
            if b.spans_gap:
                gap_points += 1
                continue
            if best is None or b.vy_hps > best[2]:
                best = (a.t_s, b.t_s, b.vy_hps)
        if best is not None:
            descent_iv = (best[0], best[1], best[1] - best[0])
            timing_source = "keyframes"
        fallback_gap_points = gap_points

    phases: dict[str, PhaseEvidence] = {}
    if descent_iv is None:
        phases["descent"] = PhaseEvidence(
            False, {"note": "no descent interval or fast keyframe drop"})
        return RulesVerdict("negative", track.track_id, None, phases,
                            ["no descent evidence"])
    onset, offset, duration = descent_iv
    in_window = p["descent_min_s"] <= duration <= p["descent_max_s"]
    descent_detail = {
        "onset_s": round(onset, 2), "offset_s": round(offset, 2),
        "duration_s": round(duration, 2), "source": timing_source}
    if timing_source == "keyframes":
        descent_detail["gap_points_skipped"] = fallback_gap_points
    phases["descent"] = PhaseEvidence(in_window, descent_detail)
    if not in_window:
        return RulesVerdict("negative", track.track_id, timing_source,
                            phases,
                            [f"descent duration {duration:.2f}s outside "
                             f"[{p['descent_min_s']}, {p['descent_max_s']}]"])

    # --- pre-descent posture -------------------------------------------
    pre = [f for f in frames if f.t_s < onset]
    phases["pre_posture"] = _phase_from_postures(pre, p, "upright")
    if phases["pre_posture"].satisfied is False:
        return RulesVerdict("negative", track.track_id, timing_source,
                            phases, ["not upright before the descent"])

    # --- post-descent posture ------------------------------------------
    post = [f for f in frames if f.t_s > offset]
    phases["post_posture"] = _phase_from_postures(post, p, "horizontal")
    if phases["post_posture"].satisfied is False:
        return RulesVerdict("negative", track.track_id, timing_source,
                            phases, ["not horizontal after the descent"])
    if phases["post_posture"].satisfied is None:
        return RulesVerdict("uncertain", track.track_id, timing_source,
                            phases, ["no classifiable keyframes after the descent"])

    # --- stillness (post-descent period only) ----------------------------
    still = stillness(track, frame_w, frame_h, after_s=offset)
    if still is None:
        phases["stillness"] = PhaseEvidence(
            None, {"note": "insufficient observed span after descent"})
        return RulesVerdict("uncertain", track.track_id, timing_source,
                            phases,
                            ["descent + horizontal, stillness unobserved"])
    phases["stillness"] = PhaseEvidence(
        still <= p["stillness_max_disp_h"],
        {"displacement_h": round(still, 4)})
    if still > p["stillness_max_disp_h"]:
        return RulesVerdict("negative", track.track_id, timing_source,
                            phases, ["person moved after the descent"])

    # --- recovery on another track ---------------------------------------
    # If association broke at the posture flip, the person getting up
    # appears as a new upright track after the descent. That evidence
    # must not be discarded, but it is not a plain negative either: an
    # upright track could be a second person. Escalate, do not dismiss.
    for other in usable:
        if other.track_id == track.track_id:
            continue
        after = [f for f in other.frames if f.t_s > offset]
        if len(after) >= 2 and any(_posture(f, p) == "upright"
                                   for f in after):
            return RulesVerdict(
                "uncertain", track.track_id, timing_source, phases,
                ["upright activity on another track after the descent; "
                 "cannot confirm the fallen person stayed down"])

    if phases["pre_posture"].satisfied is None:
        return RulesVerdict("uncertain", track.track_id, timing_source,
                            phases,
                            ["no classifiable keyframes before the descent"])
    return RulesVerdict("fall_candidate", track.track_id, timing_source,
                        phases, ["all four phases satisfied"])


def evaluate(tracks: list[Track], frame_w: int, frame_h: int,
             timing: TimingResult | None = None,
             params: dict | None = None) -> RulesVerdict:
    """Evaluate the rules state machine (see _evaluate).

    Every verdict is stamped with the current config hash, so a result
    record can always be tied to the parameter set that produced it.
    """
    from .config import config_hash
    v = _evaluate(tracks, frame_w, frame_h, timing=timing, params=params)
    v.config_hash = config_hash()
    return v
