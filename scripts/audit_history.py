"""Audit the full git history for anything credential-shaped.

Run before the first GitHub push and again before submission (DECISIONS.md,
2026-10-27: credentials never enter this repo). Scans every commit's diff
plus the tracked file list. Exits nonzero on any real hit so it can gate
a push.

This repo legitimately contains sha256 checksums (dataset provenance in
results/). Hex/base64 blobs in checksum contexts are counted and reported
as expected content, not failures; the same shapes anywhere else fail.
"""
from __future__ import annotations

import re
import subprocess
import sys

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
    checksum_context = 0
    names = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    for n in names:
        if BAD_NAMES.search(n) and not n.endswith(".example"):
            print(f"  BAD FILENAME tracked: {n}")
            hits += 1
    path = ""
    for line in git("log", "-p", "--all", "--no-color").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
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
                if is_checksum_context(path, body):
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
    print("AUDIT CLEAN: no credential-shaped content in history or filenames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
