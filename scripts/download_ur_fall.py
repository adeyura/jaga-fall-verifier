"""Download the UR Fall Detection Dataset (RGB, camera 0) from its official page.

Source: http://fenix.ur.edu.pl/~mkepski/ds/uf.html
License: CC BY-NC-SA 4.0, non-commercial academic use (see the source page).
Citation: Kwolek & Kepski, Comput Methods Programs Biomed 117(3), 2014.

Design rules (SPEC.md, DECISIONS.md):
- Archives land in data/ which is gitignored. Media never enters the repo.
- This script writes a receipt (results/ur_fall_download_receipt.json) with
  every source URL and the sha256 of every archive downloaded. That receipt
  is the provenance record; the manifest is built from it.
- Fails loudly if the index page yields no matching archives.

Scope choice, stated openly: RGB camera 0 only (the floor-parallel view).
SAM 3.1 works on RGB; depth streams and the ceiling camera are skipped to
keep the gate evaluation inside the API budget. Revisit only by decision.
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
DEST = ROOT / "data" / "ur_fall" / "archives"
RECEIPT = ROOT / "results" / "ur_fall_download_receipt.json"


def discover() -> list[str]:
    html = urllib.request.urlopen(INDEX, timeout=60).read().decode("utf-8", "replace")
    hrefs = re.findall(r'href="([^"]+)"', html)
    zips = [h for h in hrefs if h.lower().endswith(".zip")]
    keep = [h for h in zips if "rgb" in h.lower() and "cam0" in h.lower()]
    others = [h for h in zips if h not in keep]
    print(f"index: {len(zips)} zip links, {len(keep)} match rgb+cam0")
    for h in others[:5]:
        print(f"  skipped (not rgb/cam0): {h}")
    return [urllib.request.urljoin(INDEX, h) for h in keep]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    urls = discover()
    if not urls:
        print("ERROR: no rgb/cam0 archives found on the index page", file=sys.stderr)
        return 1
    DEST.mkdir(parents=True, exist_ok=True)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"source_index": INDEX, "archives": []}
    if RECEIPT.exists():
        receipt = json.loads(RECEIPT.read_text())
    done = {a["filename"] for a in receipt["archives"]}
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        path = DEST / name
        if name in done and path.exists():
            print(f"have {name}")
            continue
        print(f"downloading {name} ...", flush=True)
        urllib.request.urlretrieve(url, path)
        receipt["archives"].append(
            {"filename": name, "url": url, "bytes": path.stat().st_size,
             "sha256": sha256(path)})
        RECEIPT.write_text(json.dumps(receipt, indent=2))
        print(f"  ok {path.stat().st_size} bytes")
    print(f"receipt: {len(receipt['archives'])} archives -> {RECEIPT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
