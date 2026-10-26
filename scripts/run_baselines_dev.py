"""Dev baselines (SPEC D5): the pipeline must beat the cheap
alternatives, not just a strawman.

Two trivial baselines over the same manifest rows and the same
motion gate as the pipeline:

1. aspect-only: a threshold rule on mask geometry alone — a track
   whose elongation reaches >= 2.0 while its floor proximity reaches
   >= 0.7 in the same keyframe neighborhood is a "fall". No timing,
   no stillness, no view model.
2. spark-only: Muse Spark adjudicates every gated candidate
   directly from a neutral evidence pack (timing summary + the
   primary track's keyframe table + the chosen evidence images).
   No rules stage anywhere: no phases, no verdict, no view model.

Usage: python scripts/run_baselines_dev.py [n_falls] [n_adl] [evidence]
Writes cache/runs/dev_baselines.json. Development evidence only.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_eval_dev import vm_transport                     # noqa: E402
from jaga.adjudicator import adjudicate                   # noqa: E402
from jaga.frames import probe_duration, sample_frames     # noqa: E402
from jaga.harness import overlay_picker                   # noqa: E402
from jaga.motion_gate import gate_clip                    # noqa: E402
from jaga.sam_runner import SamRunner, helper_transport   # noqa: E402
from jaga.timing import timing_from_video                 # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
TAG = "DEV ONLY — NOT A RESULT"


def aspect_only(run) -> str:
    """fall if some track is elongated AND low in the same keyframe."""
    for tr in run.tracks:
        for f in tr.frames:
            if (f.elongation is not None and f.elongation >= 2.0
                    and f.floor_proximity >= 0.7):
                return "fall"
    return "benign"


def neutral_traces(clip_id: str, run, timing) -> str:
    lines = [f"Clip {clip_id}: fall-event verification, raw evidence "
             "only (no rules stage has seen this clip)."]
    if timing is not None and timing.descent is not None:
        d = timing.descent
        lines.append(
            f"Local motion timing: a descent-like burst runs "
            f"{d.onset_s:.2f}-{d.offset_s:.2f} s; its core (width at "
            f"half prominence) is {d.core_duration_s:.2f} s; peak "
            f"changed-area fraction {d.peak_area_frac:.3f}.")
    else:
        lines.append("Local motion timing: no descent-like burst "
                     "was measured.")
    if run.tracks:
        tr = max(run.tracks, key=lambda t: sum(f.area_px for f in t.frames))
        lines.append(f"Primary person track ({len(tr.frames)} "
                     "keyframes): t, area px, elongation, tilt deg, "
                     "floor proximity:")
        for f in tr.frames:
            lines.append(
                f"  {f.t_s:.1f}s area={f.area_px} "
                f"elong={f.elongation} tilt={f.axis_tilt_deg} "
                f"floor={f.floor_proximity:.2f}")
    else:
        lines.append("No person track was built from the keyframes.")
    return "\n".join(lines)


def main() -> None:
    n_falls = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_adl = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    rows = list(csv.DictReader((ROOT / "results" / "manifest_draft.csv").open()))
    selected = ([r for r in rows if r["label"] == "fall"][:n_falls]
                + [r for r in rows if r["label"] != "fall"][:n_adl])
    cache_root = ROOT / "cache"
    runner = SamRunner(cache_root, helper_transport(HELPER),
                       keep_rasters=True)
    out = []
    for row in selected:
        video = ROOT / row["video_path"]
        clip_id = row["clip_id"]
        duration = probe_duration(video)
        segments, _gate_stats = gate_clip(video, duration)
        rec = {"clip_id": clip_id, "label": row["label"],
               "aspect_only": None, "spark_only": None}
        if segments:
            seg = segments[0]
            frames_dir = cache_root / "keyframes" / clip_id
            all_frames = sample_frames(video, frames_dir, 2.0)
            window = [(t, p) for t, p in all_frames
                      if seg.start_s - 1e-9 <= t <= seg.end_s + 1e-9]
            if len(window) >= 2:
                run = runner.run_keyframes(clip_id, window)
                timing = timing_from_video(video)
                rec["aspect_only"] = aspect_only(run)
                images, labels = overlay_picker(window, run)
                adj = adjudicate(vm_transport,
                                 neutral_traces(clip_id, run, timing),
                                 images, image_labels=labels)
                rec["spark_only"] = {
                    "usable": adj.usable, "verdict": adj.verdict,
                    "confidence": adj.confidence, "error": adj.error}
        out.append(rec)
        print(f"{TAG}: {clip_id} aspect={rec['aspect_only']} "
              f"spark={rec['spark_only']}")
    out_dir = cache_root / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev_baselines.json").write_text(json.dumps(
        {"dev": True, "records": out}, indent=2))
    for name, key in (("aspect-only", "aspect_only"),
                      ("spark-only", "spark_only")):
        falls_hit = sum(1 for r in out if r["label"] == "fall"
                        and (r[key] == "fall" if key == "aspect_only"
                             else (r[key] or {}).get("verdict") == "fall"))
        adl_fp = sum(1 for r in out if r["label"] != "fall"
                     and (r[key] == "fall" if key == "aspect_only"
                          else (r[key] or {}).get("verdict") == "fall"))
        print(f"{TAG}: {name}: falls called fall {falls_hit}/"
              f"{sum(1 for r in out if r['label'] == 'fall')}, "
              f"ADL called fall {adl_fp}/"
              f"{sum(1 for r in out if r['label'] != 'fall')}")


if __name__ == "__main__":
    main()
