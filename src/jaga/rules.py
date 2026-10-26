"""Rules state machine: does this candidate look like a fall?

The shape is the SPEC's: upright, then a rapid descent of 0.4 to 1.0 s,
then horizontal, then still for the window after the descent. The
rules stage is tuned for recall; precision is the adjudicator's job.
What this module owes the rest of the system is not a bare label but
an evidence record: every phase reports what was measured, and
missing evidence is a distinct outcome, never a quiet negative.

Labels:
- fall_candidate: all four phases satisfied on some track and some
  descent window.
- uncertain: the evidence is consistent with a fall but a required
  measurement is missing or unmeasurable — classically an unobserved
  descent with a clear upright-to-horizontal transition, a descent
  whose duration the keyframe rate cannot measure, or stillness that
  could not be observed for long enough. Uncertainty escalates to a
  human or to the adjudicator; it never defaults to silence.
- negative: the evidence contradicts a fall (descent measured too
  slow, never upright before, never horizontal after, or the person
  moved in the window after the descent, or no descent and no posture
  transition anywhere).
- no_evidence: no track with enough keyframes covers the window, so
  there is nothing to judge. Distinct from negative by design.

Every usable track is evaluated, and every local timing interval that
overlaps the track is tried as the descent window; verdicts merge
with fall_candidate over uncertain over negative. A fragmented faller
must not lose to a longer bystander track by construction.

Descent duration is the timing interval's CORE duration (width at
half prominence), never the whole envelope run: post-descent recovery
motion merges into the run's tail and would otherwise inflate the
measurement into a confident miss. The keyframe fallback (centroid
velocity between SAM keyframes) can establish that a fast downward
step happened, but its duration is the sampling gap, not a
measurement, so a fallback descent leaves the descent phase unknown
and caps the verdict at uncertain. Provenance is recorded on every
verdict.

Params overrides exist for development only; scored runs pass none,
and every verdict carries the config hash it was produced under.
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


def _phase_from_postures(frames, p: dict, target: str) -> "PhaseEvidence":
    """Majority posture over a phase's keyframes.

    Satisfied when at least half of the classified (non-abstaining)
    keyframes show the target posture and at least min_phase_frames
    keyframes could be classified at all; None when the phase does
    not hold enough classifiable evidence to mean anything.
    """
    postures = [_posture(f, p) for f in frames]
    classified = [x for x in postures if x != "abstain"]
    if len(classified) < p["min_phase_frames"]:
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
    config_hash: str = ""       # stamped by evaluate()


@dataclass
class _Window:
    onset: float                # descent core start (posture bracket)
    offset: float               # descent core end (posture bracket)
    duration: float | None      # None = unmeasurable (keyframe fallback)
    source: str                 # "local" | "keyframes"
    on_slack: bool = False
    gap_points: int = 0         # fallback only: fast points skipped
                                # because they spanned a missed keyframe
    run_onset_s: float | None = None  # local only: full envelope run


_ORDER = {"fall_candidate": 0, "uncertain": 1, "negative": 2}


def _windows_for_track(track: Track, timing: TimingResult | None,
                       p: dict) -> list[_Window]:
    frames = track.frames
    t_first, t_last = frames[0].t_s, frames[-1].t_s
    slack = p["overlap_slack_s"]
    windows: list[_Window] = []
    if timing is not None:
        for iv in timing.intervals:
            if iv.offset_s >= t_first - slack and iv.onset_s <= t_last + slack:
                contained = (iv.core_onset_s >= t_first
                             and iv.core_offset_s <= t_last)
                w = _Window(iv.core_onset_s, iv.core_offset_s,
                            iv.core_duration_s, "local",
                            on_slack=not contained,
                            run_onset_s=iv.onset_s)
                windows.append(w)
    if windows:
        return windows
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
        return [_Window(best[0], best[1], None, "keyframes",
                        gap_points=gap_points)]
    return []


def _evaluate_window(track: Track, w: _Window, frame_w: int,
                     frame_h: int, p: dict) -> RulesVerdict:
    frames = track.frames
    phases: dict[str, PhaseEvidence] = {}
    detail = {"onset_s": round(w.onset, 2), "offset_s": round(w.offset, 2),
              "duration_s": (None if w.duration is None
                             else round(w.duration, 2)),
              "source": w.source, "admitted_on_slack": w.on_slack}
    if w.run_onset_s is not None:
        detail["run_onset_s"] = round(w.run_onset_s, 2)
    if w.source == "keyframes":
        detail["gap_points_skipped"] = w.gap_points
    if w.duration is None:
        phases["descent"] = PhaseEvidence(None, detail)
    else:
        in_window = p["descent_min_s"] <= w.duration <= p["descent_max_s"]
        phases["descent"] = PhaseEvidence(in_window, detail)
        if not in_window:
            return RulesVerdict(
                "negative", track.track_id, w.source, phases,
                [f"descent duration {w.duration:.2f}s outside "
                 f"[{p['descent_min_s']}, {p['descent_max_s']}]"])

    pre = [f for f in frames if f.t_s < w.onset]
    phases["pre_posture"] = _phase_from_postures(pre, p, "upright")
    if phases["pre_posture"].satisfied is False:
        return RulesVerdict("negative", track.track_id, w.source, phases,
                            ["not upright before the descent"])
    post = [f for f in frames if f.t_s > w.offset]
    phases["post_posture"] = _phase_from_postures(post, p, "horizontal")
    if phases["post_posture"].satisfied is False:
        return RulesVerdict("negative", track.track_id, w.source, phases,
                            ["not horizontal after the descent"])

    still = stillness(track, frame_w, frame_h, after_s=w.offset,
                      anchor="start")
    if still is None:
        phases["stillness"] = PhaseEvidence(
            None, {"note": "insufficient observed span after descent"})
    else:
        phases["stillness"] = PhaseEvidence(
            still <= p["stillness_max_disp_h"],
            {"displacement_h": round(still, 4)})
        if still > p["stillness_max_disp_h"]:
            return RulesVerdict("negative", track.track_id, w.source,
                                phases, ["person moved after the descent"])

    unknown = [name for name, ph in phases.items() if ph.satisfied is None]
    if unknown:
        return RulesVerdict(
            "uncertain", track.track_id, w.source, phases,
            [f"fall-consistent, but unmeasured: {', '.join(unknown)}"])
    return RulesVerdict("fall_candidate", track.track_id, w.source,
                        phases, ["all four phases satisfied"])


def _evaluate_track_no_descent(track: Track, p: dict) -> RulesVerdict:
    """No descent was observed on this track. What does posture say?

    An upright-to-horizontal transition with no observed descent is
    the occluded-fall shape: missing evidence, so uncertain. No
    transition at all is contradictory evidence: negative.
    """
    frames = track.frames
    postures = [_posture(f, p) for f in frames]
    need = p["min_phase_frames"]
    for k in range(1, len(frames)):
        pre = [x for x in postures[:k] if x != "abstain"]
        post = [x for x in postures[k:] if x != "abstain"]
        if len(pre) < need or len(post) < need:
            continue
        if (pre.count("upright") * 2 >= len(pre)
                and post.count("horizontal") * 2 >= len(post)):
            phases = {"descent": PhaseEvidence(
                None, {"note": "no descent interval or fast keyframe drop"}),
                "transition": PhaseEvidence(
                    True, {"split_at_s": frames[k].t_s,
                           "postures": postures})}
            return RulesVerdict(
                "uncertain", track.track_id, None, phases,
                ["upright-to-horizontal transition with the descent "
                 "itself unobserved"])
    return RulesVerdict(
        "negative", track.track_id, None,
        {"descent": PhaseEvidence(
            False, {"note": "no descent and no posture transition"})},
        ["no descent evidence and no posture transition"])


def _evaluate_track(track: Track, timing: TimingResult | None,
                    frame_w: int, frame_h: int, p: dict) -> RulesVerdict:
    windows = _windows_for_track(track, timing, p)
    if not windows:
        return _evaluate_track_no_descent(track, p)
    verdicts = [_evaluate_window(track, w, frame_w, frame_h, p)
                for w in windows]
    best = min(verdicts, key=lambda v: _ORDER[v.label])
    if len(verdicts) > 1:
        best.reasons.append(
            f"best of {len(verdicts)} descent windows on this track")
    return best


def _evaluate(tracks: list[Track], frame_w: int, frame_h: int,
              timing: TimingResult | None = None,
              params: dict | None = None) -> RulesVerdict:
    p = dict(RULES)
    if params:
        p.update(params)
    usable = [t for t in tracks if len(t.frames) >= p["min_track_frames"]]
    if not usable:
        return RulesVerdict("no_evidence", None, None,
                            reasons=["no track with enough keyframes"])
    verdicts = [_evaluate_track(t, timing, frame_w, frame_h, p)
                for t in usable]
    best = min(verdicts, key=lambda v: _ORDER[v.label])
    if len(verdicts) > 1:
        best.reasons.append(
            f"verdict from track {best.track_id} of {len(verdicts)} "
            "evaluated tracks")
    return best


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
