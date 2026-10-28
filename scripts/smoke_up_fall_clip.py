"""Smoke one assembled UP-Fall clip through the full pipeline.

Usage: python scripts/smoke_up_fall_clip.py <clip_mp4> <clip_id>

The clip row is built, not read from a manifest: this is a smoke
run, not a scored run, so it invents no split and no label beyond
the dataset's own activity label (UP-Fall activities 1-5 are falls).
Adjudication runs in the scored D3 form: traces only
(image_picker=None, evidence_form="none"), so no image data reaches
the adjudicator. Records land in cache/runs/up_fall_smoke.json.
Smoke evidence only; never presented as a frozen result.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.harness import run_clip  # noqa: E402
from jaga.sam_runner import SamRunner, helper_transport  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
ADJUDICATE_ON = frozenset({"fall_candidate", "uncertain"})
TAG = "SMOKE ONLY — NOT A RESULT"


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


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: smoke_up_fall_clip.py <clip_mp4> <clip_id>")
    video = Path(sys.argv[1])
    clip_id = sys.argv[2]
    # UP-Fall Camera1 of a fall activity is the side view under the
    # frozen SPEC (P3 side window); the label comes from the dataset
    # activity inventory, not from this script.
    row = {"clip_id": clip_id, "label": "fall", "camera": "camera1",
           "view": "side"}
    cache_root = ROOT / "cache"
    runner = SamRunner(cache_root, helper_transport(HELPER),
                       keep_rasters=False)
    rec = run_clip(video, row, runner, cache_root,
                   adjudicate_labels=ADJUDICATE_ON,
                   transport=vm_transport,
                   image_picker=None, evidence_form="none")
    out_dir = cache_root / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "up_fall_smoke.json").write_text(json.dumps(
        {"smoke": True, "evidence_form": "none", "record": rec},
        indent=2))
    print(f"{TAG}: {rec['clip_id']} ({rec['label']}) -> "
          f"{rec['outcome']} in {rec.get('wall_s')}s")
    print(f"{TAG}: gate: {rec.get('gate')}")
    print(f"{TAG}: timing_descent: {rec.get('timing_descent')}")
    for seg in rec.get("segments", []):
        print(f"{TAG}: segment {seg.get('start_s')}-{seg.get('end_s')}s "
              f"keyframes={seg.get('keyframes')} "
              f"rules={seg.get('rules_label')} "
              f"adj={seg.get('adjudication')}")


if __name__ == "__main__":
    main()
