"""Smoke test: run the motion gate over one clip and report what it selects.

Usage: python scripts/smoke_motion_gate.py <video>
Plumbing check only. Every line of output is prefixed so the numbers can
never be quoted downstream as a measurement.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.config import GATE, config_hash          # noqa: E402
from jaga.frames import probe_duration             # noqa: E402
from jaga.motion_gate import gate_clip             # noqa: E402

TAG = "SMOKE ONLY — NOT A RESULT"

def main() -> None:
    video = Path(sys.argv[1])
    duration = probe_duration(video)
    segs, stats = gate_clip(video, duration)
    print(f"{TAG} | config {config_hash()} | gate params {GATE}")
    print(f"{TAG} | video {video.name} duration {duration:.1f}s")
    print(f"{TAG} | segments kept {stats.segments_kept}, short runs dropped "
          f"{stats.runs_dropped_short}, zero-candidate {stats.zero_candidate}")
    print(f"{TAG} | flagged {stats.seconds_flagged:.1f}s of {duration:.1f}s")
    for s in segs:
        print(f"{TAG} |   segment {s.start_s:5.1f}s -> {s.end_s:5.1f}s peak {s.peak:.2f}")

if __name__ == "__main__":
    main()
