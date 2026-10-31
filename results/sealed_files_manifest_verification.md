# Verification record — results/sealed_files_manifest.sha256

Date: 2026-11-01.

This record is the recomputation verification required by the
2026-11-01 amendment to the audit rule (see DECISIONS.md,
"Amendment to the secret-audit rule: hash manifests under
results/"). The amendment extends the audit's provenance treatment
to a hash manifest only when a verification of this kind is on
record for it.

## What was verified

`results/sealed_files_manifest.sha256` lists 144 SHA-256 checksums,
one per sealed UP-Fall archive (Subjects 3, 4, and 5; the
replication seal described in `results/replication_addendum.md`).

## Method

For each of the 144 entries, the SHA-256 of the corresponding local
dataset archive was recomputed and compared against the recorded
value (the `sha256sum -c` check over the manifest, run against the
archives held locally under `data/up_fall/` — dataset media is
gitignored and never committed). The archives are the ones listed,
with their download provenance, in
`results/up_fall_download_manifest.csv`. Total data hashed:
29,715,403,676 bytes.

The manifest's filename column was checked at the same time: every
entry is a bare dataset filename (for example,
`Subject3Activity1Trial1_Camera1.zip`). No entry is an absolute
path, and no entry contains a directory component.

## Result

- Entries checked: 144
- Matched exactly: 144
- Mismatched: 0
- Missing archives: 0

## Verifiers

Two independent recomputations on 2026-11-01, both with the result
above: the dress-rehearsal pass that committed the manifest, and
the audit-resolution pass that adopted the 2026-11-01 amendment.
