"""Evidence traces: the text record of what the pipeline measured.

One builder for the adjudicator input and for human inspection, so the
model reads exactly what a human reader would read. Facts only: measured
values and the rules stage's phase record. The conclusion the reader
draws is their own; this text never editorializes beyond the labels
the stages themselves produced.
"""
from __future__ import annotations


def traces_text(clip_id: str, run, timing, verdict, view: str = "side") -> str:
    lines = [f"Clip: {clip_id} (public fall-dataset clip, staged, lab room)"]
    lines.append(f"Camera view: {view}.")
    if view == "ceiling":
        lines.append(
            "This view looks straight down. The subject typically "
            "enters the frame and falls within about half a second, "
            "so pre-descent posture is unobservable by construction, "
            "and image-plane axis tilt does not encode body "
            "orientation from above; elongation and mask area are "
            "the informative shape measures here.")
    if timing.descent is not None:
        d = timing.descent
        lines.append(
            f"Local dense timing: descent onset {d.onset_s:.2f}s, "
            f"core duration {d.core_duration_s:.2f}s (the descent "
            f"itself; full envelope run {d.duration_s:.2f}s), peak "
            f"changed-area {d.peak_area_frac:.2f}.")
    else:
        lines.append("Local dense timing: no descent interval found.")
    lines.append(f"Rules stage verdict: {verdict.label} "
                 f"(timing source: {verdict.timing_source})")
    for name, ph in verdict.phases.items():
        lines.append(f"  phase {name}: satisfied={ph.satisfied} {ph.detail}")
    lines.append("Primary track keyframes (t, axis tilt deg, elongation, "
                 "mask area px, floor proximity, base-band share, speed):")
    track = next((t for t in run.tracks
                  if t.track_id == verdict.track_id), None)
    if track is not None:
        for f in track.frames:
            tilt = ("abstain" if f.axis_tilt_deg is None
                    else f"{f.axis_tilt_deg:.0f}")
            lines.append(
                f"  {f.t_s:.1f}s tilt={tilt} "
                f"elong={f.elongation} area={f.area_px} "
                f"floor={f.floor_proximity:.2f} "
                f"band={f.bottom_band_share:.2f} "
                f"speed={f.speed_hps if f.speed_hps is None else round(f.speed_hps, 3)}")
    lines.append(f"SAM keyframes: {len(run.keyframes)}, "
                 f"empty: {run.empty_keyframes}, "
                 f"tracks: {run.track_stats}")
    return "\n".join(lines)
