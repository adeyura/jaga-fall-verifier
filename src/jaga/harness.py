"""Evaluation harness: manifest clips through the whole pipeline.

One clip record per manifest row, and a cascade summary that keeps
every stage's losses visible: gate misses, SAM anomaly failures,
rules outcomes by ground-truth label, adjudicator usability and
agreement. No stage's failures are laundered into a later stage's
denominator, and a clip the pipeline could not process is recorded
as a pipeline failure, never as a negative.

The harness is configuration, not conclusions: whether adjudication
runs, and on which rules labels, is a caller parameter recorded in
every output. Scored runs freeze those choices in the spec first.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from . import rules as rules_mod
from .adjudicator import Verdict, adjudicate
from .config import config_hash
from .frames import probe_duration, sample_frames
from .motion_gate import gate_clip
from .sam_runner import AnomalyError, SamRunner
from .timing import timing_from_video
from .traces import traces_text

_LABEL_ORDER = {"fall_candidate": 0, "uncertain": 1, "negative": 2,
                "no_evidence": 3}


def _merge_labels(labels: list[str]) -> str:
    if not labels:
        return "no_evidence"
    return min(labels, key=lambda x: _LABEL_ORDER.get(x, 9))


def run_clip(video: Path, row: dict, runner: SamRunner, cache_root: Path,
             keyframe_fps: float = 2.0,
             adjudicate_labels: frozenset[str] = frozenset(),
             transport: Callable | None = None,
             image_picker: Callable | None = None) -> dict:
    clip_id = row["clip_id"]
    rec: dict = {"clip_id": clip_id, "label": row["label"],
                 "camera": row.get("camera", ""),
                 "config_hash": config_hash(), "segments": []}
    t0 = time.monotonic()
    duration = probe_duration(video)
    rec["duration_s"] = round(duration, 2)
    segments, gate_stats = gate_clip(video, duration)
    from dataclasses import asdict
    rec["gate"] = {"n_segments": len(segments),
                   "flagged_s": round(sum(s.end_s - s.start_s
                                          for s in segments), 2),
                   "zero_candidate": len(segments) == 0,
                   "stats": asdict(gate_stats)}
    if not segments:
        rec["outcome"] = "gate_miss"
        rec["wall_s"] = round(time.monotonic() - t0, 2)
        return rec

    timing = timing_from_video(video)
    rec["timing_descent"] = (
        None if timing.descent is None else {
            "onset_s": round(timing.descent.onset_s, 2),
            "core_duration_s": round(timing.descent.core_duration_s, 2),
            "run_duration_s": round(timing.descent.duration_s, 2),
            "peak_area_frac": round(timing.descent.peak_area_frac, 3)})
    frames_dir = cache_root / "keyframes" / clip_id
    all_frames = sample_frames(video, frames_dir, keyframe_fps)
    labels: list[str] = []
    for seg in segments:
        seg_rec: dict = {"start_s": round(seg.start_s, 2),
                         "end_s": round(seg.end_s, 2)}
        window = [(t, p) for t, p in all_frames
                  if seg.start_s - 1e-9 <= t <= seg.end_s + 1e-9]
        seg_rec["keyframes"] = len(window)
        if len(window) < 2:
            seg_rec["rules_label"] = "no_evidence"
            labels.append("no_evidence")
            rec["segments"].append(seg_rec)
            continue
        try:
            run = runner.run_keyframes(clip_id, window)
        except AnomalyError as e:
            seg_rec["pipeline_error"] = str(e)
            seg_rec["run"] = e.run.to_dict()
            rec["segments"].append(seg_rec)
            rec["outcome"] = "pipeline_error"
            rec["wall_s"] = round(time.monotonic() - t0, 2)
            return rec
        verdict = rules_mod.evaluate(run.tracks, run.frame_w,
                                     run.frame_h, timing=timing)
        seg_rec["run"] = run.to_dict()
        seg_rec["rules_label"] = verdict.label
        seg_rec["rules_reasons"] = verdict.reasons
        seg_rec["rules_phases"] = {
            name: {"satisfied": ph.satisfied, "detail": ph.detail}
            for name, ph in verdict.phases.items()}
        labels.append(verdict.label)
        if (transport is not None
                and verdict.label in adjudicate_labels):
            images = image_picker(window) if image_picker else []
            adj: Verdict = adjudicate(
                transport, traces_text(clip_id, run, timing, verdict),
                images)
            seg_rec["adjudication"] = {
                "usable": adj.usable, "verdict": adj.verdict,
                "confidence": adj.confidence, "error": adj.error,
                "discriminator": adj.discriminator,
                "usage": adj.usage}
        rec["segments"].append(seg_rec)
    rec["outcome"] = _merge_labels(labels)
    rec["wall_s"] = round(time.monotonic() - t0, 2)
    return rec


def cascade(records: list[dict]) -> dict:
    """Stage-by-stage loss accounting over a set of clip records."""
    falls = [r for r in records if r["label"] == "fall"]
    adl = [r for r in records if r["label"] != "fall"]
    def count(rs, outcome):
        return sum(1 for r in rs if r.get("outcome") == outcome)
    adj_usable = adj_total = adj_agree = 0
    sam_cost = 0.0
    cost_known = True
    for r in records:
        for s in r["segments"]:
            run = s.get("run") or {}
            if run.get("est_cost_usd") is None:
                if run:
                    cost_known = False
            else:
                sam_cost += run["est_cost_usd"]
            a = s.get("adjudication")
            if a is not None:
                adj_total += 1
                adj_usable += 1 if a["usable"] else 0
                rules_pos = s["rules_label"] == "fall_candidate"
                adj_pos = a["verdict"] == "fall"
                adj_agree += 1 if (a["usable"] and rules_pos == adj_pos) else 0
    return {
        "clips": len(records),
        "falls": len(falls), "adl": len(adl),
        "gate_miss_falls": count(falls, "gate_miss"),
        "gate_miss_adl": count(adl, "gate_miss"),
        "pipeline_errors": sum(1 for r in records
                               if r.get("outcome") == "pipeline_error"),
        "rules_fall_candidates_on_falls": count(falls, "fall_candidate"),
        "rules_fall_candidates_on_adl": count(adl, "fall_candidate"),
        "rules_uncertain_on_falls": count(falls, "uncertain"),
        "rules_uncertain_on_adl": count(adl, "uncertain"),
        "sam_est_cost_usd": round(sam_cost, 4) if cost_known else None,
        "adjudications": adj_total,
        "adjudicator_usable": adj_usable,
        "adjudicator_agrees_with_rules": adj_agree,
    }
