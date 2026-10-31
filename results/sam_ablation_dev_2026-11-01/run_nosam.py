"""No-SAM arm of the post-hoc supplementary SAM ablation (dev set only).

Implements METHODS.md as amended by METHODS_AMENDMENT.md (2026-11-01).
Per descent window, three motion-stillness readings are computed —
v1 (core anchor, activity-level rule; the original definition), v2a
(run anchor, activity-level rule), v2 (run anchor, new-burst rule;
the arm of record) — and dispositions are aggregated under each, so
the construction sensitivity is a reported number. The headline
column `nosam_disposition` is v2.

Reads ~/workspace/jaga read-only; writes only under
~/workspace/jaga-ablation/. Makes no SAM calls. Refuses to run if the
live config hash differs from the gate's recorded hash.
"""
from __future__ import annotations

import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path.home() / "workspace" / "jaga"
OUT = Path.home() / "workspace" / "jaga-ablation"
sys.path.insert(0, str(ROOT / "src"))

from jaga.config import FEATURES, RULES, TIMING, VIEWS, config_hash  # noqa: E402
from jaga.frames import probe_duration  # noqa: E402
from jaga.motion_gate import gate_clip  # noqa: E402
from jaga.timing import _smooth, analyze, series_from_video  # noqa: E402

EXPECTED_HASH = "6d7c03257b12ab00"
PREC = {"confirmed": 0, "escalated": 1, "pipeline_error": 2,
        "cleared": 3, "gate_miss": 4}
LABEL_ORDER = {"fall_candidate": 0, "uncertain": 1, "negative": 2,
               "no_evidence": 3}
SEG_DISP = {"fall_candidate": "confirmed", "uncertain": "escalated",
            "negative": "cleared", "no_evidence": "escalated"}
VARIANTS = ("v1", "v2a", "v2")

# Effective rules params for the side view, merged exactly as
# rules._evaluate merges them (RULES + VIEWS[view]).
P = dict(RULES)
P.update(VIEWS["side"])


def event_id(row: dict) -> str:
    """The gate driver's event construction, copied verbatim."""
    if row["dataset"] == "up_fall":
        return (f"upfall:S{row['subject']}:A{row['activity']}"
                f":T{row['trial']}")
    return row["clip_id"]


def video_path(row: dict) -> Path:
    if row["dataset"] == "up_fall":
        return ROOT / "data" / "up_fall" / "clips" / (
            Path(row["filename"]).stem + ".mp4")
    return ROOT / row["video_path"]


def _level_reading(af_smooth: np.ndarray, low: float, fps: float,
                   anchor: float) -> tuple[bool | None, dict]:
    """Activity-level stillness over [anchor, anchor + window].

    Satisfied iff the smoothed changed-area fraction never exceeds
    the clip's activity level `low` at any observed step; None iff
    the observed span inside the window is shorter than the frozen
    minimum span (the shipped stillness span rule, applied to the
    dense series). Step i has time (i + 1) / fps.
    """
    win_s = FEATURES["stillness_window_s"]
    min_span = FEATURES["stillness_min_span_s"]
    times = (np.arange(len(af_smooth)) + 1) / fps
    idx = np.where((times >= anchor) & (times <= anchor + win_s))[0]
    if len(idx) < 2:
        return None, {"note": "fewer than two motion steps in window"}
    span = float(times[idx[-1]] - times[idx[0]])
    detail = {"observed_span_s": round(span, 2),
              "low_level": round(float(low), 6)}
    if span < min_span:
        detail["note"] = "insufficient observed span after descent"
        return None, detail
    peak = float(af_smooth[idx].max())
    detail["peak_af_in_window"] = round(peak, 6)
    return peak <= low, detail


def stillness_readings(af_smooth, low, fps, iv, intervals) -> dict:
    """The three motion-stillness readings for one descent window."""
    v1, d1 = _level_reading(af_smooth, low, fps, iv.core_offset_s)
    v2a, d2a = _level_reading(af_smooth, low, fps, iv.offset_s)
    win_s = FEATURES["stillness_window_s"]
    min_span = FEATURES["stillness_min_span_s"]
    series_end = len(af_smooth) / fps
    observed = min(iv.offset_s + win_s, series_end) - iv.offset_s
    if observed < min_span:
        v2, d2 = None, {"observed_span_s": round(float(observed), 2),
                        "note": "insufficient observed span after descent"}
    else:
        new = [j for j in intervals
               if j is not iv and iv.offset_s - 1e-9 <= j.onset_s
               < iv.offset_s + win_s]
        v2 = not new
        d2 = {"observed_span_s": round(float(observed), 2),
              "new_interval_onset_s": (round(new[0].onset_s, 2)
                                       if new else None)}
    return {"v1": v1, "v2a": v2a, "v2": v2,
            "detail": {"v1": d1, "v2a": d2a, "v2": d2}}


def _compose(descent_ok: bool, still: bool | None) -> tuple[str, list[str]]:
    """The shipped _evaluate_window composition with posture = None."""
    contradictions = ["stillness"] if still is False else []
    if descent_ok is False:
        dur_reason = "descent duration outside window"
        if contradictions:
            return "negative", [dur_reason,
                                "person moved after the descent"]
        return "uncertain", [dur_reason + "; remaining evidence is "
                                         "fall-consistent or unmeasured"]
    if contradictions:
        return "negative", ["person moved after the descent"]
    return "uncertain", ["fall-consistent, but unmeasured: "
                         "pre_posture, post_posture"]


def evaluate_window(iv, on_slack: bool, af_smooth, low, fps,
                    intervals) -> dict:
    dur = iv.core_duration_s
    descent_ok = P["descent_min_s"] <= dur <= P["descent_max_s"]
    readings = stillness_readings(af_smooth, low, fps, iv, intervals)
    labels, reasons = {}, {}
    for v in VARIANTS:
        labels[v], reasons[v] = _compose(descent_ok, readings[v])
    return {"onset_s": round(iv.core_onset_s, 2),
            "offset_s": round(iv.core_offset_s, 2),
            "run_onset_s": round(iv.onset_s, 2),
            "run_offset_s": round(iv.offset_s, 2),
            "duration_s": round(dur, 2),
            "descent_satisfied": descent_ok,
            "stillness": {v: readings[v] for v in VARIANTS},
            "stillness_detail": readings["detail"],
            "labels": labels, "reasons": reasons,
            "admitted_on_slack": on_slack,
            "progress": 1 if descent_ok else 0}


def evaluate_segment(seg, timing, af_smooth, low, fps) -> dict:
    """One gate segment under the no-SAM arm (see METHODS.md)."""
    slack = P["overlap_slack_s"]
    cands = []
    for iv in timing.intervals:
        if (iv.offset_s >= seg.start_s - slack
                and iv.onset_s <= seg.end_s + slack):
            contained = (iv.core_onset_s >= seg.start_s
                         and iv.core_offset_s <= seg.end_s)
            cands.append((iv, not contained))
    base = {"start_s": round(seg.start_s, 2), "end_s": round(seg.end_s, 2)}
    if not cands:
        base.update({"labels": {v: "uncertain" for v in VARIANTS},
                     "branch": "no_descent_interval",
                     "reasons": ["no descent interval observed and "
                                 "posture unmeasurable (no SAM evidence)"],
                     "windows": []})
        return base
    verdicts = [evaluate_window(iv, on_slack, af_smooth, low, fps,
                                timing.intervals)
                for iv, on_slack in cands]
    labels = {}
    for v in VARIANTS:
        best = min(verdicts,
                   key=lambda w: (LABEL_ORDER[w["labels"][v]],
                                  w["admitted_on_slack"], -w["progress"]))
        labels[v] = best["labels"][v]
    base.update({"labels": labels, "branch": "windowed",
                 "windows": verdicts})
    return base


def process_clip(row: dict) -> dict:
    rec = {"clip_id": row["clip_id"], "event_id": event_id(row),
           "dataset": row["dataset"], "label": row["label"]}
    video = video_path(row)
    try:
        duration = probe_duration(video)
        segments, _gs = gate_clip(video, duration)
    except Exception as e:
        rec["clip_dispositions"] = {v: "pipeline_error" for v in VARIANTS}
        rec["error"] = f"probe/gate stage: {type(e).__name__}: {e}"
        return rec
    rec["duration_s"] = round(duration, 2)
    rec["n_segments"] = len(segments)
    if not segments:
        rec["clip_dispositions"] = {v: "gate_miss" for v in VARIANTS}
        rec["segments"] = []
        return rec
    try:
        energy, area_frac, centroid_y, fps = series_from_video(video)
        timing = analyze(energy, area_frac, centroid_y, fps)
    except Exception as e:
        rec["clip_dispositions"] = {v: "pipeline_error" for v in VARIANTS}
        rec["error"] = f"timing stage: {type(e).__name__}: {e}"
        return rec
    # The clip's own activity level, computed exactly as timing.analyze
    # computes its hysteresis levels (same smoothing, same floor/p95).
    win = max(1, int(round(TIMING["smooth_s"] * fps)))
    af_smooth = _smooth(area_frac.astype(np.float64), win)
    floor = float(np.median(af_smooth))
    scale = float(np.percentile(af_smooth, 95))
    low = floor + TIMING["burst_low_frac"] * (scale - floor)
    rec["timing"] = {"floor": round(floor, 6), "p95": round(scale, 6),
                     "low_level": round(low, 6),
                     "n_intervals": len(timing.intervals)}
    seg_recs = [evaluate_segment(seg, timing, af_smooth, low, fps)
                for seg in segments]
    rec["segments"] = seg_recs
    rec["clip_dispositions"] = {
        v: min((SEG_DISP[s["labels"][v]] for s in seg_recs),
               key=lambda d: PREC[d])
        for v in VARIANTS}
    return rec


def event_disposition(clip_disps: list[str]) -> str:
    """The gate analyzer's event aggregation, copied verbatim."""
    for d in ("confirmed", "escalated", "pipeline_error", "cleared"):
        if d in clip_disps:
            return d
    return "gate_miss"


def main() -> None:
    h = config_hash()
    if h != EXPECTED_HASH:
        print(f"ABORT: config_hash() = {h}, expected {EXPECTED_HASH}")
        sys.exit(2)
    rows = list(csv.DictReader((ROOT / "results" / "split_dev.csv").open()))
    for r in rows:
        assert r["split"] == "dev", f"non-dev row: {r['clip_id']}"
        blob = json.dumps(r).lower()
        assert "coffee_room_02" not in blob and "coffee-room-02" not in blob
        assert not (r["dataset"] == "up_fall" and r["subject"] == "2")
    assert len(rows) == 215, f"expected 215 dev rows, got {len(rows)}"

    recs: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(process_clip, r): r["clip_id"] for r in rows}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            recs[rec["clip_id"]] = rec
            if i % 50 == 0 or i == len(rows):
                print(f"{i}/{len(rows)} clips", flush=True)

    rec_dir = OUT / "clip_records"
    rec_dir.mkdir(exist_ok=True)
    for cid, rec in sorted(recs.items()):
        (rec_dir / (cid.replace("/", "_") + ".json")).write_text(
            json.dumps(rec, indent=1))

    gate = {r["event_id"]: r for r in csv.DictReader(
        (ROOT / "results" / "gate_d1_dev_results.csv").open())}
    events: dict[str, list[dict]] = {}
    for r in rows:
        events.setdefault(event_id(r), []).append(recs[r["clip_id"]])

    # Sanity: event set and clip membership must reproduce the gate's.
    assert set(events) == set(gate), (
        f"event set mismatch: only-mine={sorted(set(events)-set(gate))[:5]} "
        f"only-gate={sorted(set(gate)-set(events))[:5]}")
    for eid, clips in events.items():
        mine = sorted(c["clip_id"] for c in clips)
        theirs = sorted(gate[eid]["clip_ids"].split(";"))
        assert mine == theirs, f"clip membership mismatch for {eid}"

    out_rows = []
    for eid in sorted(events):
        clips = events[eid]
        g = gate[eid]
        row_out = {
            "event_id": eid, "dataset": g["dataset"], "label": g["label"],
            "n_clips": len(clips),
            "clip_ids": ";".join(sorted(c["clip_id"] for c in clips)),
            "sam_rules_disposition": g["rules_disposition"],
        }
        for v in VARIANTS:
            disp = event_disposition(
                [c["clip_dispositions"][v] for c in clips])
            row_out[f"nosam_{v}_disposition" if v != "v2"
                     else "nosam_disposition"] = disp
        row_out["agree"] = (row_out["nosam_disposition"]
                            == g["rules_disposition"])
        out_rows.append(row_out)
    with (OUT / "nosam_dev_dispositions.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    for v, col in (("v2 (arm of record)", "nosam_disposition"),
                   ("v1", "nosam_v1_disposition"),
                   ("v2a", "nosam_v2a_disposition")):
        agree = sum(1 for r in out_rows
                    if r[col] == r["sam_rules_disposition"])
        print(f"{v}: agree {agree}/191, differ {191 - agree}")


if __name__ == "__main__":
    main()
