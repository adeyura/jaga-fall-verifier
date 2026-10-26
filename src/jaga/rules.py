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

from .config import RULES, VIEWS
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
    # The effective parameter VALUES that produced this verdict
    # (rules + view + stillness), snapshotted by _evaluate. A hash
    # alone cannot be read back without the historical config, and
    # it does not move when a caller overrides a parameter; this
    # snapshot can and does. params_overridden flags dev overrides.
    params: dict = field(default_factory=dict)
    alternatives: list[dict] = field(default_factory=list)
    # every (track, window) evaluation that did not win, compact:
    # {track_id, onset_s, label, first_reason} — a negative result
    # must show whether the real descent was among the rejected
    # windows and what rejected it, not just the winning record.


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
    vy_hps: float | None = None       # fallback only: authoring step
    match_iou: float | None = None    # fallback only: its association
    low_iou_points: int = 0           # fallback only: fast points
                                      # skipped for weak association


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
    low_iou_points = 0
    for a, b in zip(frames, frames[1:]):
        if b.spans_gap:
            gap_points += 1
            continue
        if b.vy_hps is None or b.vy_hps < p["descent_vy_min_hps"]:
            continue
        if (b.match_iou is not None
                and b.match_iou < p["fallback_min_match_iou"]):
            # A fast step on a weakly associated frame is the
            # identity-switch shape: the centroid "fell" because the
            # tracker swapped which mask it was following.
            low_iou_points += 1
            continue
        if best is None or b.vy_hps > best[2]:
            best = (a.t_s, b.t_s, b.vy_hps, b.match_iou)
    if best is not None:
        return [_Window(best[0], best[1], None, "keyframes",
                        gap_points=gap_points, vy_hps=best[2],
                        match_iou=best[3],
                        low_iou_points=low_iou_points)]
    return []


def _evaluate_window(track: Track, w: _Window, frame_w: int,
                     frame_h: int, p: dict,
                     still: dict | None = None) -> RulesVerdict:
    frames = track.frames
    phases: dict[str, PhaseEvidence] = {}
    detail = {"onset_s": round(w.onset, 2), "offset_s": round(w.offset, 2),
              "duration_s": (None if w.duration is None
                             else round(w.duration, 2)),
              "source": w.source, "admitted_on_slack": w.on_slack}
    if w.run_onset_s is not None:
        detail["run_onset_s"] = round(w.run_onset_s, 2)
    if w.source == "keyframes":
        detail["vy_hps"] = w.vy_hps
        detail["match_iou"] = w.match_iou
        detail["gap_points_on_track"] = w.gap_points
        detail["low_iou_points_skipped"] = w.low_iou_points
    if w.duration is None:
        phases["descent"] = PhaseEvidence(None, detail)
    else:
        in_window = p["descent_min_s"] <= w.duration <= p["descent_max_s"]
        phases["descent"] = PhaseEvidence(in_window, detail)

    ceiling = p.get("posture_model") == "ceiling"
    pre = [f for f in frames if f.t_s < w.onset]
    post = [f for f in frames if f.t_s > w.offset]
    if ceiling:
        # Ceiling model: before the descent there is
        # usually nobody in frame to classify (enter-and-fall), and
        # image tilt does not encode body orientation from above.
        # The pre phase is unobservable by construction; the post
        # phase is the presence of a PERSON-SIZED mask — a frame
        # count alone would let the known pocket-sized ceiling
        # fixture author "person present" evidence. The verdict in
        # this view therefore caps at uncertain by design.
        phases["pre_posture"] = PhaseEvidence(None, {
            "note": "unobservable by construction in the ceiling view"})
        floor_px = p["min_person_area_frac"] * frame_w * frame_h
        sized = [f for f in post if f.area_px >= floor_px]
        if len(post) < p["min_phase_frames"]:
            phases["post_posture"] = PhaseEvidence(None, {
                "note": "too few keyframes after the descent"})
        elif not sized:
            phases["post_posture"] = PhaseEvidence(False, {
                "note": "no person-sized mask after the descent",
                "areas_px": [f.area_px for f in post],
                "floor_px": round(floor_px)})
        elif len(sized) * 2 >= len(post):
            phases["post_posture"] = PhaseEvidence(True, {
                "note": "person-sized mask present after the descent",
                "elongations": [f.elongation for f in post],
                "areas_px": [f.area_px for f in post]})
        else:
            phases["post_posture"] = PhaseEvidence(None, {
                "note": "person-sized mask in a minority of "
                        "post-descent keyframes",
                "areas_px": [f.area_px for f in post],
                "floor_px": round(floor_px)})
    else:
        phases["pre_posture"] = _phase_from_postures(pre, p, "upright")
        phases["post_posture"] = _phase_from_postures(post, p, "horizontal")

    sk = still or {}
    disp = stillness(track, frame_w, frame_h, after_s=w.offset,
                     anchor="start",
                     window_s=sk.get("stillness_window_s"),
                     min_span_s=sk.get("stillness_min_span_s"),
                     max_gap_s=sk.get("stillness_max_gap_s"))
    if disp is None:
        phases["stillness"] = PhaseEvidence(
            None, {"note": "insufficient observed span after descent"})
    else:
        phases["stillness"] = PhaseEvidence(
            disp <= p["stillness_max_disp_h"],
            {"displacement_h": round(disp, 4)})

    # Composition. A measured descent outside the window is evidence,
    # not a veto (P3 safeguard): it produces a confident
    # negative only alongside a contradiction in another phase. When
    # everything else is fall-consistent, the case escalates.
    def _reason(name: str) -> str:
        if ceiling and name == "post_posture":
            return "no person-sized mask after the descent"
        return {
            "pre_posture": "not upright before the descent",
            "post_posture": "not horizontal after the descent",
            "stillness": "person moved after the descent",
        }[name]

    contradictions = [n for n in ("pre_posture", "post_posture", "stillness")
                      if phases[n].satisfied is False]
    if phases["descent"].satisfied is False:
        dur = (f"descent duration {w.duration:.2f}s outside "
               f"[{p['descent_min_s']}, {p['descent_max_s']}]")
        if contradictions:
            return RulesVerdict("negative", track.track_id, w.source,
                                phases, [dur, _reason(contradictions[0])])
        return RulesVerdict(
            "uncertain", track.track_id, w.source, phases,
            [dur + "; remaining evidence is fall-consistent or "
                   "unmeasured"])
    if contradictions:
        return RulesVerdict("negative", track.track_id, w.source, phases,
                            [_reason(contradictions[0])])
    unknown = [n for n, ph in phases.items() if ph.satisfied is None]
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
    if p.get("posture_model") == "ceiling":
        # Enter-and-fall with the burst itself missed: an elongated,
        # person-sized person present in the track's later part is
        # the same missing-evidence shape in this view's terms. The
        # size test matters: the pocket-sized ceiling fixture is a
        # thin sliver (elongation ~3.4) and would otherwise author
        # this escalation on its own.
        floor_px = (p["min_person_area_frac"] * track.frame_w
                    * track.frame_h)
        later = frames[len(frames) // 2:]
        qualifying = [f for f in later
                      if f.elongation is not None
                      and f.elongation >= p["min_elongation"]
                      and f.area_px >= floor_px]
        if len(qualifying) >= p["min_phase_frames"]:
            return RulesVerdict(
                "uncertain", track.track_id, None,
                {"descent": PhaseEvidence(
                    None, {"note": "no descent interval observed"}),
                 "post_posture": PhaseEvidence(
                     True, {"note": "elongated person-sized mask "
                                    "present later in the track"})},
                ["elongated person present with the descent itself "
                 "unobserved"])
        return RulesVerdict(
            "negative", track.track_id, None,
            {"descent": PhaseEvidence(
                False, {"note": "no descent and no elongated "
                                 "person-sized mask in the later track"})},
            ["no descent evidence and no elongated person-sized mask"])
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
    classified = [x for x in postures if x != "abstain"]
    if len(classified) < need:
        # Posture itself is unmeasurable on this track (axes
        # undefined, masks too round): with the descent also
        # unobserved, nothing here is contradictory evidence.
        return RulesVerdict(
            "uncertain", track.track_id, None,
            {"descent": PhaseEvidence(
                None, {"note": "no descent observed and posture "
                                "unmeasurable on this track"}),
             "transition": PhaseEvidence(
                 None, {"postures": postures})},
            ["descent unobserved and posture unmeasurable"])
    return RulesVerdict(
        "negative", track.track_id, None,
        {"descent": PhaseEvidence(
            False, {"note": "no descent and no posture transition"})},
        ["no descent evidence and no posture transition"])


def _progress(v: RulesVerdict) -> int:
    """How far a verdict got through the phases, for ranking negatives.

    When every window is negative, the record worth showing is the one
    that progressed furthest — it is the most informative rejection.
    """
    score = 0
    for name in ("descent", "pre_posture", "post_posture", "stillness"):
        ph = v.phases.get(name)
        if ph is not None and ph.satisfied is True:
            score += 1
        else:
            break
    return score


def _evaluate_track(track: Track, timing: TimingResult | None,
                    frame_w: int, frame_h: int, p: dict,
                    still: dict | None = None) -> RulesVerdict:
    windows = _windows_for_track(track, timing, p)
    if not windows:
        return _evaluate_track_no_descent(track, p)
    verdicts = [_evaluate_window(track, w, frame_w, frame_h, p, still)
                for w in windows]

    def _window_rank(v: RulesVerdict):
        d = v.phases.get("descent")
        slack = bool(d and d.detail.get("admitted_on_slack"))
        return (_ORDER[v.label], slack,
                0 if v.timing_source == "local" else 1, -_progress(v))

    best = min(verdicts, key=_window_rank)
    for v in verdicts:
        if v is best:
            continue
        d = v.phases.get("descent")
        best.alternatives.append({
            "track_id": v.track_id,
            "onset_s": (None if d is None
                        else d.detail.get("onset_s")),
            "label": v.label,
            "first_reason": v.reasons[0] if v.reasons else ""})
    if len(verdicts) > 1:
        best.reasons.append(
            f"best of {len(verdicts)} descent windows on this track")
    return best


def _evaluate(tracks: list[Track], frame_w: int, frame_h: int,
              timing: TimingResult | None = None,
              params: dict | None = None,
              view: str = "side") -> RulesVerdict:
    if view not in VIEWS:
        raise ValueError(f"unknown view: {view!r}")
    p = dict(RULES)
    p.update(VIEWS[view])
    from .config import FEATURES
    p.setdefault("min_person_area_frac",
                 FEATURES["min_person_area_frac"])
    if params:
        p.update(params)
    from .config import FEATURES as _F
    # The stillness parameters in force — including any params
    # override — computed ONCE here and passed to the stillness call
    # itself, so the snapshot below is the values the call consumed,
    # not a second reading of the same dicts.
    eff_still = {k: (params or {}).get(k, _F[k]) for k in (
        "stillness_window_s", "stillness_min_span_s",
        "stillness_max_gap_s")}
    snapshot = {
        "view": view,
        "rules": dict(p),
        "stillness": dict(eff_still),
        "params_overridden": bool(params),
    }
    usable = [t for t in tracks if len(t.frames) >= p["min_track_frames"]]
    if not usable:
        v = RulesVerdict("no_evidence", None, None,
                         reasons=["no track with enough keyframes"])
        v.params = snapshot
        return v
    verdicts = [_evaluate_track(t, timing, frame_w, frame_h, p,
                                eff_still)
                for t in usable]
    # Rank by label, then phase progress, then evidence mass: when
    # two tracks reach the same verdict, the one carrying more mask
    # area is the person-sized evidence. Without the area term a
    # persistent pocket-sized false positive (a ceiling fixture SAM
    # returns in every keyframe) wins ties over the actual person
    # purely by track order, and downstream stages inherit the wrong
    # track's record.
    area = {t.track_id: sum(f.area_px for f in t.frames) for t in usable}
    best = min(verdicts,
               key=lambda v: (_ORDER[v.label], -_progress(v),
                              -area.get(v.track_id, 0)))
    for v in verdicts:
        if v is best:
            continue
        best.alternatives.append({
            "track_id": v.track_id, "onset_s": None, "label": v.label,
            "first_reason": v.reasons[0] if v.reasons else ""})
        best.alternatives.extend(v.alternatives)
    if len(verdicts) > 1:
        best.reasons.append(
            f"verdict from track {best.track_id} of {len(verdicts)} "
            "evaluated tracks")
    best.params = snapshot
    return best


_STILL_KEYS = ("stillness_window_s", "stillness_min_span_s",
               "stillness_max_gap_s")


def params_snapshot(view: str = "side",
                    params: dict | None = None) -> dict:
    """The effective-parameter snapshot evaluate() would stamp.

    Exposed so run records that never reach a verdict (gate miss,
    pipeline error) still carry the parameters in force.
    """
    if view not in VIEWS:
        raise ValueError(f"unknown view: {view!r}")
    from .config import FEATURES as _F, RULES as _R
    p = dict(_R)
    p.update(VIEWS[view])
    p.setdefault("min_person_area_frac",
                 _F["min_person_area_frac"])
    if params:
        p.update(params)
    eff_still = {k: (params or {}).get(k, _F[k]) for k in _STILL_KEYS}
    return {"view": view, "rules": p, "stillness": eff_still,
            "params_overridden": bool(params)}


def evaluate(tracks: list[Track], frame_w: int, frame_h: int,
             timing: TimingResult | None = None,
             params: dict | None = None,
             view: str = "side") -> RulesVerdict:
    """Evaluate the rules state machine (see _evaluate).

    Every verdict is stamped with the current config hash AND a
    snapshot of the effective parameter values (verdict.params), so
    a result record can be reproduced from the record alone. The
    params argument is a development facility: overridden verdicts
    carry params_overridden=True in that snapshot and must not be
    scored.
    """
    from .config import config_hash
    v = _evaluate(tracks, frame_w, frame_h, timing=timing, params=params,
                  view=view)
    v.config_hash = config_hash()
    return v
