"""Build the draft clip manifest from downloaded UR Fall files.

A manifest row is a commitment: once SPEC.md freezes, this file (completed
for all gate datasets) becomes the frozen manifest, and the eval harness
reads only what it lists. Rows carry the source file's sha256 from the
download receipt so every clip traces to a verified artifact.

Nothing here invents labels: UR Fall sequence names carry fall-/adl-
prefixes; finer hard-negative categories are a separate curation step and
are left blank rather than guessed. The camera column records the UR Fall
distribution asymmetry (falls = ceiling cam1, adl = floor cam0) so the
confound travels with the data.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "results" / "ur_fall_download_receipt.json"
OUT = ROOT / "results" / "manifest_draft.csv"


def main() -> int:
    if not RECEIPT.exists():
        print(f"ERROR: {RECEIPT} missing; run download_ur_fall.py first",
              file=sys.stderr)
        return 1
    receipt = json.loads(RECEIPT.read_text())
    by_name = {f["filename"]: f for f in receipt["files"]}
    rows = []
    for name, f in sorted(by_name.items()):
        if not name.endswith(".mp4"):
            continue
        stem = name[:-4]                       # fall-01-cam1 / adl-01-cam0
        seq, cam = stem.rsplit("-", 1)
        label = "fall" if seq.startswith("fall-") else "adl"
        acc = by_name.get(f"{seq}-acc.csv", {})
        rows.append({
            "clip_id": f"urfall_{seq}_{cam}",
            "dataset": "ur_fall",
            "sequence": seq,
            "camera": cam,
            "label": label,
            "negative_category": "",
            "split": "",
            "source_file": name,
            "file_sha256": f["sha256"],
            "accel_file": acc.get("filename", ""),
            "notes": ("ceiling view; class-conditional camera confound "
                      "vs adl cam0") if label == "fall" else "floor-parallel view",
        })
    rows.sort(key=lambda r: r["clip_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    falls = sum(1 for r in rows if r["label"] == "fall")
    print(f"manifest draft: {len(rows)} clips ({falls} fall, "
          f"{len(rows) - falls} adl) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
