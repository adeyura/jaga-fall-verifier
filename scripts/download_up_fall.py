"""Download the UP-Fall Detection Dataset from its official page.

Source: https://sites.google.com/up.edu.mx/har-up/
License: no license form on the site; citation required.
Citation: Martinez-Villaseñor et al., Sensors 19(9), 1988 (2019).
Data: per-trial image-sequence zips (18 Hz, 640x480) hosted on Google
Drive, linked from the source page. The full raw set is ~812 GB across
modalities, so downloads are selective by subject/activity (below).

Verified 2026-10-27 by parsing the live page (this script's step 1):
- The page groups Drive links in divs id="Subject{S}Activity{A}Trial{T}"
  (17 subjects x 11 activities x 3 trials = 561 groups), each holding
  labeled links: DataSet, Features* (3), Camera1, Camera2, the two
  optical-flow variants, and resized-OF feature files.
- 559 groups carry Camera1 + Camera2 links (1118 camera files). Exactly
  two groups carry only a DataSet link and no camera or feature files:
  Subject 8, Activity 11, Trials 2 and 3. That is the dataset's known
  missing data, checked below as a hard inventory, not assumed away.
- Page URLs use the domain-scoped form
  drive.google.com/a/up.edu.mx/uc?id=...&export=download; they are
  recorded verbatim in the file map.

Assumed, and exercised by the first live run:
- A plain GET on a page URL returns the zip bytes when Drive allows it,
  or an HTML page when it does not. Verified live 2026-10-27, all on
  subject 1 files: Drive answers either the quota page directly, or
  the virus-scan warning page (a form pointing at
  drive.usercontent.google.com) with the quota page behind the confirm
  hop. Both shapes are classified as quota failures; an HTML response
  to a .zip request is never treated as data. Drive quotas are
  per-file and reset over time. What remains unverified until a quota
  reset: a successful end-to-end zip download through the confirm hop.

Jaga selection (SPEC.md): falls are activities 1-5; hard negatives are
8 (picking up an object), 9 (sitting down), 11 (laying down). Two
camera views of one event count as ONE sample; both are downloaded.

Design rules (SPEC.md, DECISIONS.md), mirroring download_ur_fall.py:
- Files land in data/ which is gitignored. Media never enters the repo.
- The file map (results/up_fall_file_map.json) is the discovery record;
  the manifest (results/up_fall_download_manifest.csv) records the
  sha256 and byte count of every verified file.
- Resumable at the file level: a re-run skips files whose manifest row
  says ok and whose on-disk file still matches (size + readable zip
  central directory) and retries everything else.
- Fails loudly if the page inventory differs from the verified counts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

INDEX = "https://sites.google.com/up.edu.mx/har-up/"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "up_fall"
FILE_MAP = ROOT / "results" / "up_fall_file_map.json"
MANIFEST = ROOT / "results" / "up_fall_download_manifest.csv"
UA = {"User-Agent": "Mozilla/5.0"}

# Verified against the live page on 2026-10-27 (see docstring).
EXPECTED_GROUPS = 561
EXPECTED_CAMERA_EACH = 559
EXPECTED_CAMERALESS_GROUPS = {(8, 11, 2), (8, 11, 3)}

FALL_ACTIVITIES = {1, 2, 3, 4, 5}
NEGATIVE_ACTIVITIES = {8, 9, 11}

QUOTA_MARKERS = (
    "too many users have viewed or downloaded",
    "quota exceeded",
    "view or download this file at this time",
)
GROUP_RE = re.compile(r'<div id="Subject(\d+)Activity(\d+)Trial(\d+)"')
LINK_RE = re.compile(
    r'<a href="(https://drive\.google\.com/[^"]*uc\?id=([A-Za-z0-9_-]+)[^"]*)"'
    r"[^>]*>([^<]*)</a>")
USERCONTENT_RE = re.compile(
    r"https://drive\.usercontent\.google\.com/download\?[^\"'\s<]+")

MANIFEST_FIELDS = ["filename", "drive_id", "subject", "activity", "trial",
                   "kind", "label", "url", "bytes", "sha256", "status",
                   "attempts", "error", "updated_utc"]


class QuotaExceeded(Exception):
    """Drive refused the file: per-file quota, resets over time."""


class Interstitial(Exception):
    """Drive answered HTML that is neither data nor a known quota page."""


def kind_of(label: str) -> str:
    if label == "DataSet":
        return "dataset"
    if label == "Camera1":
        return "camera1"
    if label == "Camera2":
        return "camera2"
    if label in ("Camera1_OF", "Camera2_OF"):
        return "camera_of"
    if label.startswith("Camera OF Features"):
        return "of_features"
    if label == "Camera Resized OF":
        return "of_resized"
    if label.startswith("Features"):
        return "features"
    return "other"


def fetch_file_map() -> list[dict]:
    req = urllib.request.Request(INDEX, headers=UA)
    raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    doc = html_mod.unescape(raw)
    opens = [(m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3)))
             for m in GROUP_RE.finditer(doc)]
    entries: list[dict] = []
    cameraless: set[tuple[int, int, int]] = set()
    for pos, s, a, t in opens:
        end = doc.find("</div>", pos)
        if end == -1:
            raise SystemExit(f"ERROR: unclosed group div at Subject{s} "
                             f"Activity{a} Trial{t}; page structure changed")
        links = [(m.group(3).strip(), m.group(2), m.group(1))
                 for m in LINK_RE.finditer(doc[pos:end])]
        group_kinds = {kind_of(label) for label, _, _ in links}
        if not group_kinds & {"camera1", "camera2"}:
            cameraless.add((s, a, t))
        for label, fid, url in links:
            entries.append({"id": fid, "subject": s, "activity": a,
                            "trial": t, "kind": kind_of(label),
                            "label": label, "url": url})
    cam1 = sum(1 for e in entries if e["kind"] == "camera1")
    cam2 = sum(1 for e in entries if e["kind"] == "camera2")
    print(f"index: {len(opens)} trial groups, {len(entries)} file links "
          f"({cam1} Camera1, {cam2} Camera2), {len(cameraless)} "
          "camera-less groups")
    if (len(opens) != EXPECTED_GROUPS or cam1 != EXPECTED_CAMERA_EACH
            or cam2 != EXPECTED_CAMERA_EACH
            or cameraless != EXPECTED_CAMERALESS_GROUPS):
        raise SystemExit(
            f"ERROR: expected {EXPECTED_GROUPS} groups, "
            f"{EXPECTED_CAMERA_EACH} Camera1 + {EXPECTED_CAMERA_EACH} Camera2, "
            f"camera-less groups {sorted(EXPECTED_CAMERALESS_GROUPS)}; found "
            f"{len(opens)} groups, {cam1} + {cam2}, camera-less "
            f"{sorted(cameraless)} — the source page changed; stop and "
            "re-verify by hand")
    return entries


def load_or_fetch_map(refresh: bool) -> list[dict]:
    if FILE_MAP.exists() and not refresh:
        entries = json.loads(FILE_MAP.read_text())
        print(f"file map: loaded {len(entries)} entries from {FILE_MAP} "
              "(--refresh-map to refetch)")
        return entries
    entries = fetch_file_map()
    FILE_MAP.parent.mkdir(parents=True, exist_ok=True)
    FILE_MAP.write_text(json.dumps(entries, indent=2))
    print(f"file map: {len(entries)} entries -> {FILE_MAP}")
    return entries


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def filename_for(e: dict) -> str:
    return (f"Subject{e['subject']}Activity{e['activity']}Trial{e['trial']}"
            f"_{e['label']}.zip")


def _looks_html(head: bytes) -> bool:
    text = head.lstrip().lower()
    return text.startswith(b"<!doctype") or text.startswith(b"<html")


def _stream(url: str, dest: Path) -> bytes:
    """GET url into dest; return the first bytes seen (for sniffing)."""
    req = urllib.request.Request(url, headers=UA)
    head = b""
    with urllib.request.urlopen(req, timeout=600) as r, dest.open("wb") as f:
        while chunk := r.read(1 << 20):
            if len(head) < 512:
                head += chunk[: 512 - len(head)]
            f.write(chunk)
    return head


def _confirm_url(page: bytes, base_url: str) -> str | None:
    text = html_mod.unescape(page.decode("utf-8", "replace"))
    m = USERCONTENT_RE.search(text)
    if m:
        return m.group(0)
    form = re.search(r'<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>',
                     text, re.S)
    if form and "usercontent" in form.group(1):
        fields = dict(re.findall(
            r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', form.group(2)))
        if "id" in fields:
            q = "&".join(f"{k}={fields[k]}" for k in
                         ("id", "export", "confirm", "uuid") if k in fields)
            return f"{form.group(1)}?{q}"
    return None


def _is_quota_page(page: bytes) -> bool:
    lowered = page.decode("utf-8", "replace").lower().replace("\u2019", "'")
    return any(marker in lowered for marker in QUOTA_MARKERS)


def download_once(url: str, partial: Path) -> None:
    """One attempt. Raises QuotaExceeded / Interstitial / OSError family."""
    head = _stream(url, partial)
    if not _looks_html(head):
        return
    page = partial.read_bytes()[: 1 << 18]
    if _is_quota_page(page):
        raise QuotaExceeded("Drive quota page returned")
    confirm = _confirm_url(page, url)
    if confirm is None:
        snippet = re.sub(r"\s+", " ",
                         page.decode("utf-8", "replace"))[:160]
        raise Interstitial(f"unrecognized HTML response: {snippet}")
    head = _stream(confirm, partial)
    if _looks_html(head):
        # Verified live 2026-10-27: for quota-blocked files Drive serves
        # the virus-scan warning first, and the quota page only appears
        # behind the confirm hop. Classify by the second page too.
        if _is_quota_page(partial.read_bytes()[: 1 << 18]):
            raise QuotaExceeded("Drive quota page behind confirm hop")
        raise Interstitial("confirm hop still returned HTML")
    if not (partial.stat().st_size > 0 and head[:2] == b"PK"):
        raise Interstitial("confirm hop returned a non-zip payload")


def load_manifest() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if MANIFEST.exists():
        with MANIFEST.open(newline="") as f:
            for row in csv.DictReader(f):
                rows[row["filename"]] = row
    return rows


def write_manifest(rows: dict[str, dict]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for name in sorted(rows):
            w.writerow({k: rows[name].get(k, "") for k in MANIFEST_FIELDS})


def verified_on_disk(row: dict, path: Path) -> bool:
    return (row.get("status") == "ok" and path.exists()
            and str(path.stat().st_size) == row.get("bytes", "")
            and zipfile.is_zipfile(path))


def parse_range(text: str) -> set[int]:
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subjects", default="1-5",
                    help="subjects to download, e.g. '1-5' or '1,3' "
                         "(default 1-5)")
    ap.add_argument("--activities", default="1-5,8,9,11",
                    help="activities to download (default falls 1-5 plus "
                         "hard negatives 8, 9, 11)")
    ap.add_argument("--kinds", default="camera1,camera2",
                    help="file kinds to download (default camera1,camera2)")
    ap.add_argument("--attempts", type=int, default=4,
                    help="per-file attempts before recording a failure")
    ap.add_argument("--backoff", type=float, default=30.0,
                    help="base backoff seconds, doubled per attempt")
    ap.add_argument("--map-only", action="store_true",
                    help="build the file map and stop")
    ap.add_argument("--refresh-map", action="store_true",
                    help="refetch the source page even if a map exists")
    args = ap.parse_args()

    entries = load_or_fetch_map(args.refresh_map)
    if args.map_only:
        return 0

    subjects = parse_range(args.subjects)
    activities = parse_range(args.activities)
    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    selected = [e for e in entries if e["subject"] in subjects
                and e["activity"] in activities and e["kind"] in kinds]
    print(f"selected: {len(selected)} files for subjects "
          f"{sorted(subjects)}, activities {sorted(activities)}, "
          f"kinds {sorted(kinds)}")

    DEST.mkdir(parents=True, exist_ok=True)
    rows = load_manifest()
    ok = skipped = failed = 0
    failed_names: list[str] = []
    for e in selected:
        name = filename_for(e)
        path = DEST / name
        row = rows.get(name, {})
        if verified_on_disk(row, path):
            print(f"have {name}")
            skipped += 1
            continue
        row = {"filename": name, "drive_id": e["id"],
               "subject": e["subject"], "activity": e["activity"],
               "trial": e["trial"], "kind": e["kind"], "label": e["label"],
               "url": e["url"], "bytes": "", "sha256": "",
               "status": "failed", "attempts": 0, "error": ""}
        partial = path.with_suffix(".partial")
        error: Exception | None = None
        for attempt in range(1, args.attempts + 1):
            row["attempts"] = attempt
            try:
                print(f"downloading {name} (attempt {attempt}) ...",
                      flush=True)
                download_once(e["url"], partial)
                if not zipfile.is_zipfile(partial):
                    raise Interstitial("downloaded payload is not a zip")
                partial.replace(path)
                row.update(bytes=str(path.stat().st_size),
                           sha256=sha256(path), status="ok", error="")
                error = None
                break
            except Exception as exc:  # noqa: BLE001 - recorded, then retried
                error = exc
                if partial.exists():
                    partial.unlink()
                if attempt < args.attempts:
                    wait = args.backoff * (2 ** (attempt - 1))
                    print(f"  {type(exc).__name__}: {exc}; "
                          f"retrying in {wait:.0f}s")
                    time.sleep(wait)
        row["updated_utc"] = datetime.now(timezone.utc).isoformat()
        if error is None:
            ok += 1
            print(f"  ok {row['bytes']} bytes")
        else:
            failed += 1
            failed_names.append(name)
            row["error"] = f"{type(error).__name__}: {error}"
            print(f"  FAILED {name}: {row['error']}")
        rows[name] = row
        write_manifest(rows)
    total_bytes = sum(int(r["bytes"]) for r in rows.values()
                      if r.get("status") == "ok" and r.get("bytes"))
    print(f"done: {ok} downloaded, {skipped} already verified, "
          f"{failed} failed; manifest holds {total_bytes} verified bytes "
          f"-> {MANIFEST}")
    if failed_names:
        print("failed files: " + ", ".join(failed_names))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
