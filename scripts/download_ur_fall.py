"""Download the UR Fall Detection Dataset from its official page.

Source: http://fenix.ur.edu.pl/~mkepski/ds/uf.html
License: CC BY-NC-SA 4.0, non-commercial academic use (see the source page).
Citation: Kwolek & Kepski, Comput Methods Programs Biomed 117(3), 2014.

What the page actually serves (verified 2026-10-27; the page's prose about
PNG-sequence zips is stale): one MP4 per sequence plus one accelerometer
CSV per sequence.
- falls: fall-01..30, video is camera 1 ONLY (the ceiling-mounted camera)
- adl:   adl-01..40, video is camera 0 ONLY (floor-parallel)
That asymmetry is a class-conditional camera confound. It is recorded in
the manifest and in SPEC.md, and UR Fall numbers are never pooled with
other datasets' views.

Design rules (SPEC.md, DECISIONS.md):
- Files land in data/ which is gitignored. Media never enters the repo.
- A receipt (results/ur_fall_download_receipt.json) records every source
  URL and the sha256 of every file. The manifest is built from it.
- Fails loudly if discovery finds an unexpected file inventory.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

INDEX = "http://fenix.ur.edu.pl/~mkepski/ds/uf.html"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "ur_fall"
RECEIPT = ROOT / "results" / "ur_fall_download_receipt.json"
UA = {"User-Agent": "Mozilla/5.0"}


def discover() -> list[str]:
    req = urllib.request.Request(INDEX, headers=UA)
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    hrefs = [h for h in re.findall(r'href="([^"]+)"', html)
             if h.startswith("./data/")]
    urls = [urllib.request.urljoin(INDEX, h) for h in hrefs]
    mp4 = [u for u in urls if u.endswith(".mp4")]
    csv = [u for u in urls if u.endswith(".csv")]
    print(f"index: {len(urls)} data files ({len(mp4)} mp4, {len(csv)} csv)")
    if len(mp4) != 70 or len(csv) != 70:
        raise SystemExit(
            f"ERROR: expected 70 mp4 + 70 csv, found {len(mp4)} + {len(csv)}; "
            "the source page changed — stop and re-verify by hand")
    return urls


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    urls = discover()
    DEST.mkdir(parents=True, exist_ok=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"source_index": INDEX, "files": []}
    if RECEIPT.exists():
        receipt = json.loads(RECEIPT.read_text())
    done = {a["filename"] for a in receipt["files"]}
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        path = DEST / name
        if name in done and path.exists():
            print(f"have {name}")
            continue
        print(f"downloading {name} ...", flush=True)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r, path.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        receipt["files"].append(
            {"filename": name, "url": url, "bytes": path.stat().st_size,
             "sha256": sha256(path)})
        RECEIPT.write_text(json.dumps(receipt, indent=2))
        print(f"  ok {path.stat().st_size} bytes")
    print(f"receipt: {len(receipt['files'])} files -> {RECEIPT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
