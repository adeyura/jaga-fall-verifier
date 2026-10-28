# Dev core measurements — summary

Descent core durations from the pipeline's local stages only
(motion gate + timing; no SAM, no adjudicator, no Meta API).
Measured 2026-10-28 for the pending P3 side-window amendment
decision. Measurements only; this file recommends nothing.

## Distribution of descent core durations (seconds)

Quartiles use the inclusive method. 'All measured' includes
fallback rows; 'descent-selected only' excludes them (see
the fallback caveat under Methods).

| group | n | min | Q1 | median | Q3 | max |
|---|---|---|---|---|---|---|
| upfall_adl — all measured | 9 | 0.1000 | 0.1333 | 0.2667 | 0.3000 | 0.3667 |
| upfall_adl — descent-selected only | 6 | 0.2667 | 0.2750 | 0.3000 | 0.3000 | 0.3667 |
| le2i_fall — all measured | 83 | 0.1000 | 0.5333 | 0.7333 | 0.9000 | 1.7333 |
| le2i_fall — descent-selected only | 82 | 0.2667 | 0.5333 | 0.7333 | 0.9000 | 1.7333 |

Fallback rows: upfall_adl 3/9, le2i_fall 1/83.

## In-window counts (raw float cores, as the rules stage compares them)

### Group A — UP-Fall Subject 1 ADL (hard negatives)

| window (s) | in-window | measured |
|---|---|---|
| [0.4, 1] | 0 | 9 |
| [0.2, 1] | 6 | 9 |
| [0.1, 0.8] | 8 | 9 |

### Group B — Le2i-dev falls

| window (s) | in-window | measured |
|---|---|---|
| [0.4, 1] | 63 | 83 |
| [0.2, 1] | 70 | 83 |
| [0.1, 0.8] | 58 | 83 |

## Failures and non-measured rows

- Subject1Activity8Trial1_Camera1.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity8Trial2_Camera2.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity8Trial3_Camera1.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity8Trial3_Camera2.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity11Trial1_Camera2.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity11Trial2_Camera1.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity11Trial2_Camera2.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity11Trial3_Camera1.zip (upfall_adl): status=no_interval — no timing interval found
- Subject1Activity11Trial3_Camera2.zip (upfall_adl): status=no_interval — no timing interval found
- le2i_home-01_video-16 (le2i_fall): status=no_interval — no timing interval found

## Methods

- Stages: probe_duration, gate_clip (motion gate),
  timing_from_video (local timing) — the same invocation as
  src/jaga/harness.py and scripts/measure_up_fall_s1_fall_timing.py. No other pipeline stage ran.
- The timing module decodes every clip at its own fixed
  series rate (TIMING decode_fps = 30 fps), resampling the
  container's native rate (UP-Fall assemblies 18 fps;
  Le2i 25 fps for Coffee_room_01, 24.0004 fps for Home_01
  and Home_02). fps_series and fps_native are recorded per row;
  all durations are on the 30 fps series grid (~0.033 s
  steps).
- Recorded descent: TimingResult.descent — the strongest
  interval whose core falls in the timing module's own
  selection bounds.
- Fallback caveat: when no interval qualifies but intervals
  exist, the strongest interval is recorded and the row is
  flagged fallback=yes. A fallback value is what the timing
  module reports when it fails to find a qualifying
  interval; it is not a clean descent measurement and must
  not be read as one.
- UP-Fall zips were sha256-verified against
  results/up_fall_download_manifest.csv before assembly;
  Le2i files were sha256-verified against the frozen
  split's file_sha256. Clips failing verification were not
  measured and appear above as failures.
- Dev split only (results/split_dev.csv). Subject 2 and
  the Le2i holdout room Coffee_room_02 were never read.
- Core durations are stored unrounded in the CSV
  (core_duration_s, full float repr) alongside a 2-decimal
  display column; every count in this summary uses the raw
  floats.
