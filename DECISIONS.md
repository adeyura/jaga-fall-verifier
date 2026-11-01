# Decisions (published technical record)

This file is the published technical decision record for Jaga, prepared
for publication on 2026-11-01. It is a selected record, not a
complete one. It carries the decisions that affect
how the system and its evaluation should be interpreted: the protocol
adoption, the dated amendments, the gate outcome and the pivot, and
the evidentiary status of each later analysis.
Each entry states the decision and the reasoning and evidence it
rests on.

Amendment process: the evaluation protocol (SPEC.md) and this record
change only through dated amendment entries. Frozen run records under
results/ are never edited after the run they describe.

## 2026-10-27: Evaluation protocol adopted and frozen (SPEC D1-D5, P1-P3)

The evaluation protocol in SPEC.md was adopted and frozen before any
scored run. Its load-bearing elements: a pre-registered gate (D1) for
the Muse Spark adjudicator, which had to show zero additional missed
falls against the rules-only arm, at least 40% relative and at least
3 absolute fewer hard-negative false alarms, and at least 95% usable
verdicts, or be removed; a tiered alert ladder (D2); an adjudicator
evidence form to be settled by comparison before the gate (D3);
descent timing measured locally from the motion signal (D4); and a
split discipline (D5) with a development split for tuning and a
frozen test split reserved for one confirmation run, with Wilson
intervals on every proportion. Every scored run stamps the
configuration hash of the code it ran under.

## 2026-10-27: Secret-audit rule adopted

No credential of any kind enters this repository. A scripted audit
(scripts/audit_history.py) scans the full commit history for
credential-shaped content and gates any push. The audit's later
amendments are recorded below (2026-10-30 and 2026-11-01).

## 2026-10-27 (later): D3 scored evidence form: traces only

Three adjudicator evidence forms were compared on a shakedown set:
numeric traces only, raw frames with traces, and segmentation
overlays with traces. Recall to a human was identical across forms,
and the overlay form confirmed nothing. Adopted: the scored form is
traces only. It ties the best confirmation rate of the three and is
the strongest privacy form, because no image data leaves the machine
in the evidence pack. The overlay form remains implemented as a
non-scored form. Full detail is in SPEC.md.

## 2026-10-28: Amendment P3: side-view descent window lower bound 0.4 s to 0.15 s

Measured on development data only, under the check the frozen
protocol scheduled: side-view fall descent cores cluster below the
original 0.4 s lower bound. Adopted: the side-view descent window is
[0.15, 1.0] s; the ceiling window [0.15, 1.35] s is unchanged. The
change moved the configuration hash from d940d0c26c123909 to
6d7c03257b12ab00. The test split was untouched. Derivation and
evidence are in SPEC.md.

## 2026-10-29: Splits frozen

The development split (215 clips) and the test split (68 clips) were
frozen, with manifests and checksums recorded in
results/split_freeze_2026-10-29.md. The test split is reserved for
one confirmation run under the shipped configuration.

## 2026-10-29: D1 gate FAIL; pivot to rules-primary adopted

The pre-registered gate ran on the development split. Criterion
outcomes: the safety veto passed (zero additional missed falls; both
arms miss the same falls); false-alarm reduction failed (0.0%
relative and 0 absolute; the counted false alarms were 4 before the
adjudicator and 4 after it); usable verdicts passed (141 of 142,
99.3%). Under the rule fixed in advance, the Muse Spark adjudicator
was removed from the disposition path.

The shipped configuration is rules-primary: motion gate, then SAM 3.1
segmentation evidence, then features and timing, then rules, then the
D2 alert ladder. SAM 3.1 stays in the loop as the evidence layer. The
confirmation run is one run of this configuration on the frozen test
split; its record is results/confirmation_summary.md, which cites
this entry as the adoption of that configuration. The gate results
are published in full (results/gate_d1_dev_summary.md); the failed
gate is a headline finding, not a number to soften.

## 2026-10-29 (later): Post-hoc diagnostic: dev label quality behind the gate's false alarms

After the gate, a visual audit of the development split's discordant
cases found that all four events the gate counted as false alarms
visibly show staged falls. The two source archives those events come
from ship no per-video annotation files, so their everyday-activity
labels in the development manifest were inferred from room layout.
This is a post-hoc diagnostic about label quality. It changes no
score and no verdict: the gate FAIL recorded above stands as
measured, and the adjudicator's value on the false-alarm axis is
recorded as unmeasured by the gate, not refuted. Detail:
results/gate_d1_visual_audit.md and
results/gate_d1_visual_reaudit.md.

## 2026-10-30: Amendment to the secret-audit rule: verified provenance checksums

The repository legitimately contains checksums (SHA-256) of project
files and datasets. A long hex value in prose is suppressed by the
audit only when it is explicitly labelled as a SHA-256, the prose
names the project file it hashes, and recomputation from that file
matches exactly. A pass under this amendment is reported as a pass
under the amendment, never as a pass of the original unamended rule.
Credential patterns are checked first and can never be exempted.

## 2026-11-01: Amendment to the secret-audit rule: hash manifests under results/

Hash manifests under results/ (files ending in .sha256) join the
provenance treatment under strict whole-line format validation: a
line counts as provenance data only when it matches the checksum
manifest format exactly, and any non-conforming non-empty line is a
hit. The treatment requires a recomputation verification on record
for the manifest; for the sealed files manifest that record is
results/sealed_files_manifest_verification.md.

## 2026-11-01: Post-hoc supplementary SAM ablation (development split only)

The gate compared rules plus SAM evidence against rules plus SAM
evidence plus the adjudicator, so the marginal contribution of the
SAM evidence itself was unmeasured. A no-SAM arm was run post-hoc on
the development split under a written plan fixed before the run:
identical gate, timing, thresholds and scoring, with the SAM-derived
phases marked evidence-absent. Removing the SAM evidence makes
confirmation unreachable by construction and changes the operating
point on every reading tried. This ablation is a post-hoc
diagnostic, not a confirmation result; the frozen test split was not
touched and no SAM calls were made. Package:
results/sam_ablation_dev_2026-11-01/.

## 2026-11-01: Replication timing: sealed subjects run after the final

A sealed replication set (UP-Fall Subjects 3 to 5, with a file
manifest and checksums in results/) was assembled and never
inspected. The frozen shipped pipeline will be run on it once, after
the hackathon final on 2026-11-09, and the outcome published whatever
it is. Replication results are never pooled with the frozen test
split. Plan: results/replication_addendum.md.

## 2026-11-01 (editorial): wording of the record clarified for publication

Editorial amendment, publication hygiene only. In this record, in
SPEC.md, in the results records, in code comments, and in commit
messages, passages that credited decisions to the review process were
reworded to state the decision and the reasoning or evidence it rests
on. No number, threshold, date, result, or code behaviour changed:
the configuration hash is 6d7c03257b12ab00, as before, and the test
suite passes in full (77 checks), as before. Citations that pointed
outside this repository were replaced by the substance itself or by
the run records under results/. Decision labels (D1-D5, P1-P3) are
unchanged.
