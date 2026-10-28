"""D1 gate run driver: the paired dev-split evaluation (SPEC D1/D3/D5).

Phases:
  main      Full pipeline over the dev split with the scored traces-only
            adjudication (D3). One record per clip yields BOTH arms:
            rules-only (rules labels alone) and full (rules + Spark).
  abc       D3 A/B/C rerun on the UP-Fall dev split: the raw-frames and
            overlay evidence forms (the traces form is the main phase).
  baselines D5 trivial baselines over the same gate: aspect-only and
            Spark-only, following scripts/run_baselines_dev.py exactly.
  analyze   Event-level scoring per the split-freeze counting
            convention, the D1 verdict, cascade metrics, discordants;
            writes the results artifacts.

Scope guard: rows come only from results/split_dev.csv; the driver
asserts split == 'dev' on every row and refuses any row naming
Subject 2 or Coffee_room_02. The test split is never opened.

Checkpointing: one JSON record per clip under cache/gate_d1/<phase>/,
written on completion; a rerun skips clips whose record exists under
the current config hash (pipeline_error records get one serial retry).
State and cumulative spend live in cache/gate_d1/state.json.
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
sys.path.insert(0, str(ROOT / "scripts"))

from jaga.config import config_hash  # noqa: E402

HELPER = (Path.home() / "workspace/custom-connectors/"
          "custom.meta-model-api/bin/meta_api.py")
STATE_DIR = ROOT / "cache" / "gate_d1"
ADJUDICATE_ON = frozenset({"fall_candidate", "uncertain"})
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


def load_dev_rows() -> list[dict]:
    rows = list(csv.DictReader((ROOT / "results" / "split_dev.csv").open()))
    for r in rows:
        assert r["split"] == "dev", f"non-dev row in dev split: {r}"
        blob = json.dumps(r).lower()
        assert "coffee_room_02" not in blob and "coffee-room-02" not in blob, r
        assert not (r["dataset"] == "up_fall" and r["subject"] == "2"), r
    assert len(rows) == 215, f"expected 215 dev rows, got {len(rows)}"
    return rows


def harness_row(row: dict) -> dict:
    """The row the harness sees. The manifest records UP-Fall view as ''
    and Le2i view as 'corner'; the rules view model for both is 'side'
    (config: side covers frontal/lateral/corner views). The mapping is
    recorded on every output record as manifest_view."""
    return {"clip_id": row["clip_id"], "label": row["label"],
            "camera": row.get("kind") or row.get("camera", ""),
            "view": "side"}


def job_order(rows: list[dict]) -> list[dict]:
    """Gate-decisive strata first: falls, then UP-Fall ADL (the labeled
    hard negatives), then the Le2i ADL pool."""
    def key(r):
        if r["label"] == "fall":
            return (0, 0 if r["dataset"] == "up_fall" else 1)
        return (1, 0 if r["dataset"] == "up_fall" else 1)
    return sorted(rows, key=key)


def rec_path(phase: str, clip_id: str, form: str = "") -> Path:
    d = STATE_DIR / phase / form if form else STATE_DIR / phase
    d.mkdir(parents=True, exist_ok=True)
    return d / (clip_id.replace("/", "_") + ".json")


def record_done(phase: str, clip_id: str, form: str = "") -> dict | None:
    p = rec_path(phase, clip_id, form)
    if not p.exists():
        return None
    try:
        rec = json.loads(p.read_text())
    except Exception:
        return None
    if rec.get("config_hash") != EXPECTED_HASH:
        return None
    return rec


# ---------------------------------------------------------------- workers

_RUNNER = None
_TRANSPORTS = None


def _init_worker(keep_rasters: bool):
    global _RUNNER, _TRANSPORTS
    from jaga.sam_runner import SamRunner, helper_transport
    from run_eval_dev import vm_transport
    _RUNNER = SamRunner(ROOT / "cache", helper_transport(HELPER),
                        keep_rasters=keep_rasters)
    _TRANSPORTS = vm_transport


def _base_meta(row: dict) -> dict:
    return {"dataset": row["dataset"], "event_id": event_id(row),
            "manifest_view": row.get("view", ""),
            "config_hash": config_hash()}


def work_main(row: dict) -> dict:
    from jaga.harness import run_clip
    meta = _base_meta(row)
    try:
        rec = run_clip(video_path(row), harness_row(row), _RUNNER,
                       ROOT / "cache", adjudicate_labels=ADJUDICATE_ON,
                       transport=_TRANSPORTS, image_picker=None,
                       evidence_form="none")
    except Exception as e:  # run_clip contains stage failures; be safe
        rec = {"clip_id": row["clip_id"], "label": row["label"],
               "outcome": "pipeline_error",
               "error": f"driver-level: {type(e).__name__}: {e}",
               "segments": []}
    rec.update(meta)
    p = rec_path("main", row["clip_id"])
    p.write_text(json.dumps(rec, indent=1))
    return rec


def work_abc(job: tuple[dict, str]) -> dict:
    from jaga.harness import overlay_picker, run_clip
    from run_eval_dev import pick_raw_frames
    row, form = job
    picker = overlay_picker if form == "overlay" else pick_raw_frames
    meta = _base_meta(row)
    try:
        rec = run_clip(video_path(row), harness_row(row), _RUNNER,
                       ROOT / "cache", adjudicate_labels=ADJUDICATE_ON,
                       transport=_TRANSPORTS, image_picker=picker,
                       evidence_form=form)
    except Exception as e:
        rec = {"clip_id": row["clip_id"], "label": row["label"],
               "outcome": "pipeline_error",
               "error": f"driver-level: {type(e).__name__}: {e}",
               "segments": []}
    rec.update(meta)
    rec["abc_form"] = form
    p = rec_path("abc", row["clip_id"], form)
    p.write_text(json.dumps(rec, indent=1))
    return rec


def work_baseline(row: dict) -> dict:
    """Mirrors scripts/run_baselines_dev.py: first gated segment only,
    aspect threshold rule on the SAM run, Spark-only adjudication of a
    neutral evidence pack with overlay images."""
    from jaga.adjudicator import adjudicate
    from jaga.frames import probe_duration, sample_frames
    from jaga.harness import overlay_picker
    from jaga.motion_gate import gate_clip
    from jaga.timing import timing_from_video
    from run_baselines_dev import aspect_only, neutral_traces
    rec = {"clip_id": row["clip_id"], "label": row["label"],
           "aspect_only": None, "spark_only": None,
           **_base_meta(row)}
    video = video_path(row)
    try:
        duration = probe_duration(video)
        rec["duration_s"] = round(duration, 2)
        segments, _gs = gate_clip(video, duration)
        rec["n_segments"] = len(segments)
        if segments:
            seg = segments[0]
            frames_dir = ROOT / "cache" / "keyframes" / row["clip_id"]
            all_frames = sample_frames(video, frames_dir, 2.0)
            window = [(t, p) for t, p in all_frames
                      if seg.start_s - 1e-9 <= t <= seg.end_s + 1e-9]
            rec["window_keyframes"] = len(window)
            if len(window) >= 2:
                run = _RUNNER.run_keyframes(row["clip_id"], window)
                timing = timing_from_video(video)
                rec["aspect_only"] = aspect_only(run)
                images, labels = overlay_picker(window, run)
                adj = adjudicate(_TRANSPORTS,
                                 neutral_traces(row["clip_id"], run, timing),
                                 images, image_labels=labels)
                rec["spark_only"] = {
                    "usable": adj.usable, "verdict": adj.verdict,
                    "confidence": adj.confidence, "error": adj.error,
                    "usage": adj.usage}
    except Exception as e:
        rec["baseline_error"] = f"{type(e).__name__}: {e}"
    p = rec_path("baselines", row["clip_id"])
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
    state["updated_unix"] = time.time()
    p.write_text(json.dumps(state, indent=1))


def spend_of(records: list[dict]) -> dict:
    sam_usd, sam_images, sam_unknown = 0.0, 0, 0
    adj_n, adj_usable, tok_in, tok_out = 0, 0, 0, 0
    for rec in records:
        for seg in rec.get("segments", []):
            run = seg.get("run") or {}
            if run:
                if run.get("est_cost_usd") is None:
                    sam_unknown += 1
                else:
                    sam_usd += run["est_cost_usd"]
                sam_images += run.get("images_billed") or 0
            a = seg.get("adjudication")
            if a is not None:
                adj_n += 1
                adj_usable += 1 if a.get("usable") else 0
                u = a.get("usage") or {}
                tok_in += u.get("prompt_tokens", 0) or 0
                tok_out += u.get("completion_tokens", 0) or 0
        so = rec.get("spark_only")
        if so:
            adj_n += 1
            adj_usable += 1 if so.get("usable") else 0
            u = so.get("usage") or {}
            tok_in += u.get("prompt_tokens", 0) or 0
            tok_out += u.get("completion_tokens", 0) or 0
    return {"sam_est_usd": round(sam_usd, 4), "sam_images_billed": sam_images,
            "sam_runs_cost_unknown": sam_unknown,
            "adjudications": adj_n, "adjudications_usable": adj_usable,
            "adj_prompt_tokens": tok_in, "adj_completion_tokens": tok_out}


def run_pool(phase: str, jobs: list, worker, workers: int,
             keep_rasters: bool, form: str = ""):
    done = []
    t0 = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers,
                             initializer=_init_worker,
                             initargs=(keep_rasters,)) as ex:
        futs = {ex.submit(worker, j): j for j in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            done.append(rec)
            if i % 10 == 0 or i == len(jobs):
                el = time.monotonic() - t0
                print(f"[{phase}{('/' + form) if form else ''}] "
                      f"{i}/{len(jobs)} clips, {el:.0f}s elapsed, "
                      f"{el / i:.1f}s/clip", flush=True)
                update_state(**{f"{phase}{('_'+form) if form else ''}"
                                "_progress": f"{i}/{len(jobs)}"})
    return done


def phase_main(workers: int, limit: int | None):
    rows = job_order(load_dev_rows())
    todo = []
    for r in rows:
        rec = record_done("main", r["clip_id"])
        if rec is None or rec.get("outcome") == "pipeline_error":
            todo.append(r)
    if limit:
        todo = todo[:limit]
    print(f"main: {len(todo)} clips to run "
          f"({215 - len(todo)} already recorded)", flush=True)
    if todo:
        run_pool("main", todo, work_main, workers, keep_rasters=False)
    # serial retry pass for pipeline errors (cache races, transients)
    rows_by_id = {r["clip_id"]: r for r in rows}
    errs = [cid for cid in rows_by_id
            if (record_done("main", cid) or {}).get("outcome")
            == "pipeline_error"]
    if errs and not limit:
        print(f"main: serial retry of {len(errs)} pipeline_error clips",
              flush=True)
        _init_worker(False)
        for cid in errs:
            work_main(rows_by_id[cid])
    all_recs = [record_done("main", r["clip_id"]) for r in rows]
    update_state(main_spend=spend_of([r for r in all_recs if r]),
                 main_done=sum(1 for r in all_recs if r))
    print("main spend:", json.dumps(spend_of([r for r in all_recs if r])),
          flush=True)


def phase_abc(workers: int, limit: int | None):
    rows = [r for r in job_order(load_dev_rows())
            if r["dataset"] == "up_fall"]
    for form in ("raw", "overlay"):
        todo = [r for r in rows
                if record_done("abc", r["clip_id"], form) is None
                or (record_done("abc", r["clip_id"], form) or {})
                .get("outcome") == "pipeline_error"]
        if limit:
            todo = todo[:limit]
        print(f"abc/{form}: {len(todo)} clips to run", flush=True)
        if todo:
            run_pool("abc", [(r, form) for r in todo], work_abc, workers,
                     keep_rasters=True, form=form)
    all_recs = []
    for form in ("raw", "overlay"):
        all_recs += [record_done("abc", r["clip_id"], form)
                     for r in rows]
    update_state(abc_spend=spend_of([r for r in all_recs if r]))


def phase_baselines(workers: int, limit: int | None):
    rows = job_order(load_dev_rows())
    todo = [r for r in rows
            if record_done("baselines", r["clip_id"]) is None
            or (record_done("baselines", r["clip_id"]) or {})
            .get("baseline_error")]
    if limit:
        todo = todo[:limit]
    print(f"baselines: {len(todo)} clips to run", flush=True)
    if todo:
        run_pool("baselines", todo, work_baseline, workers,
                 keep_rasters=True)
    rows_by_id = {r["clip_id"]: r for r in rows}
    errs = [cid for cid in rows_by_id
            if (record_done("baselines", cid) or {}).get("baseline_error")]
    if errs and not limit:
        print(f"baselines: serial retry of {len(errs)} error clips",
              flush=True)
        _init_worker(True)
        for cid in errs:
            work_baseline(rows_by_id[cid])
    all_recs = [record_done("baselines", r["clip_id"]) for r in rows]
    update_state(baselines_spend=spend_of([r for r in all_recs if r]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["main", "abc", "baselines"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    h = config_hash()
    if h != EXPECTED_HASH:
        print(f"ABORT: config_hash() = {h}, expected {EXPECTED_HASH}")
        sys.exit(2)
    update_state(started_phase=args.phase)
    {"main": phase_main, "abc": phase_abc,
     "baselines": phase_baselines}[args.phase](args.workers, args.limit)
    print(f"phase {args.phase} complete", flush=True)
