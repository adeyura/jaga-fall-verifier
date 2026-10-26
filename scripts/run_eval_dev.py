"""Dev harness driver: run manifest clips through the full pipeline.

Usage: python scripts/run_eval_dev.py [n_falls] [n_adl]

Runs the first N fall and M ADL rows of the UR Fall manifest through
gate, timing, SAM, rules, and (for fall_candidate and uncertain rules
outcomes) one Spark adjudication each. Records land in
cache/runs/dev_eval.json with the cascade summary printed here.
Development evidence only; the frozen run writes the single results
file under results/ and happens once, after the spec freezes.
"""
import base64
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.harness import cascade, run_clip          # noqa: E402
from jaga.sam_runner import SamRunner, helper_transport  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
TAG = "DEV ONLY — NOT A RESULT"
ADJUDICATE_ON = frozenset({"fall_candidate", "uncertain"})


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


def pick_images(window):
    chosen = [window[0], window[len(window) // 2], window[-1]]
    urls = ["data:image/png;base64,"
            + base64.b64encode(p.read_bytes()).decode()
            for _, p in chosen]
    labels = [f"Keyframe at {t:.1f} s:" for t, _ in chosen]
    return urls, labels


def main() -> None:
    n_falls = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_adl = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    rows = list(csv.DictReader((ROOT / "results" / "manifest_draft.csv").open()))
    selected = ([r for r in rows if r["label"] == "fall"][:n_falls]
                + [r for r in rows if r["label"] != "fall"][:n_adl])
    cache_root = ROOT / "cache"
    runner = SamRunner(cache_root, helper_transport(HELPER))
    records = []
    for row in selected:
        video = (ROOT / row["video_path"] if row.get("video_path")
                 else ROOT / "data" / "ur_fall" / row["source_file"])
        rec = run_clip(video, row, runner, cache_root,
                       adjudicate_labels=ADJUDICATE_ON,
                       transport=vm_transport, image_picker=pick_images)
        records.append(rec)
        print(f"{TAG}: {rec['clip_id']} ({rec['label']}) -> "
              f"{rec['outcome']} in {rec['wall_s']}s")
    out_dir = cache_root / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dev_eval.json").write_text(json.dumps(
        {"dev": True, "records": records, "cascade": cascade(records)},
        indent=2))
    print(f"{TAG}: cascade: {json.dumps(cascade(records), indent=2)}")


if __name__ == "__main__":
    main()
