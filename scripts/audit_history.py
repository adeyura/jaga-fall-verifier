"""Audit the full git history for anything credential-shaped.

Run before the first GitHub push and again before submission (DECISIONS.md,
2026-10-27: credentials never enter this repo). Scans every commit's diff
plus the tracked file list. Exits nonzero on any real hit so it can gate
a push.

This repo legitimately contains sha256 checksums (dataset provenance in
results/). Hex/base64 blobs in checksum contexts are counted and reported
as expected content, not failures; the same shapes anywhere else fail.

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


def is_verified_checksum(value: str, context: str) -> bool:
    """The amendment test for one 64-hex value, as a conjunction:
    (i) the context explicitly labels it "SHA-256"; AND (ii)+(iii) the
    value is tied to a named project file whose recomputed SHA-256
    matches exactly — either via the amendment's verified allowlist or
    via a live recomputation for a file reference that resolves."""
    if not SHA256_LABEL.search(context):
        return False
    if value in VERIFIED_PROVENANCE_HASHES:
        return True
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
    if "sha256" in line:
        return True
    return path.startswith("results/") and path.endswith((".json", ".csv"))


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
    path = ""
    recent: list[str] = []  # surrounding prose for the amendment test
    for line in git("log", "-p", "--all", "--no-color").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            recent = []
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        context = "\n".join([*recent[-2:], body])
        recent.append(body)
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
