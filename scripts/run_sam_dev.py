"""Dev harness: run the SAM runner over one clip end to end.

Usage: python scripts/run_sam_dev.py <video> <clip_id> [keyframe_fps]

Development plumbing only: keyframes are sampled over the whole clip,
responses are cached under cache/ (gitignored), and the run record is
written to cache/runs/<clip_id>.json. Nothing this script prints is a
result; scored runs go through the frozen evaluation harness.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.frames import sample_frames              # noqa: E402
from jaga.sam_runner import SamRunner, helper_transport  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
TAG = "DEV ONLY — NOT A RESULT"


def main() -> None:
    video = Path(sys.argv[1])
    clip_id = sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    cache_root = ROOT / "cache"
    frames_dir = cache_root / "keyframes" / clip_id
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames = sample_frames(video, frames_dir, fps)
    runner = SamRunner(cache_root, helper_transport(HELPER),
                       fail_on_anomaly=False)
    run = runner.run_keyframes(clip_id, frames)
    out_dir = cache_root / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{clip_id}.json").write_text(
        json.dumps(run.to_dict(), indent=2))
    cost = ("unknown" if run.est_cost_usd is None
            else f"${run.est_cost_usd:.4f}")
    print(f"{TAG}: {clip_id}: {len(frames)} keyframes, "
          f"{run.api_calls} API calls, {run.cache_hits} cache hits, "
          f"est {cost}, {run.empty_keyframes} empty, "
          f"tracks {run.track_stats}, anomalies {run.anomalies}")


if __name__ == "__main__":
    main()
