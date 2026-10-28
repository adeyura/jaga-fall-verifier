"""Frozen confirmation run driver: the pivot arm on the test split.

This is the project's ONE confirmation run (SPEC D5 two-split
protocol; split freeze of 2026-10-29). It runs exactly once, on
results/split_test.csv only (68 clips / 44 events: UP-Fall Subject 2 +
the Le2i holdout Coffee_room_02), under the pivot configuration
adopted 2026-10-29 after the D1 gate FAIL (DECISIONS):

  motion gate -> SAM 3.1 evidence -> features/timing (amended
  window) -> rules -> D2 alert ladder     ("pivot_rules_primary")

Muse Spark is NOT in this run: run_clip is called with no transport
and the default empty adjudicate_labels, so no adjudication can occur
and no segment record can carry one (the analyzer asserts this).

Scope guard: rows come only from results/split_test.csv; the driver
asserts split == 'test' on every row, asserts the UP-Fall rows are
all Subject 2 and the Le2i rows all Coffee_room_02, and asserts the
clip set is disjoint from the dev split. The dev split is never run.

Checkpointing: one JSON record per clip under cache/confirmation/,
written on completion; a rerun skips clips whose record exists under
the current config hash. pipeline_error records get one serial retry
pass (the established exception convention); retried clip ids are
logged in cache/confirmation/state.json. State and cumulative spend
live in the same file.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# /tmp is a 512MB tmpfs on this VM and has already caused a disk-full
# incident during assembly; all temp work goes on the main disk.
TMP = ROOT / "cache" / "tmp"
TMP.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TMPDIR", str(TMP))

sys.path.insert(0, str(ROOT / "src"))

from jaga.config import config_hash  # noqa: E402

HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
STATE_DIR = ROOT / "cache" / "confirmation"
ARM = "pivot_rules_primary"
EXPECTED_HASH = "6d7c03257b12ab00"


def event_id(row: dict) -> str:
    if row["dataset"] == "up_fall":
        return (f"upfall:S{row['subject']}:A{row['activity']}"
                f":T{row['trial']}")
    return row["clip_id"]


def video_path(row: dict) -> Path:
    if row["dataset"] == "up_fall":
        return ROOT / "data" / "up_fall" / "clips" / (
            Path(row["filename"]).stem + ".mp4")
    return ROOT / row["video_path"]


def load_test_rows() -> list[dict]:
    rows = list(csv.DictReader((ROOT / "results" / "split_test.csv").open()))
    for r in rows:
        assert r["split"] == "test", f"non-test row in test split: {r}"
        if r["dataset"] == "up_fall":
            assert r["subject"] == "2", f"non-Subject-2 test row: {r}"
        else:
            assert "coffee-room-02" in r["clip_id"], \
                f"non-holdout Le2i test row: {r}"
    assert len(rows) == 68, f"expected 68 test rows, got {len(rows)}"
    dev_ids = {r["clip_id"] for r in csv.DictReader(
        (ROOT / "results" / "split_dev.csv").open())}
    assert not (dev_ids & {r["clip_id"] for r in rows}), \
        "test/dev clip overlap"
    return rows


def harness_row(row: dict) -> dict:
    """Mirror of the gate driver's mapping: the manifest records
    UP-Fall view as '' and Le2i view as 'corner'; the rules view model
    for both is 'side'. The manifest value is kept on every output
    record as manifest_view."""
    return {"clip_id": row["clip_id"], "label": row["label"],
            "camera": row.get("kind") or row.get("camera", ""),
            "view": "side"}


def job_order(rows: list[dict]) -> list[dict]:
    """Falls first, then ADL (the gate driver's order)."""
    def key(r):
        if r["label"] == "fall":
            return (0, 0 if r["dataset"] == "up_fall" else 1)
        return (1, 0 if r["dataset"] == "up_fall" else 1)
    return sorted(rows, key=key)


def rec_path(clip_id: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / (clip_id.replace("/", "_") + ".json")


def record_done(clip_id: str) -> dict | None:
    p = rec_path(clip_id)
    if not p.exists():
        return None
    try:
        rec = json.loads(p.read_text())
    except Exception:
        return None
    if rec.get("config_hash") != EXPECTED_HASH:
        return None
    return rec


# ---------------------------------------------------------------- worker

_RUNNER = None


def _init_worker():
    global _RUNNER
    from jaga.sam_runner import SamRunner, helper_transport
    _RUNNER = SamRunner(ROOT / "cache", helper_transport(HELPER),
                        keep_rasters=False)


def work(row: dict) -> dict:
    from jaga.harness import run_clip
    meta = {"dataset": row["dataset"], "event_id": event_id(row),
            "manifest_view": row.get("view", ""),
            "config_hash": config_hash(), "arm": ARM}
    try:
        # The pivot arm: no transport, default (empty)
        # adjudicate_labels, no image picker — adjudication cannot
        # occur and Spark is never called.
        rec = run_clip(video_path(row), harness_row(row), _RUNNER,
                       ROOT / "cache")
    except Exception as e:  # run_clip contains stage failures; be safe
        rec = {"clip_id": row["clip_id"], "label": row["label"],
               "outcome": "pipeline_error",
               "error": f"driver-level: {type(e).__name__}: {e}",
               "segments": []}
    rec.update(meta)
    p = rec_path(row["clip_id"])
    p.write_text(json.dumps(rec, indent=1))
    return rec


# ---------------------------------------------------------------- state

def update_state(**kw):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / "state.json"
    state = {}
    if p.exists():
        try:
            state = json.loads(p.read_text())
        except Exception:
            state = {}
    state.update(kw)
    state["config_hash"] = config_hash()
    state["arm"] = ARM
    state["updated_unix"] = time.time()
    p.write_text(json.dumps(state, indent=1))


def spend_of(records: list[dict]) -> dict:
    sam_usd, sam_images, sam_unknown = 0.0, 0, 0
    adj_n = 0
    for rec in records:
        for seg in rec.get("segments", []):
            run = seg.get("run") or {}
            if run:
                if run.get("est_cost_usd") is None:
                    sam_unknown += 1
                else:
                    sam_usd += run["est_cost_usd"]
                sam_images += run.get("images_billed") or 0
            if seg.get("adjudication") is not None:
                adj_n += 1
    return {"sam_est_usd": round(sam_usd, 4),
            "sam_images_billed": sam_images,
            "sam_runs_cost_unknown": sam_unknown,
            "adjudications": adj_n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    h = config_hash()
    if h != EXPECTED_HASH:
        print(f"ABORT: config_hash() = {h}, expected {EXPECTED_HASH}")
        sys.exit(2)
    rows = job_order(load_test_rows())
    todo = []
    for r in rows:
        rec = record_done(r["clip_id"])
        if rec is None or rec.get("outcome") == "pipeline_error":
            todo.append(r)
    if args.limit:
        todo = todo[:args.limit]
    print(f"confirmation: {len(todo)} clips to run "
          f"({68 - len(todo)} already recorded)", flush=True)
    update_state(started_unix=time.time())
    if todo:
        t0 = time.monotonic()
        with ProcessPoolExecutor(max_workers=args.workers,
                                 initializer=_init_worker) as ex:
            futs = {ex.submit(work, r): r for r in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                fut.result()
                if i % 10 == 0 or i == len(todo):
                    el = time.monotonic() - t0
                    print(f"[confirmation] {i}/{len(todo)} clips, "
                          f"{el:.0f}s elapsed, {el / i:.1f}s/clip",
                          flush=True)
                    update_state(progress=f"{i}/{len(todo)}")
    # serial retry pass for pipeline errors (the established
    # exception convention; every retry is logged)
    rows_by_id = {r["clip_id"]: r for r in rows}
    errs = [cid for cid in rows_by_id
            if (record_done(cid) or {}).get("outcome")
            == "pipeline_error"]
    if errs and not args.limit:
        print(f"confirmation: serial retry of {len(errs)} "
              f"pipeline_error clips: {errs}", flush=True)
        _init_worker()
        for cid in errs:
            work(rows_by_id[cid])
        state_p = STATE_DIR / "state.json"
        state = json.loads(state_p.read_text()) \
            if state_p.exists() else {}
        log = state.get("retry_log", [])
        log.append({"clips": errs, "unix": time.time()})
        update_state(retry_log=log)
    all_recs = [record_done(r["clip_id"]) for r in rows]
    sp = spend_of([r for r in all_recs if r])
    update_state(spend=sp, done=sum(1 for r in all_recs if r))
    print("confirmation spend:", json.dumps(sp), flush=True)
    print("confirmation run complete", flush=True)


if __name__ == "__main__":
    main()
