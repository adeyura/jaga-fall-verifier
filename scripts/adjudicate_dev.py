"""Dev harness: full pipeline pass over one clip, ending in adjudication.

Usage: python scripts/adjudicate_dev.py <video> <clip_id>

Development plumbing only. Runs the SAM runner (responses cached, so
repeat runs are free), dense timing, the rules stage, and one Spark
adjudication with three raw keyframes attached. The evidence form is
still an open decision; this harness exists to prove the chain works
and to give the adjudicator prompt its first real input. Everything it
prints is labeled dev output and is never a result.
"""
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga import rules as rules_mod               # noqa: E402
from jaga.adjudicator import adjudicate           # noqa: E402
from jaga.frames import sample_frames             # noqa: E402
from jaga.sam_runner import SamRunner, helper_transport  # noqa: E402
from jaga.timing import timing_from_video         # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
TAG = "DEV ONLY — NOT A RESULT"


def vm_transport(body: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="jaga-adj-") as td:
        req = Path(td) / "body.json"
        resp = Path(td) / "resp.json"
        req.write_text(json.dumps(body))
        proc = subprocess.run(
            ["python3", str(HELPER), "chat-body", "--file", str(req),
             "--out", str(resp)],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(
                f"chat-body helper failed: {(proc.stderr or proc.stdout)[-300:]}")
        return json.loads(resp.read_text())


def traces_text(clip_id: str, run, timing, verdict) -> str:
    lines = [f"Clip: {clip_id} (public fall-dataset clip, staged, lab room)"]
    if timing.descent is not None:
        d = timing.descent
        lines.append(
            f"Local dense timing: descent onset {d.onset_s:.2f}s, "
            f"duration {d.duration_s:.2f}s, peak changed-area "
            f"{d.peak_area_frac:.2f}.")
    else:
        lines.append("Local dense timing: no descent interval found.")
    lines.append(f"Rules stage verdict: {verdict.label} "
                 f"(timing source: {verdict.timing_source})")
    for name, ph in verdict.phases.items():
        lines.append(f"  phase {name}: satisfied={ph.satisfied} {ph.detail}")
    lines.append("Primary track keyframes (t, axis tilt deg, elongation, "
                 "floor proximity, base-band share, speed):")
    track = next((t for t in run.tracks
                  if t.track_id == verdict.track_id), None)
    if track is not None:
        for f in track.frames:
            lines.append(
                f"  {f.t_s:.1f}s tilt={f.axis_tilt_deg:.0f} "
                f"elong={f.elongation:.2f} floor={f.floor_proximity:.2f} "
                f"band={f.bottom_band_share:.2f} "
                f"speed={f.speed_hps if f.speed_hps is None else round(f.speed_hps, 3)}")
    lines.append(f"SAM keyframes: {len(run.keyframes)}, "
                 f"empty: {run.empty_keyframes}, "
                 f"tracks: {run.track_stats}")
    return "\n".join(lines)


def main() -> None:
    video, clip_id = Path(sys.argv[1]), sys.argv[2]
    cache_root = ROOT / "cache"
    frames_dir = cache_root / "keyframes" / clip_id
    frames = sample_frames(video, frames_dir, 2.0)
    runner = SamRunner(cache_root, helper_transport(HELPER))
    run = runner.run_keyframes(clip_id, frames)
    timing = timing_from_video(video)
    verdict = rules_mod.evaluate(run.tracks, run.frame_w, run.frame_h,
                                 timing=timing)
    traces = traces_text(clip_id, run, timing, verdict)
    pick = [frames[0], frames[len(frames) // 2], frames[-1]]
    images = ["data:image/png;base64,"
              + base64.b64encode(p.read_bytes()).decode()
              for _, p in pick]
    adj = adjudicate(vm_transport, traces, images)
    record = {
        "clip_id": clip_id, "traces": traces,
        "rules_label": verdict.label,
        "adjudication": {
            "usable": adj.usable, "verdict": adj.verdict,
            "confidence": adj.confidence, "for_fall": adj.for_fall,
            "for_benign": adj.for_benign,
            "data_quality": adj.data_quality,
            "discriminator": adj.discriminator, "error": adj.error,
            "usage": adj.usage,
        },
    }
    out_dir = cache_root / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{clip_id}-adjudication.json").write_text(
        json.dumps(record, indent=2))
    print(f"{TAG}: rules={verdict.label} "
          f"adjudicator usable={adj.usable} verdict={adj.verdict} "
          f"confidence={adj.confidence} error={adj.error}")
    print(f"{TAG}: adjudicator discriminator: {adj.discriminator}")


if __name__ == "__main__":
    main()
