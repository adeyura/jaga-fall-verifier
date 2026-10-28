"""D1 gate analysis: event-level scoring of the dev gate run.

Reads the per-clip records written by scripts/run_gate_d1_dev.py
(cache/gate_d1/{main,abc,baselines}/) and produces the run's result
artifacts under results/:

  gate_d1_dev_results.csv     one row per dev event, every arm's
                              disposition (the single results file)
  gate_d1_dev_summary.md      D1 verdict, per-arm tables by dataset,
                              cascade metrics, baselines, D3 A/B/C
  gate_d1_dev_discordants.csv every event where arms disagree or an
                              arm's verdict disagrees with the label

Scoring definitions (SPEC D1, frozen): a fall is missed only when its
final disposition clears it without escalation (dispositions: cleared,
or gate_miss — the gate found nothing to escalate). An adjudicator
"uncertain", an unusable adjudication, a rules "uncertain", and a
segment with no evidence all escalate: an alert to a human, never a
clear. A hard negative is a false alarm only when the final
disposition confirms a fall; it counts as cleared only on a benign
final disposition (rules negative, or adjudicator benign). Pipeline
errors are reported as their own category, never scored as negatives
and never silently dropped from the listing.

Event aggregation (freeze-note convention): an event takes the most
protective disposition across its clips — confirmed > escalated >
pipeline_error > cleared > gate_miss; gate_miss requires every clip
of the event to have missed at the gate.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jaga.config import config_hash  # noqa: E402

STATE = ROOT / "cache" / "gate_d1"
EXPECTED_HASH = "6d7c03257b12ab00"
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


def seg_dispositions(rec: dict) -> list[tuple[str, str]]:
    """(rules_only, full) disposition per segment of a clip record."""
    out = []
    for seg in rec.get("segments", []):
        rl = seg.get("rules_label")
        if rl == "fall_candidate":
            rules = "confirmed"
        elif rl == "negative":
            rules = "cleared"
        else:  # uncertain, no_evidence: cannot clear
            rules = "escalated"
        full = rules
        if rl in ("fall_candidate", "uncertain"):
            a = seg.get("adjudication")
            if a and a.get("usable") and a.get("verdict") in (
                    "fall", "benign", "uncertain"):
                full = {"fall": "confirmed", "benign": "cleared",
                        "uncertain": "escalated"}[a["verdict"]]
            else:
                full = "escalated"  # unusable adjudication escalates
        out.append((rules, full))
    return out


def clip_disposition(rec: dict, arm: int) -> str:
    if rec.get("outcome") == "pipeline_error":
        return "pipeline_error"
    if rec.get("outcome") == "gate_miss":
        return "gate_miss"
    disps = [d[arm] for d in seg_dispositions(rec)]
    if not disps:
        return "pipeline_error"
    return min(disps, key=lambda d: PREC[d])


def event_disposition(clip_disps: list[str]) -> str:
    for d in ("confirmed", "escalated", "pipeline_error", "cleared"):
        if d in clip_disps:
            return d
    return "gate_miss"


def load(phase: str, form: str = "") -> dict[str, dict]:
    d = STATE / phase / form if form else STATE / phase
    out = {}
    for p in sorted(d.glob("*.json")):
        rec = json.loads(p.read_text())
        out[rec["clip_id"]] = rec
    return out


def arm_table(events: list[dict], arm_key: str) -> dict:
    t = {"n_fall": 0, "n_adl": 0}
    for cat in ("confirmed", "escalated", "cleared", "gate_miss",
                "pipeline_error"):
        t[f"fall_{cat}"] = 0
        t[f"adl_{cat}"] = 0
    for e in events:
        lab = e["label"]
        t[f"n_{lab}"] += 1
        t[f"{lab}_{e[arm_key]}"] += 1
    t["fall_missed"] = t["fall_cleared"] + t["fall_gate_miss"]
    t["adl_fa"] = t["adl_confirmed"]
    return t


def main() -> None:
    h = config_hash()
    assert h == EXPECTED_HASH, f"config hash drift: {h}"
    rows = list(csv.DictReader((ROOT / "results" / "split_dev.csv").open()))
    main_recs = load("main")
    base_recs = load("baselines")
    abc = {f: load("abc", f) for f in ("raw", "overlay")}
    assert len(main_recs) == 215, f"main records: {len(main_recs)}"
    assert len(base_recs) == 215, f"baseline records: {len(base_recs)}"
    for f in ("raw", "overlay"):
        assert len(abc[f]) == 48, f"abc/{f} records: {len(abc[f])}"
    for recs in (main_recs, base_recs, *abc.values()):
        for rec in recs.values():
            assert rec.get("config_hash") == EXPECTED_HASH, rec["clip_id"]

    # ---- events ------------------------------------------------------
    events: dict[str, dict] = {}
    for r in rows:
        cid = r["clip_id"]
        rec = main_recs[cid]
        ev = events.setdefault(rec["event_id"], {
            "event_id": rec["event_id"], "dataset": r["dataset"],
            "label": r["label"], "clips": [], "duration_s": None})
        ev["clips"].append(cid)
        ev.setdefault("_disp_rules", []).append(clip_disposition(rec, 0))
        ev.setdefault("_disp_full", []).append(clip_disposition(rec, 1))
        if rec.get("duration_s") is not None:
            ev["duration_s"] = (rec["duration_s"] if ev["duration_s"] is None
                                else max(ev["duration_s"], rec["duration_s"]))
    for ev in events.values():
        ev["rules"] = event_disposition(ev.pop("_disp_rules"))
        ev["full"] = event_disposition(ev.pop("_disp_full"))
    ev_list = sorted(events.values(),
                     key=lambda e: (e["dataset"], e["label"], e["event_id"]))

    # ---- baselines at event level ------------------------------------
    def baseline_event(ev: dict, kind: str) -> str:
        vals = []
        for cid in ev["clips"]:
            b = base_recs[cid]
            if kind == "aspect":
                vals.append(b.get("aspect_only") or "none")
            else:
                so = b.get("spark_only")
                vals.append(so["verdict"] if so and so.get("usable")
                            else ("unusable" if so else "none"))
        if "fall" in vals:
            return "fall"
        if kind == "spark" and "uncertain" in vals:
            return "uncertain"
        if "benign" in vals:
            return "benign"
        return vals[0] if vals else "none"
    for ev in ev_list:
        ev["aspect"] = baseline_event(ev, "aspect")
        ev["spark"] = baseline_event(ev, "spark")

    # ---- D3 A/B/C on UP-Fall (traces = main records) ------------------
    abc_forms = {"traces": {}, "raw": abc["raw"], "overlay": abc["overlay"]}
    abc_mismatch = []
    for cid, mrec in main_recs.items():
        if mrec["dataset"] != "up_fall":
            continue
        abc_forms["traces"][cid] = mrec
        for form in ("raw", "overlay"):
            arec = abc[form][cid]
            same = ([s.get("rules_label") for s in mrec["segments"]]
                    == [s.get("rules_label") for s in arec["segments"]])
            if not same:
                abc_mismatch.append((cid, form))
    abc_events: dict[str, dict] = {}
    for form, recs in abc_forms.items():
        per_ev: dict[str, list[str]] = defaultdict(list)
        for cid, rec in recs.items():
            if any((cid, form) == m for m in abc_mismatch):
                continue
            per_ev[rec["event_id"]].append(clip_disposition(rec, 1))
        abc_events[form] = {eid: event_disposition(ds)
                            for eid, ds in per_ev.items()}
    for ev in ev_list:
        if ev["dataset"] == "up_fall":
            for form in abc_forms:
                ev[f"abc_{form}"] = abc_events[form].get(ev["event_id"], "")

    # ---- D1 scoring ----------------------------------------------------
    strata = {"overall": ev_list,
              "up_fall": [e for e in ev_list if e["dataset"] == "up_fall"],
              "le2i": [e for e in ev_list if e["dataset"] == "le2i"]}
    tables = {s: {arm: arm_table(evs, arm) for arm in ("rules", "full")}
              for s, evs in strata.items()}
    ov = tables["overall"]
    missed_rules = {e["event_id"] for e in ev_list
                    if e["label"] == "fall" and e["rules"] in
                    ("cleared", "gate_miss")}
    missed_full = {e["event_id"] for e in ev_list
                   if e["label"] == "fall" and e["full"] in
                   ("cleared", "gate_miss")}
    additional_missed = missed_full - missed_rules
    fa_rules = {e["event_id"] for e in ev_list
                if e["label"] == "adl" and e["rules"] == "confirmed"}
    fa_full = {e["event_id"] for e in ev_list
               if e["label"] == "adl" and e["full"] == "confirmed"}
    fa_both = fa_rules & fa_full
    fa_rules_only = fa_rules - fa_full
    fa_full_only = fa_full - fa_rules
    rfa, ffa = len(fa_rules), len(fa_full)
    rel = (rfa - ffa) / rfa if rfa else float("nan")
    adj_att = adj_use = 0
    for rec in main_recs.values():
        for seg in rec.get("segments", []):
            a = seg.get("adjudication")
            if a is not None:
                adj_att += 1
                adj_use += 1 if a.get("usable") else 0
    usable_rate = adj_use / adj_att if adj_att else float("nan")
    d1 = {
        "safety_veto_pass": len(additional_missed) == 0,
        "fa_relative": rel, "fa_relative_pass": rfa > 0 and rel >= 0.40,
        "fa_absolute": rfa - ffa, "fa_absolute_pass": (rfa - ffa) >= 3,
        "usable_rate": usable_rate, "usable_pass": usable_rate >= 0.95,
    }
    d1["verdict"] = ("PASS" if all([d1["safety_veto_pass"],
                                    d1["fa_relative_pass"],
                                    d1["fa_absolute_pass"],
                                    d1["usable_pass"]]) else "FAIL")

    # ---- cascade metrics ----------------------------------------------
    clips = list(main_recs.values())
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
    adl_hours = sum(e["duration_s"] or 0 for e in ev_list
                    if e["label"] == "adl") / 3600.0

    # ---- discordants ----------------------------------------------------
    disc = []
    for e in ev_list:
        reasons = []
        if e["rules"] != e["full"]:
            reasons.append("arms_disagree")
        if e["label"] == "fall" and e["full"] != "confirmed":
            reasons.append("fall_not_confirmed_by_full")
        if e["label"] == "fall" and e["rules"] != "confirmed":
            reasons.append("fall_not_confirmed_by_rules")
        if e["label"] == "adl" and "confirmed" in (e["rules"], e["full"]):
            reasons.append("adl_confirmed_fall")
        if "pipeline_error" in (e["rules"], e["full"]):
            reasons.append("pipeline_error")
        if e.get("aspect") == "fall" and e["label"] == "adl":
            reasons.append("aspect_false_alarm")
        if e.get("spark") == "fall" and e["label"] == "adl":
            reasons.append("spark_only_false_alarm")
        if reasons:
            disc.append({**{k: e[k] for k in
                            ("event_id", "dataset", "label", "rules",
                             "full", "aspect", "spark")},
                         "clips": ";".join(e["clips"]),
                         "reasons": ";".join(reasons)})

    # ---- write results CSV ----------------------------------------------
    res_dir = ROOT / "results"
    with (res_dir / "gate_d1_dev_results.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "dataset", "label", "n_clips", "clip_ids",
                    "duration_s", "rules_disposition", "full_disposition",
                    "aspect_only_event", "spark_only_event",
                    "abc_traces", "abc_raw", "abc_overlay",
                    "config_hash", "evidence_form"])
        for e in ev_list:
            w.writerow([e["event_id"], e["dataset"], e["label"],
                        len(e["clips"]), ";".join(e["clips"]),
                        e["duration_s"], e["rules"], e["full"],
                        e["aspect"], e["spark"],
                        e.get("abc_traces", ""), e.get("abc_raw", ""),
                        e.get("abc_overlay", ""), EXPECTED_HASH, "traces"])
    with (res_dir / "gate_d1_dev_discordants.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["event_id", "dataset", "label",
                                          "rules", "full", "aspect",
                                          "spark", "clips", "reasons"])
        w.writeheader()
        w.writerows(disc)

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
        "# D1 gate run — dev split (2026-10-28)",
        "",
        f"Config hash `{EXPECTED_HASH}` (verified at run start and "
        "stamped on every record). Evidence form: traces only (D3). "
        "Set: dev split, 215 clips / 191 events (99 fall, 92 ADL); "
        "UP-Fall Subject 1 + Le2i-dev. Test split untouched.",
        "",
        f"## D1 verdict: {d1['verdict']}",
        "",
        "| Criterion | Required | Measured | Result |",
        "|---|---|---|---|",
        f"| 1. Safety veto: additional missed falls vs rules-only | 0 | "
        f"{len(additional_missed)} | "
        f"{'PASS' if d1['safety_veto_pass'] else 'FAIL'} |",
        f"| 2a. Hard-negative FA reduction, relative | >= 40% | "
        f"{rel:.1%} ({rfa} -> {ffa}) | "
        f"{'PASS' if d1['fa_relative_pass'] else 'FAIL'} |",
        f"| 2b. Hard-negative FA reduction, absolute | >= 3 | "
        f"{rfa - ffa} | {'PASS' if d1['fa_absolute_pass'] else 'FAIL'} |",
        f"| 3. Usable adjudicator verdicts | >= 95% | "
        f"{fmt_ci(adj_use, adj_att)} | "
        f"{'PASS' if d1['usable_pass'] else 'FAIL'} |",
        "",
        f"Missed falls: rules-only {len(missed_rules)}, full "
        f"{len(missed_full)}; missed by full only: "
        f"{sorted(additional_missed) or 'none'}; missed by rules only: "
        f"{sorted(missed_rules - missed_full) or 'none'}.",
        f"FA discordant pairs: both arms {len(fa_both)}, rules-only only "
        f"{len(fa_rules_only)}, full only {len(fa_full_only)}.",
    ]
    if rfa <= 5:
        lines.append(
            f"THIN POOL, stated plainly: rules-only produced only {rfa} "
            "false alarms on the dev hard-negative pool, so the "
            ">=3-absolute criterion rests on 2-3 clips and the relative "
            "criterion on a handful of events.")
    stratum_hours = {s: (sum(e["duration_s"] or 0 for e in evs
                             if e["label"] == "adl") / 3600.0)
                     for s, evs in strata.items()}
    for sname in ("overall", "up_fall", "le2i"):
        lines += ["", f"## Stratum: {sname}", ""]
        lines.append(arm_rows("Rules-only", tables[sname]["rules"],
                              stratum_hours[sname]))
        lines.append("")
        lines.append(arm_rows("Full (rules + Spark traces)",
                              tables[sname]["full"], stratum_hours[sname]))
    lines += [
        "", "## Cascade metrics (clip level, main pass)", "",
        f"- Gate recall on fall clips: {fmt_ci(len(gate_reached), len(falls_c))} "
        f"reached the SAM stage; gate-missed fall clips "
        f"{sum(1 for r in falls_c if r.get('outcome') == 'gate_miss')}.",
        f"- SAM keyframes: {kf_total} total, {kf_empty} empty "
        f"({kf_empty / kf_total:.1%}); fresh API calls {api_calls}.",
        f"- Pipeline-error clips: {len(pipe_errs)} "
        f"({[r['clip_id'] for r in pipe_errs]}).",
        f"- Segment-level SAM/rules errors recorded: {len(sam_err)}.",
        f"- Latency per clip: median {walls[len(walls) // 2]:.1f}s, "
        f"mean {sum(walls) / len(walls):.1f}s.",
        "", "## Baselines (D5, event level)", "",
        "| Baseline | Falls called fall | ADL called fall |",
        "|---|---|---|",
    ]
    for kind, key in (("aspect-only", "aspect"), ("spark-only", "spark")):
        fh = sum(1 for e in ev_list if e["label"] == "fall"
                 and e[key] == "fall")
        ah = sum(1 for e in ev_list if e["label"] == "adl"
                 and e[key] == "fall")
        lines.append(f"| {kind} | {fh}/99 | {ah}/92 |")
    lines += ["", "## D3 A/B/C rerun — UP-Fall dev (event level, full arm)", "",
              "| Form | Falls confirmed | Falls escalated | Falls missed "
              "| ADL FA | ADL escalated | ADL cleared |",
              "|---|---|---|---|---|---|---|"]
    upf = [e for e in ev_list if e["dataset"] == "up_fall"]
    for form in ("traces", "raw", "overlay"):
        c = {k: 0 for k in ("fc", "fe", "fm", "af", "ae", "ac")}
        for e in upf:
            d = e.get(f"abc_{form}")
            if e["label"] == "fall":
                c["fc" if d == "confirmed" else
                  "fe" if d == "escalated" else "fm"] += 1
            else:
                c["af" if d == "confirmed" else
                  "ae" if d == "escalated" else "ac"] += 1
        lines.append(f"| {form} | {c['fc']}/15 | {c['fe']}/15 | {c['fm']}/15 "
                     f"| {c['af']}/9 | {c['ae']}/9 | {c['ac']}/9 |")
    if abc_mismatch:
        lines.append(f"A/B/C segment-alignment mismatches (excluded): "
                     f"{abc_mismatch}")
    state = json.loads((STATE / "state.json").read_text()) \
        if (STATE / "state.json").exists() else {}
    lines += ["", "## Spend", "",
              f"```json\n{json.dumps({k: v for k, v in state.items() if 'spend' in k}, indent=1)}\n```",
              "", "Limitations: staged falls by young actors in lab "
              "rooms; dataset performance is not deployment performance. "
              "Le2i is room×class confounded (see split freeze note). "
              "UP-Fall ADL categories are 3 events each; stumble-and-"
              "recover and crouch do not exist as labeled categories in "
              "either dataset.", ""]
    (res_dir / "gate_d1_dev_summary.md").write_text("\n".join(lines))
    print(json.dumps({"d1": {k: (round(v, 4) if isinstance(v, float) else v)
                             for k, v in d1.items()},
                      "tables": tables, "discordants": len(disc),
                      "pipeline_errors": [r["clip_id"] for r in pipe_errs],
                      "sam_segment_errors": sam_err}, indent=1))


if __name__ == "__main__":
    main()
