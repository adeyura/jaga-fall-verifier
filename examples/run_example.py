"""Offline replay of one pinned clip — no API key, no network, no video.

Runs the shipped pipeline's downstream stages LIVE on the pinned SAM 3.1
output of one real scored clip (UP-Fall Subject 1, Activity 1, Trial 1,
Camera 1 — a staged fall), using this repository's own code:

  pinned SAM instances -> jaga.features.build_tracks (IoU tracking +
  kinematics) -> jaga.rules.evaluate (the frozen state machine) ->
  jaga.traces.traces_text (the evidence form) -> jaga.alerts.tier_for
  (the D2 alert ladder, pivot configuration).

Two stages need the video file itself, which this repo never ships
(dataset media stays out; see README "Datasets"), so they are replayed
from the scored run's record and labeled as replayed wherever they
appear: the motion gate's segment bounds and the local timing
intervals. The adjudication block printed at the end is likewise the
dev gate's RECORDED output, kept for provenance; Muse Spark is not
part of the shipped configuration and nothing here calls it.

The replay verifies itself: rebuilt track features are compared
against the run's recorded features, and the live rules verdict must
equal the recorded verdict, or this script exits nonzero.

Usage: python3 examples/run_example.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jaga import rules as rules_mod  # noqa: E402
from jaga.alerts import Disposition, tier_for  # noqa: E402
from jaga.features import build_tracks  # noqa: E402
from jaga.sam_parse import Instance  # noqa: E402
from jaga.sam_runner import ClipRun, KeyframeResult  # noqa: E402
from jaga.timing import Interval, TimingResult  # noqa: E402
from jaga.traces import traces_text  # noqa: E402

EX = ROOT / "examples" / "upfall_s1_a1t1_cam1"


def main() -> int:
    sam = json.loads((EX / "sam_keyframes.json").read_text())
    record = json.loads((EX / "record.json").read_text())
    W, H = sam["frame_w"], sam["frame_h"]
    clip_id = sam["clip_id"]

    print(f"=== Jaga offline example: {clip_id} "
          f"(event {sam['event']}, label: {sam['dataset_label']}) ===")
    print(f"SAM model {sam['model']}, prompt {sam['prompt']!r}, "
          f"{W}x{H}, segment {sam['segment']['start_s']}-"
          f"{sam['segment']['end_s']} s (segment bounds replayed from "
          f"the scored run's motion-gate record)")
    print(f"Gate record (replayed): {record['gate']['n_segments']} "
          f"segment(s), {record['gate']['flagged_s']} s flagged")

    # 1. Rebuild SAM instances and tracks with the repo's own code.
    kf_pairs: list[tuple[float, list[Instance]]] = []
    kf_results: list[KeyframeResult] = []
    for k in sam["keyframes"]:
        insts = []
        for i in k["instances"]:
            l, t, r, b = i["box"]
            insts.append(Instance(
                object_id=i["object_id"], box=tuple(i["box"]),
                mask_area_px=i["area_px"], mask_width=r - l,
                mask_height=b - t,
                centroid_xy=(i["centroid_x"] * W - l,
                             i["centroid_y"] * H - t),
                bottom_y=round(i["floor_proximity"] * H) - t - 1,
                bottom_band_share=i["bottom_band_share"],
                elongation=i["elongation"],
                axis_tilt_deg=i["axis_tilt_deg"]))
        kf_pairs.append((k["t_s"], insts))
        kf_results.append(KeyframeResult(
            t_s=k["t_s"], instances=insts, parse_stats={},
            from_cache=True, images_billed=0))
    tracks, stats = build_tracks(kf_pairs, W, H)
    print(f"\n[features] {stats['instances_total']} instances -> "
          f"{stats['tracks_total']} tracks "
          f"({stats['single_keyframe_tracks']} single-keyframe)")

    # Verification 1: rebuilt features vs the run's recorded features.
    built = {t.track_id: {f.t_s: f for f in t.frames} for t in tracks}
    max_drift, compared = 0.0, 0
    for rt in record["recorded_tracks"]:
        for rf in rt["frames"]:
            f = built[rt["track_id"]][rf["t_s"]]
            compared += 1
            for key in ("area_px", "aspect", "elongation",
                        "axis_tilt_deg", "centroid_x", "centroid_y",
                        "floor_proximity", "bottom_band_share"):
                a, b = getattr(f, key), rf[key]
                if a is not None and b is not None:
                    max_drift = max(max_drift, abs(a - b))
    print(f"[verify] track features: {compared} frames compared, "
          f"max drift vs recorded = {max_drift:.4f} "
          f"(record rounding is 4 decimals)")

    # 2. Timing intervals, replayed from the record (see record.json's
    # timing_reconstruction_note for exactly what is and is not stored).
    intervals = [Interval(
        onset_s=iv["onset_s"], offset_s=iv["offset_s"],
        duration_s=iv["duration_s"], core_onset_s=iv["core_onset_s"],
        core_offset_s=iv["core_offset_s"],
        peak_area_frac=iv["peak_area_frac"], peak_energy=0.0,
        peak_vy_hps=0.0, net_centroid_drop=0.0)
        for iv in record["timing_intervals_pinned"]]
    timing = TimingResult(intervals=intervals, descent=intervals[0],
                          floor=0.0, scale_p95=0.0, fps=18.0)
    print(f"[timing] intervals replayed from record: "
          + ", ".join(f"core {iv.core_onset_s:.2f}-"
                      f"{iv.core_offset_s:.2f} s" for iv in intervals))

    # 3. Rules verdict, live.
    verdict = rules_mod.evaluate(tracks, W, H, timing=timing,
                                 view=sam["view"])
    print(f"\n[rules] LIVE verdict: {verdict.label}")
    for reason in verdict.reasons:
        print(f"        - {reason}")
    rec_rules = record["recorded_rules"]
    ok = verdict.label == rec_rules["label"]
    print(f"[verify] recorded verdict was {rec_rules['label']!r}: "
          f"{'MATCH' if ok else 'MISMATCH'}")

    # 4. The evidence trace, generated live by the repo's traces code.
    run = ClipRun(clip_id=clip_id, keyframes=kf_results, tracks=tracks,
                  track_stats=stats, frame_w=W, frame_h=H,
                  model=sam["model"], prompt=sam["prompt"])
    print("\n[traces] evidence form (D3, traces only), generated live:")
    print(traces_text(clip_id, run, timing, verdict, view=sam["view"]))

    # 5. Alert ladder under the SHIPPED (pivot) configuration: no
    # adjudicator exists in the disposition path.
    disp = Disposition(clip_id=clip_id, rules_label=verdict.label)
    tier, why = tier_for(disp)
    print(f"[alerts] shipped configuration -> tier {tier!r} ({why})")

    # 6. Recorded dev-gate adjudication, for provenance only.
    adj = record["recorded_adjudication_dev_full_arm"]
    print(f"\n[recorded, not live] dev gate full arm adjudication: "
          f"verdict {adj['verdict']!r} at confidence "
          f"{adj['confidence']} (usable: {adj['usable']}). In the dev "
          f"gate this escalated the event; in the shipped configuration "
          f"there is no adjudicator and the rules verdict above stands "
          f"on its own.")

    print(f"\n=== replay {'OK' if ok else 'FAILED'}: live downstream "
          f"verdict == recorded verdict == {verdict.label!r} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
