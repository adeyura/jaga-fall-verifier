"""Joined comparison: no-SAM arm vs recorded rules+SAM arm (dev events).

Reads nosam_dev_dispositions.csv (produced by run_nosam.py, which already
joined the gate record) and writes comparison.md. The arm of record is
v2 (run-anchored, new-burst stillness; see METHODS_AMENDMENT.md); the
appendix reports the v1 and v2a stillness readings' headline numbers
as a sensitivity analysis. Wilson intervals follow the gate analyzer's
convention.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

OUT = Path.home() / "workspace" / "jaga-ablation"
CATS = ("confirmed", "escalated", "cleared", "gate_miss", "pipeline_error")
SAM = "sam_rules_disposition"
PRIMARY = "nosam_disposition"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt(k: int, n: int) -> str:
    if not n:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]"


def table(rows: list[dict], key: str) -> dict:
    t = {f"{lab}_{c}": 0 for lab in ("fall", "adl") for c in CATS}
    t["n_fall"] = t["n_adl"] = 0
    for r in rows:
        t[f"n_{r['label']}"] += 1
        t[f"{r['label']}_{r[key]}"] += 1
    t["fall_not_missed"] = t["fall_confirmed"] + t["fall_escalated"]
    t["fall_missed"] = t["fall_cleared"] + t["fall_gate_miss"]
    t["esc_all"] = t["fall_escalated"] + t["adl_escalated"]
    t["n"] = t["n_fall"] + t["n_adl"]
    return t


def block(name: str, rows: list[dict], key: str = PRIMARY,
          key_label: str = "no-SAM v2 (this run)") -> str:
    s, n = table(rows, SAM), table(rows, key)
    lines = [f"### {name} (falls {s['n_fall']}, ADL {s['n_adl']})", "",
             f"| Measure | rules+SAM (recorded) | {key_label} | delta |",
             "|---|---|---|---|"]
    def row(label, sk, nk, denom):
        d = (nk - sk) / denom if denom else float("nan")
        lines.append(f"| {label} | {fmt(sk, denom)} | {fmt(nk, denom)} "
                     f"| {d:+.3f} |")
    nf, na = s["n_fall"], s["n_adl"]
    row("Falls not-missed (confirmed+escalated)", s["fall_not_missed"],
        n["fall_not_missed"], nf)
    row("Falls confirmed", s["fall_confirmed"], n["fall_confirmed"], nf)
    row("Falls escalated", s["fall_escalated"], n["fall_escalated"], nf)
    row("Falls cleared", s["fall_cleared"], n["fall_cleared"], nf)
    row("Falls gate-missed", s["fall_gate_miss"], n["fall_gate_miss"], nf)
    row("Falls missed (cleared+gate-missed)", s["fall_missed"],
        n["fall_missed"], nf)
    row("ADL false alarms (confirmed)", s["adl_confirmed"],
        n["adl_confirmed"], na)
    row("ADL escalated", s["adl_escalated"], n["adl_escalated"], na)
    row("ADL cleared", s["adl_cleared"], n["adl_cleared"], na)
    row("ADL gate-missed", s["adl_gate_miss"], n["adl_gate_miss"], na)
    row("Escalation rate (all events)", s["esc_all"], n["esc_all"], s["n"])
    for arm, t in (("rules+SAM", s), ("no-SAM", n)):
        if t["fall_pipeline_error"] or t["adl_pipeline_error"]:
            lines.append(f"| Pipeline errors ({arm}) | falls "
                         f"{t['fall_pipeline_error']}, ADL "
                         f"{t['adl_pipeline_error']} | | |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    rows = list(csv.DictReader((OUT / "nosam_dev_dispositions.csv").open()))
    caveats = """# SAM ablation (dev set) — joined comparison

## Caveats — these travel with every number below

1. **Post-hoc.** The no-SAM arm was defined on 2026-11-01, after the
   gate, the pivot, and the confirmation run were all known. This is a
   supplementary diagnostic, not a pre-registered comparison, and must
   always be described as post-hoc and supplementary.
2. **Dev is the design set.** The rules' thresholds were tuned on these
   clips. Absolute dev numbers are optimistic for BOTH arms; only the
   within-dev delta between arms is informative, and even it is a
   dev-set quantity.
3. **The frozen test was not touched** — not run, not read for scoring.
   The sealed subjects 3–5 were not touched. Headline numbers
   (confirmation run) are unchanged by this analysis.
4. **Zero SAM calls were made.** The shipped arm is the recorded gate
   output (`results/gate_d1_dev_results.csv`, `rules_disposition`,
   config hash `6d7c03257b12ab00`); the no-SAM arm needs no SAM by
   construction.
5. **Confirmation is unreachable in the no-SAM arm by construction**:
   confirming requires both posture phases, and posture is SAM
   evidence with no motion-signal equivalent. Read the confirmed
   delta as "what confirmation costs", not as a tuning failure.
6. **The motion stillness is a construction, and its sensitivity is
   reported, not hidden.** The arm of record (v2) anchors the
   stillness window at the descent run's end and reads "moved after
   the descent" as a new motion burst under the frozen hysteresis.
   The originally defined reading (v1, core-anchored activity level)
   was found to book the descent's own envelope tail as post-descent
   movement; it and the intermediate reading (v2a) are reported in
   the appendix. See METHODS_AMENDMENT.md for the full account and
   the recorded instance that exposed it.
7. Further known asymmetries (window span = segment rather than
   track; the shipped arm's multi-track verdict merge has no motion
   counterpart; no keyframe-fallback descent; no no_evidence path)
   are documented in METHODS.md and qualify every per-event
   difference.

Arm definition, in one line: identical gate, identical timing,
identical thresholds and scoring; SAM-derived phases (pre/post
posture, keyframe-fallback descent) treated as evidence-absent, and
stillness replaced by its motion-signal equivalent. Full definition:
METHODS.md + METHODS_AMENDMENT.md.

"""
    parts = [caveats, block("All dev events", rows)]
    for ds in ("up_fall", "le2i"):
        parts.append(block(f"Stratum: {ds}",
                           [r for r in rows if r["dataset"] == ds]))
    parts.append("""## How to read this

What is robust across every stillness reading (v1, v2a, v2):

- **Confirmation is SAM-carried.** Falls confirmed fall 26/99 → 0 and
  ADL false alarms 4/92 → 0 in all readings, by construction: the
  posture phases are the confirmation path.
- **The shipped operating point is unreachable without SAM.** The
  shipped arm holds falls not-missed at 0.717 while clearing 36/92
  ADL events. No motion reading holds both: v1 and v2a keep ADL
  clearances (70, 64) only by clearing most falls as well (falls
  not-missed 0.222, 0.303); v2 keeps the falls (0.990) only by
  escalating all 92 ADL events. Motion evidence alone trades one
  failure mode for the other at every operationalization tried.
- The shipped arm's ADL clearances run through the posture veto
  (a slow descent contradicted by "not horizontal after"), and its
  fall clearances through SAM centroid stillness at a sensitivity
  the energy signal does not reproduce. Both are SAM evidence doing
  disposition work, in opposite directions.

What is NOT robust: falls not-missed and the escalation rate swing
with the stillness construction (0.222 / 0.303 / 0.990). Any single
one of those numbers quoted without its construction would mislead;
the deltas that survive are the structural ones above.
""")
    parts.append("## Appendix — sensitivity to the stillness construction\n")
    parts.append("Pooled dev events under the two alternative stillness "
                 "readings (same arm otherwise). V1 is the definition as "
                 "originally written; v2a isolates the anchor change; "
                 "v2 (the arm of record, above) additionally reads "
                 "post-descent movement as a new burst.\n")
    parts.append(block("V1 reading (as originally defined)", rows,
                       "nosam_v1_disposition", "no-SAM v1"))
    parts.append(block("V2a reading (run anchor, activity level)", rows,
                       "nosam_v2a_disposition", "no-SAM v2a"))
    diffs = [r for r in rows if r[SAM] != r[PRIMARY]]
    parts.append(f"## Per-event agreement (arm of record, v2)\n\n"
                 f"{len(rows) - len(diffs)}/{len(rows)} events agree; "
                 f"{len(diffs)} differ.\n")
    parts.append("| event | dataset | label | rules+SAM | no-SAM v2 |")
    parts.append("|---|---|---|---|---|")
    for r in sorted(diffs, key=lambda r: (r["dataset"], r["event_id"])):
        parts.append(f"| {r['event_id']} | {r['dataset']} | {r['label']} "
                     f"| {r[SAM]} | {r[PRIMARY]} |")
    parts.append("")
    (OUT / "comparison.md").write_text("\n".join(parts))
    print(f"wrote comparison.md; {len(diffs)} differing events (v2)")


if __name__ == "__main__":
    main()
