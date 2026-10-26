"""Dev measurement: run the motion gate over every UR Fall clip.

Usage: python scripts/gate_ur_fall_dev.py

The spec requires gate-only recall on dev falls to be ~100% before the
freeze: the gate may never silently cap end-to-end recall. This script
measures exactly that, per clip, and writes the per-clip gate record
next to the manifest. Output is a development measurement, labeled as
such; scored runs go through the frozen harness.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.config import config_hash            # noqa: E402
from jaga.frames import probe_duration         # noqa: E402
from jaga.motion_gate import gate_clip         # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TAG = "DEV ONLY — NOT A RESULT"


def main() -> None:
    manifest = list(csv.DictReader(
        (ROOT / "results" / "manifest_draft.csv").open()))
    out_path = ROOT / "results" / "gate_stats_ur_fall_dev.csv"
    falls_total = falls_flagged = 0
    adl_total = adl_flagged = 0
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clip_id", "label", "camera", "duration_s",
                    "n_segments", "flagged_s", "zero_candidate",
                    "config_hash"])
        for row in manifest:
            video = ROOT / "data" / "ur_fall" / row["source_file"]
            duration = probe_duration(video)
            segments, stats = gate_clip(video, duration)
            flagged = sum(s.end_s - s.start_s for s in segments)
            zero = len(segments) == 0
            w.writerow([row["clip_id"], row["label"], row["camera"],
                        f"{duration:.2f}", len(segments),
                        f"{flagged:.2f}", int(zero), config_hash()])
            if row["label"] == "fall":
                falls_total += 1
                falls_flagged += 0 if zero else 1
            else:
                adl_total += 1
                adl_flagged += 0 if zero else 1
    print(f"{TAG}: gate recall on UR Fall falls: "
          f"{falls_flagged}/{falls_total} clips with >= 1 candidate")
    print(f"{TAG}: ADL clips with >= 1 candidate: "
          f"{adl_flagged}/{adl_total} (gate is recall-tuned; candidates "
          "on ADL are expected and are the downstream stages' problem)")
    print(f"{TAG}: per-clip record written to {out_path.name}")


if __name__ == "__main__":
    main()
