# Replication addendum: pre-registration

Status: pre-registration, prepared 2026-10-31, committed before the hackathon submission and before any replication run. Sealed-file manifest: `results/sealed_files_manifest.sha256` (SHA-256 hashes for all 144 files of UP-Fall Subjects 3, 4, and 5).

Written and hash-committed into this repository before the hackathon submission, and before any replication run. This text is not edited after the run; results are appended below it, dated.

## What is sealed

UP-Fall Subjects 3, 4, and 5 are in neither the dev split nor the frozen test split (see `results/split_freeze_2026-10-29.md`). The files on disk have been integrity-checked only: byte sizes and SHA-256 hashes verified against the download manifest. No Subject 3, 4, or 5 clip has been assembled, viewed, or run through any pipeline stage.

Download state at the time of writing: all three subjects are complete, 48 of 48 files each (144 files in total), each file's SHA-256 verified against the download manifest; the full UP-Fall archive stands at 240 of 240 files verified, as of 2026-10-31. Completing a download was acquisition, not inspection, and did not break the seal.

## The run, fixed in advance

Configuration: the shipped rules-primary pipeline, config hash `6d7c03257b12ab00`, unmodified. No tuning of any kind before, during, or after the run. A defect found in the pipeline is handled through the dated-amendment process in `DECISIONS.md`, in the open.

Inclusion rule: any subject at 48/48 by the run date; every subject run is reported in full, per subject, never pooled with the frozen test, and never pooled into a single headline. All three subjects meet the rule: each is complete at 48/48.

## Reporting template (per subject)

Events; falls confirmed, escalated, cleared, and gate-missed; not-missed recall (confirmed or escalated) with a Wilson interval; everyday-activity events with false alarms, escalations, and clears; precision with a Wilson interval; false alarms per hour of event footage, labeled event-stream-relative; SAM keyframes processed and API spend.

## What the seal is, and is not

This seal is a commitment device: a public, timestamped statement of what will be run and how it will be reported, committed before the run. It is not externally verifiable proof that no file was opened; the files sit on the author's machine. Its force is that any deviation would have to be hidden against a public record.

Re-running the frozen test split to confirm that the pinned pipeline reproduces the published outputs is permitted at any time: that is re-execution for a reproducibility audit. Computing a new number from the frozen test, or tuning against it, is banned: that is re-measurement.

## Publication

The run happens after the hackathon's live final on Nov 9, when judging is complete. The results are published here, in full, regardless of outcome, including a null or unfavorable one, as a post-event addendum to the submission.
