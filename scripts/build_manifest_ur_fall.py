"""Build the draft clip manifest from downloaded UR Fall archives.

A manifest row is a commitment: once SPEC.md freezes, this file (completed
for all gate datasets) becomes the frozen manifest, and the eval harness
reads only what it lists. Rows carry the source archive's sha256 from the
download receipt so every clip traces to a verified artifact.

Nothing here invents labels: UR Fall sequence names carry fall-/adl-
prefixes; finer hard-negative categories are a separate curation step and
are left blank rather than guessed.
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
    rows = []
    for a in receipt["archives"]:
        name = a["filename"]
        seq = name.replace("-cam0-rgb.zip", "").replace(".zip", "")
        label = "fall" if seq.startswith("fall-") else "adl"
        rows.append({
            "clip_id": f"urfall_{seq}_cam0",
            "dataset": "ur_fall",
            "sequence": seq,
            "camera": "cam0",
            "label": label,
            "negative_category": "",
            "split": "",
            "source_archive": name,
            "archive_sha256": a["sha256"],
        })
    rows.sort(key=lambda r: r["clip_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    falls = sum(1 for r in rows if r["label"] == "fall")
    print(f"manifest draft: {len(rows)} clips ({falls} fall, "
          f"{len(rows) - falls} adl) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
