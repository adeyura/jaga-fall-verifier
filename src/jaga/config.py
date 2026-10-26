"""Frozen pipeline parameters.

Everything in this file is part of the evaluation spec (SPEC.md): when the
spec freezes, these values freeze with it, and config_hash() is recorded
in the results file and the clip manifest. Changing a value after the
freeze is a spec change: a dated commit with a stated reason.
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
    "min_len_s": 0.4,
    "merge_gap_s": 0.6,
    "pad_pre_s": 2.0,            # SPEC candidate window: -2 s / +4 s
    "pad_post_s": 4.0,
}


def config_hash() -> str:
    blob = json.dumps({"gate": GATE}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
