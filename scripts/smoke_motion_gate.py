"""Smoke test: run the motion gate over one clip and report what it selects.

Usage: python scripts/smoke_motion_gate.py <video> [threshold]
This is a plumbing check, not a benchmark. Nothing here produces numbers
for public artifacts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jaga.frames import probe_duration          # noqa: E402
from jaga.motion_gate import candidate_segments, motion_series  # noqa: E402

FPS = 5.0

def main() -> None:
    video = Path(sys.argv[1])
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    duration = probe_duration(video)
    series = motion_series(video, fps=FPS)
    segs = candidate_segments(series, FPS, threshold)
    flagged = sum(s.end_s - s.start_s for s in segs)
    print(f"video: {video.name}")
    print(f"duration: {duration:.1f}s, sampled steps: {len(series)} @ {FPS} fps")
    print(f"motion: mean {series.mean():.2f}, p90 {sorted(series)[int(len(series)*0.9)]:.2f}, max {series.max():.2f}")
    print(f"threshold {threshold}: {len(segs)} candidate segment(s), "
          f"{flagged:.1f}s flagged = {100*flagged/duration:.0f}% of the clip")
    for s in segs:
        print(f"  segment {s.start_s:5.1f}s -> {s.end_s:5.1f}s  peak {s.peak:.2f}")

if __name__ == "__main__":
    main()
