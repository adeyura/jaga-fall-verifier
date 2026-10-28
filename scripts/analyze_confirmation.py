"""Confirmation analysis: event-level scoring of the frozen run.

Reads the per-clip records written by scripts/run_confirmation.py
(cache/confirmation/) and produces the run's result artifacts:

  results/confirmation_results.csv  one row per test event with the
                                    pivot arm's disposition
  results/confirmation_summary.md   per-stratum tables, cascade
                                    metrics, spend (gate-summary
                                    conventions)

Scoring definitions are the gate's, unchanged (SPEC D1 semantics):
a fall is missed only when its final disposition clears it without
escalation (cleared, or gate_miss). A rules "uncertain" segment, a
segment with no evidence, and an unusable anything escalate: an
alert to a human, never a clear. A hard negative is a false alarm
only when the disposition confirms a fall; it counts as cleared
only on a rules-negative disposition. Pipeline errors are their own
category, never scored as negatives and never dropped from the
listing. Event aggregation follows the freeze-note convention: an
event takes the most protective disposition across its clips —
confirmed > escalated > pipeline_error > cleared > gate_miss;
gate_miss requires every clip of the event to have missed.

The arm is the pivot configuration (DECISIONS 2026-10-29): the
analyzer asserts that no record carries an adjudication — Spark was
structurally absent from this run.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jaga.config import config_hash  # noqa: E402

STATE = ROOT / "cache" / "confirmation"
EXPECTED_HASH = "6d7c03257b12ab00"
ARM = "pivot_rules_primary"
PREC = {"confirmed": 0, "escalated": 1, "pipeline_error": 2,
        "cleared": 3, "gate_miss": 4}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt_ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]" if n else "n/a"


def clip_disposition(rec: dict) -> str:
    """The pivot (rules) disposition of one clip record."""
    if rec.get("outcome") == "pipeline_error":
        return "pipeline_error"
    if rec.get("outcome") == "gate_miss":
        return "gate_miss"
    disps = []
    for seg in rec.get("segments", []):
        rl = seg.get("rules_label")
        if rl == "fall_candidate":
            disps.append("confirmed")
        elif rl == "negative":
            disps.append("cleared")
        else:  # uncertain, no_evidence: cannot clear
            disps.append("escalated")
    if not disps:
        return "pipeline_error"
    return min(disps, key=lambda d: PREC[d])


def event_disposition(clip_disps: list[str]) -> str:
    for d in ("confirmed", "escalated", "pipeline_error", "cleared"):
        if d in clip_disps:
            return d
    return "gate_miss"


def arm_table(events: list[dict]) -> dict:
    t = {"n_fall": 0, "n_adl": 0}
    for cat in ("confirmed", "escalated", "cleared", "gate_miss",
                "pipeline_error"):
        t[f"fall_{cat}"] = 0
        t[f"adl_{cat}"] = 0
    for e in events:
        lab = e["label"]
        t[f"n_{lab}"] += 1
        t[f"{lab}_{e['disp']}"] += 1
    t["fall_missed"] = t["fall_cleared"] + t["fall_gate_miss"]
    t["adl_fa"] = t["adl_confirmed"]
    return t


def main() -> None:
    h = config_hash()
    assert h == EXPECTED_HASH, f"config hash drift: {h}"
    rows = list(csv.DictReader((ROOT / "results" / "split_test.csv").open()))
    assert len(rows) == 68, f"test rows: {len(rows)}"
    recs: dict[str, dict] = {}
    for p in sorted(STATE.glob("*.json")):
        if p.name == "state.json":
            continue
        rec = json.loads(p.read_text())
        recs[rec["clip_id"]] = rec
    assert len(recs) == 68, f"confirmation records: {len(recs)}"
    for rec in recs.values():
        assert rec.get("config_hash") == EXPECTED_HASH, rec["clip_id"]
        assert rec.get("arm") == ARM, rec["clip_id"]
        for seg in rec.get("segments", []):
            assert seg.get("adjudication") is None, \
                f"adjudication present in pivot run: {rec['clip_id']}"

    # ---- events ------------------------------------------------------
    events: dict[str, dict] = {}
    for r in rows:
        cid = r["clip_id"]
        rec = recs[cid]
        ev = events.setdefault(rec["event_id"], {
            "event_id": rec["event_id"], "dataset": r["dataset"],
            "label": r["label"], "clips": [], "duration_s": None})
        ev["clips"].append(cid)
        ev.setdefault("_disp", []).append(clip_disposition(rec))
        if rec.get("duration_s") is not None:
            ev["duration_s"] = (rec["duration_s"]
                                if ev["duration_s"] is None
                                else max(ev["duration_s"],
                                         rec["duration_s"]))
    for ev in events.values():
        ev["disp"] = event_disposition(ev.pop("_disp"))
    ev_list = sorted(events.values(),
                     key=lambda e: (e["dataset"], e["label"],
                                    e["event_id"]))
    assert len(ev_list) == 44, f"events: {len(ev_list)}"

    strata = {"overall": ev_list,
              "up_fall": [e for e in ev_list if e["dataset"] == "up_fall"],
              "le2i": [e for e in ev_list if e["dataset"] == "le2i"]}
    tables = {s: arm_table(evs) for s, evs in strata.items()}
    stratum_hours = {s: (sum(e["duration_s"] or 0 for e in evs
                             if e["label"] == "adl") / 3600.0)
                     for s, evs in strata.items()}

    # ---- cascade metrics ----------------------------------------------
    clips = list(recs.values())
    falls_c = [r for r in clips if r["label"] == "fall"]
    gate_reached = [r for r in falls_c if r.get("gate", {}).get("n_segments")]
    sam_err, kf_total, kf_empty, api_calls = [], 0, 0, 0
    for rec in clips:
        for seg in rec.get("segments", []):
            run = seg.get("run") or {}
            kf_total += len(run.get("keyframes", []))
            kf_empty += run.get("empty_keyframes", 0)
            api_calls += run.get("api_calls", 0)
            if "pipeline_error" in seg:
                sam_err.append((rec["clip_id"], seg["pipeline_error"][:160]))
    pipe_errs = [r for r in clips if r.get("outcome") == "pipeline_error"]
    walls = sorted(r["wall_s"] for r in clips if r.get("wall_s") is not None)

    # ---- write results CSV ----------------------------------------------
    res_dir = ROOT / "results"
    with (res_dir / "confirmation_results.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "dataset", "label", "n_clips", "clip_ids",
                    "duration_s", "pivot_disposition",
                    "config_hash", "arm"])
        for e in ev_list:
            w.writerow([e["event_id"], e["dataset"], e["label"],
                        len(e["clips"]), ";".join(e["clips"]),
                        e["duration_s"], e["disp"], EXPECTED_HASH, ARM])

    # ---- summary MD ------------------------------------------------------
    def arm_rows(name: str, t: dict, hours: float) -> str:
        nf, na = t["n_fall"], t["n_adl"]
        rec_n = t["fall_confirmed"] + t["fall_escalated"]
        rec_d = nf - t["fall_pipeline_error"]
        esc_d = nf + na - t["fall_pipeline_error"] - t["adl_pipeline_error"]
        esc_n = t["fall_escalated"] + t["adl_escalated"]
        prec_d = t["fall_confirmed"] + t["adl_confirmed"]
        return "\n".join([
            f"### {name}",
            f"- Fall events: {nf}; confirmed {t['fall_confirmed']}, "
            f"escalated {t['fall_escalated']}, cleared "
            f"{t['fall_cleared']}, gate-missed {t['fall_gate_miss']}, "
            f"pipeline errors {t['fall_pipeline_error']}.",
            f"- Not-missed recall (confirmed or escalated, errors "
            f"excluded): {fmt_ci(rec_n, rec_d)}.",
            f"- ADL events: {na}; false alarms (confirmed) "
            f"{t['adl_confirmed']}, escalated {t['adl_escalated']}, "
            f"cleared {t['adl_cleared']}, gate-missed "
            f"{t['adl_gate_miss']}, pipeline errors "
            f"{t['adl_pipeline_error']}.",
            f"- Precision at dataset prevalence: "
            f"{fmt_ci(t['fall_confirmed'], prec_d)}.",
            f"- Escalation rate (all events, errors excluded): "
            f"{fmt_ci(esc_n, esc_d)}.",
            f"- False alarms per hour of ADL footage: "
            f"{t['adl_confirmed'] / hours:.2f} "
            f"({t['adl_confirmed']} FA / {hours:.2f} h)",
        ])
    lines = [
        "# Confirmation run — frozen test split (2026-10-29)",
        "",
        f"Config hash `{EXPECTED_HASH}` (verified at run start and "
        f"stamped on every record). Arm: `{ARM}` — the pivot "
        "configuration adopted 2026-10-29 (DECISIONS) after the D1 "
        "gate FAIL: motion gate -> SAM 3.1 evidence -> "
        "features/timing (amended window) -> rules -> D2 alert "
        "ladder. Muse Spark is not in this arm; the analyzer "
        "asserted no record carries an adjudication. Set: the frozen "
        "test split only, 68 clips / 44 events (27 fall, 17 ADL); "
        "UP-Fall Subject 2 + Le2i holdout Coffee_room_02. One run; "
        "no tuning. Dev and confirmation numbers are labeled and "
        "never pooled.",
        "",
    ]
    for sname in ("overall", "up_fall", "le2i"):
        lines += [f"## Stratum: {sname}", ""]
        lines.append(arm_rows("Pivot (rules-primary)",
                              tables[sname], stratum_hours[sname]))
        lines.append("")
    lines += [
        "## Cascade metrics (clip level)", "",
        f"- Gate recall on fall clips: "
        f"{fmt_ci(len(gate_reached), len(falls_c))} reached the SAM "
        f"stage; gate-missed fall clips "
        f"{sum(1 for r in falls_c if r.get('outcome') == 'gate_miss')}.",
        f"- SAM keyframes: {kf_total} total, {kf_empty} empty "
        f"({kf_empty / kf_total:.1%}); fresh API calls {api_calls}.",
        f"- Pipeline-error clips: {len(pipe_errs)} "
        f"({[r['clip_id'] for r in pipe_errs]}).",
        f"- Segment-level SAM/rules errors recorded: {len(sam_err)}.",
        f"- Latency per clip: median {walls[len(walls) // 2]:.1f}s, "
        f"mean {sum(walls) / len(walls):.1f}s.",
    ]
    state = json.loads((STATE / "state.json").read_text()) \
        if (STATE / "state.json").exists() else {}
    lines += ["", "## Spend", "",
              f"```json\n{json.dumps({k: v for k, v in state.items() if k in ('spend', 'retry_log')}, indent=1)}\n```",
              "", "Limitations: staged falls by young actors in lab "
              "rooms; dataset performance is not deployment "
              "performance. The Le2i confirmation is a single room's "
              "result (Coffee_room_02, a different physical room and "
              "camera from dev's Coffee_room_01 but the same scene "
              "type), and UP-Fall confirmation a single subject's "
              "(Subject 2): the run bounds generalization, it does "
              "not establish it. UP-Fall ADL categories are 3 events "
              "each; stumble-and-recover and crouch do not exist as "
              "labeled categories in either dataset.", ""]
    (res_dir / "confirmation_summary.md").write_text("\n".join(lines))
    print(json.dumps({"tables": tables,
                      "pipeline_errors": [r["clip_id"] for r in pipe_errs],
                      "sam_segment_errors": sam_err,
                      "cascade": {"gate_reached": len(gate_reached),
                                  "fall_clips": len(falls_c),
                                  "kf_total": kf_total,
                                  "kf_empty": kf_empty,
                                  "api_calls": api_calls}}, indent=1))


if __name__ == "__main__":
    main()
