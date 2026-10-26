# Jaga

A fall-event **verifier** for families who live far apart.

Fall detectors exist. Families unplug them because they cry wolf. Jaga is the verification layer that sits behind a candidate detector: it checks possible falls, separates real events from everyday movement, and escalates only what a person needs to act on.

**Status:** prototype built during the Meta Global AI Developer Hackathon (build window Oct 26 – Nov 4, 2026 ET). It is not deployed, it does not protect anyone yet, and benchmark results on public datasets are evidence of feasibility, not of real-world performance.

## How it works

1. A cheap local motion gate (frame differencing) selects candidate segments. Most footage never goes anywhere.
2. Candidate frames are segmented with **SAM 3.1** via the Meta Model API ("person" prompt), tracked across keyframes, and reduced to mask-derived kinematics: bounding-box aspect ratio, centroid height and velocity, floor-contact area, post-event stillness.
3. A rules state machine (upright, rapid descent, horizontal, stillness) tuned for high fall recall proposes candidate events.
4. **Muse Spark** (Meta Model API) adjudicates each candidate against the hard-negative categories (fast sit-down, bend, crouch, stumble-and-recover, intentional lie-down) and returns a verdict with a rationale.
5. Verdicts map to a tiered response: urgent alert, check-now prompt, or log-only. Uncertainty escalates to a human check; it never defaults to silence.

## Evaluation

Benchmarks run on public fall datasets (UR Fall, Le2i; UP-Fall after the gate). The evaluation protocol is frozen in [SPEC.md](SPEC.md) before results exist: frozen clip manifest and dev/test split, event-level recall, per-category results, and false alarms per hour of everyday-activity footage. Every number in this README comes from the single results file produced by the harness in `results/`.

## Provenance and disclosures

- Built during the event window above. Commit history is the evidence. Anything pre-existing is itemized here: *(none yet)*.
- **AI assistance:** substantial implementation was written with an AI coding agent under the author's direction. The author designed the architecture and the evaluation methodology, reviews the code, and is responsible for every claim in this repository.
- **Clean room:** this is an independent personal project. Public datasets and published methods only. No employer code, data, prompts, labels, or internal tools are used anywhere in this repository.
- **Third-party assets:** SAM 3.1 and Muse Spark are Meta Model API services. Datasets: UR Fall, Le2i, UP-Fall (sources and terms in `scripts/`). Dataset media is **not** redistributed in this repository and does not appear in the demo video; the repo ships download scripts, a clip manifest, and checksums instead.
- **Demo footage:** any synthetic or generated footage in the demo video is captioned as such. Benchmark results are shown as charts from dataset evaluation.
- **Privacy, stated precisely:** in the design, only candidate-event frames leave the home for adjudication; continuous footage does not. Nothing is retained after adjudication except, on a verified event, a single still. This prototype processes public dataset clips only; no real home is monitored.

## Quickstart

*(one-command demo with a clearly labeled cached-results mode lands here before submission)*

## License

See [LICENSE](LICENSE).
