"""Audit the full git history for anything credential-shaped.

Run before the first GitHub push and again before submission (DECISIONS.md,
2026-10-27: credentials never enter this repo). Scans every commit's diff
plus the tracked file list. Exits nonzero on any real hit so it can gate
a push.

This repo legitimately contains sha256 checksums (dataset provenance).
Hex/base64-shaped values inside the machine-generated provenance tables
under results/ (*.csv / *.json: download manifests, split files, run
receipts) are counted and reported as expected provenance data, not
failures. That treatment is scoped to those tables only (see
is_checksum_context): of their 547 shape-matching lines, basename
recomputation resolves only 80 — the rest are clip-level hashes whose
named archive is a room zip, receipt rows naming no file on the
value's line, and hashes of derived files — so a strict per-line
recomputation rule is not viable there. It is not a prose exemption:
anywhere else, the same shapes fail unless the amendment test below
suppresses them. Credential patterns are checked first, on every line,
in every file, tables included, and can never be exempted.

Amendment (DECISIONS.md, 2026-10-30): a 64-hex value in prose is
suppressed only when ALL THREE hold — it is explicitly labelled
"SHA-256" in its context, the surrounding prose names the project file
it hashes, and recomputation from that file matches exactly (the
verified allowlist below, or a live recomputation for file references
that resolve). Suppressed values are printed, with a count, and a pass
is reported as "PASS under the 2026-10-30 amendment", never as a pass
of the original unamended rule. Credential patterns are checked first
and can never be exempted.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

FAIL_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9_\.\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|access[_-]?token|password)"
               r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
]
SHAPE_PATTERNS = [
    re.compile(r"[0-9a-f]{40,}"),               # long hex
    re.compile(r"[A-Za-z0-9+/]{48,}={0,2}"),     # long base64
]
BAD_NAMES = re.compile(r"(?i)(^|/)(\.env|.*\.pem|.*\.key|id_rsa|credentials)")

# --- 2026-10-30 amendment (DECISIONS.md): verified provenance checksums.
# Each value below was recomputed from the project file it hashes and
# matched exactly; locations and method are recorded in the amendment.
AMENDMENT_ID = "2026-10-30"
VERIFIED_PROVENANCE_HASHES = {
    # SHA-256 of results/split_dev.csv; cited in
    # results/split_freeze_2026-10-29.md (labelled "SHA-256", bullet
    # naming results/split_dev.csv directly above).
    "f968ee85b519ecc69d9506b55f4ad65902d49c49052e1d80b1b906b666607895":
        "results/split_dev.csv",
    # SHA-256 of results/split_test.csv; cited in
    # results/split_freeze_2026-10-29.md (same labelling pattern).
    "6006c2fa9d4e3aaae03d5d4c80bf3b3dc67385582bab8a62fa22846851d0ac03":
        "results/split_test.csv",
    # SHA-256 of Subject1Activity1Trial1_Camera1.zip (local dataset
    # media, data/up_fall/, never committed); its verification is recorded as
    # "zip sha256 verified against results/up_fall_download_manifest.csv".
    "963af49e519884f69b7e607069d27bc9afea3f3a9b496ffaf4cca7431bb1cc1d":
        "data/up_fall/Subject1Activity1Trial1_Camera1.zip",
}
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
SHA256_LABEL = re.compile(r"sha[-\s]?256", re.IGNORECASE)
FILE_TOKEN = re.compile(r"[A-Za-z0-9_./\-]+\.[A-Za-z0-9]{1,8}")


def credential_hit(body: str) -> bool:
    """Credential patterns: checked before everything, never exempted."""
    return any(p.search(body) for p in FAIL_PATTERNS)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _context_names_file(context: str, mapped: str) -> bool:
    """True when the surrounding prose names the project file `mapped`:
    by its repo path, by its file name, or by its stem (citing files
    may name the UP-Fall zip by its clip name,
    Subject1Activity1Trial1_Camera1, without the .zip extension). The
    stem must stand as its own token,
    not glued to other file-name characters."""
    if mapped in context or Path(mapped).name in context:
        return True
    stem = Path(mapped).stem
    return bool(re.search(
        r"(?<![A-Za-z0-9_\-])" + re.escape(stem) + r"(?![A-Za-z0-9_\-])",
        context))


def is_verified_checksum(value: str, context: str) -> bool:
    """The amendment test for one 64-hex value, as a conjunction:
    (i) the context explicitly labels it "SHA-256"; AND (ii)+(iii) the
    value is tied to a named project file whose recomputed SHA-256
    matches exactly — either via the amendment's verified allowlist or
    via a live recomputation for a file reference that resolves."""
    if not SHA256_LABEL.search(context):
        return False
    if value in VERIFIED_PROVENANCE_HASHES:
        # Conjunct (ii): the prose must name the file this value is
        # verified against (the allowlist mapping), not just any file,
        # and not no file. (2026-10-30, defect D2: the
        # mapping was previously never read, so a bare label sufficed.)
        return _context_names_file(
            context, VERIFIED_PROVENANCE_HASHES[value])
    for token in FILE_TOKEN.findall(context):
        candidate = Path(token.strip("`\"'(),:;"))
        if candidate.is_file() and _sha256_of_file(candidate) == value:
            return True
    return False


def amendment_suppresses(body: str, context: str) -> bool:
    """True only when every 64-hex value on the line passes the
    amendment test. `context` is the line plus its surrounding prose
    (the label and the file naming may sit on an adjacent line)."""
    values = HEX64.findall(body)
    return bool(values) and all(
        is_verified_checksum(v, context) for v in values)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True,
                          text=True).stdout


def is_checksum_context(path: str, line: str) -> bool:
    """Checksum-context treatment, scoped to the machine-generated
    provenance tables under results/ (*.csv / *.json) ONLY. A prose
    line earns no exemption from its content — not even from carrying
    the substring "sha256": that branch let a labelled, non-matching
    hash in prose pass, contradicting the 2026-10-30 amendment
    (defect D1). Prose is governed solely by
    amendment_suppresses(). The `line` argument is kept for signature
    compatibility and is deliberately unused."""
    return path.startswith("results/") and path.endswith((".json", ".csv"))


def _surrounding(records: list[tuple[str, str]], i: int,
                 reach: int = 6) -> list[str]:
    """The prose surrounding records[i]: up to `reach` added lines on
    either side within the same file, stopping at a blank line. The
    amendment test reads this context because the prose naming a
    checksum's file may sit before OR after the value (DECISIONS.md
    lists each checksum first and names its file in the lines that
    follow)."""
    path = records[i][0]
    lo = i
    while lo > 0 and i - lo < reach:
        p, b = records[lo - 1]
        if p != path or not b.strip():
            break
        lo -= 1
    hi = i
    while hi < len(records) - 1 and hi - i < reach:
        p, b = records[hi + 1]
        if p != path or not b.strip():
            break
        hi += 1
    return [b for _, b in records[lo:hi + 1]]


def main() -> int:
    commits = git("rev-list", "--all").split()
    print(f"auditing {len(commits)} commits")
    hits = 0
    suppressed = 0
    checksum_context = 0
    names = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    for n in names:
        if BAD_NAMES.search(n) and not n.endswith(".example"):
            print(f"  BAD FILENAME tracked: {n}")
            hits += 1
    # Collect every added line first: classification needs the
    # surrounding prose (see _surrounding), which may follow the line.
    records: list[tuple[str, str]] = []
    path = ""
    for line in git("log", "-p", "--all", "--no-color").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        records.append((path, line[1:]))
    for i, (path, body) in enumerate(records):
        context = "\n".join(_surrounding(records, i))
        # Credential patterns first, on every line, in every file —
        # including results/ tables and base64-shaped lines. A hit here
        # can never be reclassified as checksum context or suppressed.
        failed = False
        for p in FAIL_PATTERNS:
            if p.search(body):
                print(f"  HIT [{p.pattern[:40]}...] in {path}: {body[:100]}")
                hits += 1
                failed = True
                break
        if failed:
            continue
        for p in SHAPE_PATTERNS:
            if p.search(body):
                if amendment_suppresses(body, context):
                    print(f"  SUPPRESSED under {AMENDMENT_ID} amendment "
                          f"in {path}: {body[:100]}")
                    suppressed += 1
                elif is_checksum_context(path, body):
                    checksum_context += 1
                else:
                    print(f"  SHAPE HIT [{p.pattern[:30]}...] in {path}: "
                          f"{body[:100]}")
                    hits += 1
                break
    print(f"checksum-context blobs (expected provenance data): {checksum_context}")
    if hits:
        print(f"AUDIT FAILED: {hits} hit(s). Do not push. Inspect each one.")
        return 1
    print(f"AUDIT PASS under the {AMENDMENT_ID} amendment "
          f"({suppressed} suppressed, 0 unsuppressed hits): "
          f"no credential-shaped content in history or filenames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
