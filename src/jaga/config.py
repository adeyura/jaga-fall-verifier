"""Frozen pipeline parameters.

Everything in this file is part of the evaluation spec (SPEC.md): when the
spec freezes, these values freeze with it, and config_hash() is recorded
in the results file and the clip manifest. Changing a value after the
freeze is a spec change: a dated commit with a stated reason.

Scored runs go through the config only (gate_clip and the eval harness).
Function-level parameter overrides elsewhere in the codebase exist for
dev experimentation and must never produce a reported number.
"""
from __future__ import annotations

import hashlib
import json

GATE = {
    "sample_fps": 5.0,
    "width": 160,
    "height": 90,
    "diff_threshold": 2.0,       # mean abs gray-level diff, dev-tunable only
    "bg_threshold": 3.0,         # background-difference channel threshold
    "bg_ref_window_s": 2.0,      # rolling-reference window for the bg channel
    "min_len_s": 0.4,
    "merge_gap_s": 0.6,
    "pad_pre_s": 2.0,            # SPEC candidate window: -2 s / +4 s
    "pad_post_s": 4.0,
}

FEATURES = {
    "iou_threshold": 0.2,        # keyframe association threshold (box IoU)
    "max_missed_keyframes": 1,   # a track survives this many missed keyframes
    "stillness_window_s": 3.0,   # trailing window for the stillness measure
    "stillness_min_span_s": 2.5, # min observed span before stillness is known
    "stillness_max_gap_s": 1.0,  # max unobserved gap inside that span
    "bottom_band_frac": 0.2,     # mask rows counted as the base band
    "min_mask_area_px": 25,      # below this a mask is segmentation noise
    "min_person_area_frac": 0.01,  # a person-sized mask, as a fraction
                                 # of frame area. Measured at 320x240:
                                 # person ~5000 px (~6.5%), the persistent
                                 # ceiling fixture ~150 px (~0.2%), feet
                                 # at entry ~510 px. Dev-provisional;
                                 # the freeze re-derives it per view.
}

TIMING = {
    "decode_fps": 30.0,          # local series rate for descent timing
    "smooth_s": 0.1,             # moving-average window for the series
    "area_diff_threshold": 10.0, # gray levels: a pixel counts as changed
    "burst_high_frac": 0.5,      # burst peak, fraction of floor-to-p95 span
    "burst_low_frac": 0.2,       # hysteresis floor, same span
    "core_frac": 0.5,            # descent core: width at this fraction of
                                 # the peak's height above the floor
    "core_peak_percentile": 90.0,  # the peak the core is measured
                                 # against: a high percentile of the run,
                                 # not the max — one-step spikes at impact
                                 # otherwise shrink the core to the spike
    "min_span_abs": 0.005,       # below this p95-floor span the envelope
                                 # carries no usable signal at all
    "centroid_fill_max_gap_s": 1.0,  # diagnostics only: longest NaN gap
                                 # the centroid trace may be filled across
    "min_duration_s": 0.15,
    "max_duration_s": 3.0,
}

RULES = {
    "upright_tilt_min_deg": 55.0,   # axis tilt at/above: upright posture
    "horizontal_tilt_max_deg": 35.0,  # axis tilt at/below: horizontal
    "min_elongation": 1.2,       # below this the axis is ill-defined
    "descent_min_s": 0.4,        # SPEC: rapid descent window
    "descent_max_s": 1.0,
    "descent_vy_min_hps": 0.25,  # keyframe fallback: downward velocity
    "stillness_max_disp_h": 0.03,  # trailing stillness ceiling, frame ht
    "overlap_slack_s": 1.0,      # timing/track pairing tolerance
    "min_track_frames": 2,       # a track needs this many keyframes
    "min_phase_frames": 2,       # classified keyframes a phase needs
                                 # before it may read as satisfied
}

# Per-view rules overrides and posture models. A view is a camera
# geometry, not a dataset: side covers frontal/lateral/corner views,
# ceiling is the straight-down view. The ceiling posture model is the
# construction used for enter-and-fall ceiling clips: the
# pre-descent phase is unobservable by construction (the subject
# enters and falls within about half a second), so the rules cap at
# uncertain in this view and the adjudicator decides from frames.
# Ceiling window values were set 2026-10-27 from the full UR Fall
# cam1 diagnostics distribution on the RGB-half signal (n=27 falls
# with a detected descent of 30; cores 0.17-1.27 s, median 0.57,
# p10 0.31, p90 1.02), padded modestly at both ends. UR Fall is a
# diagnostics-only dataset in this protocol, so its full fall set is
# legitimately development data; the frozen test sets are side view
# and never touch this window.
VIEWS = {
    "side": {"posture_model": "tilt"},
    "ceiling": {"posture_model": "ceiling",
                "descent_min_s": 0.15, "descent_max_s": 1.35},
}


def config_hash() -> str:
    blob = json.dumps({"gate": GATE, "features": FEATURES, "timing": TIMING,
                       "rules": RULES, "views": VIEWS},
                      sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
