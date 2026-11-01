# Jaga

A fall-event **verifier** for families who live far apart.

Fall detectors exist. Families unplug them because they cry wolf. Jaga
is the verification layer behind a candidate detector: it checks
possible falls against segmentation evidence and motion timing,
separates real events from everyday movement, and escalates only what
a person needs to act on. It was designed for one household: the
author's parents in Indonesia, who are usually home together; the
risk window is when one of them is out and the other is home alone.
If one of them falls while the other is out, the risk is not only the
fall. The risk is that nobody knows for hours.

**Status:** a research prototype built during the Meta Global AI
Developer Hackathon (build window Oct 26 – Nov 4, 2026 ET). It is not
deployed, it does not protect anyone yet, and every number below is a
benchmark result on public datasets: evidence of feasibility, not of
real-world performance.

**Contents:** [Results at a glance](#results-at-a-glance) ·
[The shipped system](#the-shipped-system) · [Quickstart](#quickstart) ·
[Evaluation](#evaluation) ·
[Path into the home (future work)](#path-into-the-home-future-work) ·
[Datasets, citations, licenses](#datasets-citations-licenses) ·
[Repository map](#repository-map) ·
[Provenance and disclosures](#provenance-and-disclosures) ·
[License](#license)

## Results at a glance

From the frozen protocol: one confirmation run on the frozen test
split, and the pre-registered gate that ran before it. The full
record, with dev numbers and strata, is under
[Evaluation](#evaluation).

| | |
|---|---|
| Falls routed to a human (confirmed or escalated), frozen test | **19/27** (70.4%, 95% CI 51.5–84.1) |
| Definitive-alert precision | **7/7** (95% CI 0.646–1.000), against 24 of 44 events escalated for human review |
| Confirmed false alarms | **0** across 17 everyday-activity events (0 definitive false-positive confirmations in 0.18 h of ADL clips; exact Poisson 95% CI for the rate 0–20.5/h) |
| The experiment that failed | The pre-registered gate for the Muse Spark adjudicator **failed**, and the component was removed; reported in full under Evaluation |

![SAM 3.1 mask overlays for one dev-set fall event: the person upright before the descent (left) and horizontal after it (right)](docs/assets/sam_mask_worked_example.png)

*The evidence the rules read, for one dev-set event
(`le2i_coffee-room-01_video-02`, a staged fall from the public Le2i
dataset; the performer is a dataset volunteer, not family). Left:
keyframe at 7.0 s, before the descent; the mask's axis tilt reads
85°, upright. Right: keyframe at 9.0 s, after the descent; the same
person's mask reads 33.5°, horizontal. Both panels are rendered by
the shipped overlay code (`src/jaga/overlays.py`) from the SAM 3.1
output recorded for this event in the dev-set gate run, over the
pipeline's privacy-blurred background. Full trace:
[the worked example](results/sam_ablation_dev_2026-11-01/worked_example.md).*

![The same event over time: mask axis tilt and box aspect at each recorded keyframe, with the descent core and the stillness window marked](docs/assets/worked_example_trace.png)

*The same event, read over time. Each point is one keyframe from the
record the rules scored: the mask's axis tilt (left axis) and
bounding-box aspect (right axis), with the frozen rules' posture
thresholds dashed, the descent core the timing stage measured shaded
first, and the stillness window that follows it shaded second. Every
keyframe before the descent reads upright and every keyframe after
it reads horizontal, which is the temporal pattern the shipped rules
require. Rendered by `scripts/render_worked_example_trace.py` from
the per-clip record of the dev-set gate run; the lines join recorded
points and add no values of their own. The performer is a dataset
volunteer, not family.*

## The shipped system

```
motion gate -> SAM 3.1 evidence -> timing / features -> rules -> alert ladder
```

To our knowledge, Jaga is the first published fall-verification
system to use SAM segmentation at inference time as an interpretable
evidence layer. The claim is narrow, and it is not a claim to be the
first fall detector or the first verified alert (systems that
verify alerts already exist). What is
claimed is the composition: verification as the primary design
object, in a private home, with explicit rules over segmentation
evidence, a family responder, an open method, and a published,
falsifiable evaluation that includes the experiment that failed. The
contribution is that composition and its evaluation posture, not any
single component.

1. **Motion gate (local).** Frame differencing selects candidate
   segments. In a home, this gate is what keeps most footage from
   ever leaving the room. In this evaluation it filtered little: the
   clips are staged events, and nearly every clip passed the gate and
   was segmented (113 of 114 fall clips reached the SAM stage on dev;
   42 of 42 on the confirmation split).
2. **SAM 3.1 evidence.** Candidate keyframes (2 fps) are segmented
   with SAM 3.1 via the Meta Model API ("person" prompt) and reduced
   to mask-derived kinematics: bounding-box aspect and elongation,
   axis tilt, centroid path, floor proximity, post-event stillness.
   SAM is a segmentation-derived, interpretable evidence layer: it
   outlines the person in each keyframe. The judgment about the fall
   is made by timing and rules over those outlines, never by SAM
   itself. There is no pose estimation anywhere in this system; the
   honest label is person segmentation plus mask kinematics.
3. **Timing and rules.** Descent timing is measured locally from
   the motion signal, on a fixed 30.0 fps analysis series (config
   TIMING, decode_fps = 30.0). The source clips run at 18 fps
   (UP-Fall) and 25 fps (Le2i), and timing is never derived from the
   2 fps segmentation keyframes. Timing features are expressed in
   decoder time under a fixed 30 fps assumption; native source frame
   rates were not used to rescale them. A frozen rules state machine
   (upright → rapid descent → horizontal → stillness, with a safeguard
   that escalates ambiguous evidence instead of clearing it) issues
   the verdict.
4. **Tiered alert ladder.** Verdicts map to `urgent`,
   `check_now`, or `no_immediate_alert`, with acknowledgement and
   escalation if nobody responds. Uncertainty in any segment that
   reaches the rules escalates to a human check; inside the ladder,
   nothing defaults to silence. The limit is upstream: a fall the
   motion gate never selects produces no segment and no alert, which
   is silence by another name. That happened once on the dev split
   (le2i_home-01_video-16, a slow, low descent from a crouch in a dim
   room), and it is counted in the gate numbers below, not hidden by
   this sentence.

   The mapping the ladder applies, exactly as `tier_for` in
   `src/jaga/alerts.py` computes it for the shipped configuration:

   | Rules outcome for the segment | Tier |
   |---|---|
   | Fall candidate that stands (a confirmed fall) | `urgent` |
   | Uncertain, or no evidence either way | `check_now` |
   | Negative (no fall pattern found) | `no_immediate_alert` |
   | A pipeline error or a failed verification, on any outcome above | raised to at least `check_now` |

   An alert goes to the first recipient on the ladder. If nobody
   acknowledges it within the acknowledgement window (900 s by
   default), it escalates to the next recipient; acknowledgement
   stops the escalation.

**No video archive, by design.** The system keeps verdicts, traces,
and measurements, not footage. That sentence describes the design.
The evaluation harness behind this prototype does keep a local
working cache on the author's machine: the keyframes it extracted
and the SAM response streams it received, about 1.6 GB in a
git-ignored directory that is never committed. The cache exists so
that runs can be inspected, audited, and replayed; it is not footage
kept for later viewing. In this prototype, only public dataset clips
were ever processed; no real home is monitored.

An earlier design gave a Muse Spark adjudicator the final say over
exactly the segments the rules had already flagged: fall candidates
and uncertain segments. It never saw anything else. A pre-registered
gate tested whether it earned that place.
It did not, and it was removed from the decision path. That experiment
is reported in full under [Evaluation](#evaluation), because it is
part of what this project found.

## Quickstart

### No API key: run the pinned example

The install step needs the network once. After that, the example
itself runs fully offline in about two seconds.

One real scored clip's SAM output is pinned under `examples/`, so the
pipeline's downstream stages run live on real evidence with no key
and no network:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python examples/run_example.py
```

You should see the frozen rules engine return `fall_candidate` for a
staged UP-Fall fall, the evidence trace it produced, and the alert
tier (`urgent`), with the replay verifying its own verdict against
the recorded one. `examples/upfall_s1_a1t1_cam1/expected_output.txt`
is the verified output to diff against, and `examples/README.md`
states exactly which stages run live and which are replayed from the
run record (the two that read the video file itself: dataset media
never enters this repository).

### With Meta Model API access: run a fresh clip

The pipeline takes its SAM transport as an injected callable
(`src/jaga/sam_runner.py`), so it is not tied to one machine's
credentials. On the author's machine the transport is the Meta Model
API connector helper; with your own access, wire an equivalent
callable and run one clip end to end:

```bash
python3 scripts/download_ur_fall.py          # or the UP-Fall scripts below
python3 scripts/smoke_up_fall_clip.py <clip.mp4> <clip_id>
```

UP-Fall arrives as per-trial PNG sequences: fetch with
`scripts/download_up_fall.py`, then assemble clips with
`scripts/assemble_up_fall_clips.py` (ffmpeg, native 18 fps). The full
scored runs are `scripts/run_gate_d1_dev.py` and
`scripts/run_confirmation.py`, driven by the frozen manifests in
`results/`.

## Evaluation

The protocol was frozen in [SPEC.md](SPEC.md) **before** results
existed: a dev split for all iteration, a frozen test split that
receives exactly one confirmation run, event-level scoring (UP-Fall's
two camera views of one trial count as one event), Wilson confidence
intervals on every proportion, and per-dataset strata that are never
pooled into a single headline. Dev and confirmation numbers are
labeled and never pooled with each other.

### The D1 gate: whether the LLM adjudicator earned its place

Design, registered in advance: keep Muse Spark as adjudicator only
if, against the rules-only arm on the dev split (215 clips, 191
events), it met all four criteria. Result:

| Criterion | Required | Measured | Result |
|---|---|---|---|
| 1. Safety veto: additional missed falls vs rules-only | 0 | 0 | PASS |
| 2a. Hard-negative FA reduction, relative | >= 40% | 0.0% (4 -> 4) | FAIL |
| 2b. Hard-negative FA reduction, absolute | >= 3 | 0 | FAIL |
| 3. Usable adjudicator verdicts | >= 95% | 141/142 = 0.993 [0.961, 0.999] | PASS |

**Verdict: FAIL.** The pivot to the rules-primary configuration above
was executed on that verdict, without renegotiating the rule, and the
verdict stands as recorded. Both arms routed 71/99 fall events to a
human (confirmed or escalated) (recall 0.717 [0.622, 0.796]);
rules-only precision was 0.867,
the full arm's 0.852. For scale: a crude aspect-ratio baseline calls
89/99 falls and 87/92 everyday activities "fall"; Spark alone,
without the pipeline, confirms 49/99 falls with 7 false alarms.

The verdict needs its second level stated as plainly as the first,
because the two are different claims:

- The deciding criterion (2a/2b) was measured against a dev negative
  pool whose only four counted "false alarms" were, on a post-hoc
  visual audit (next section), real falls whose ADL labels **our dev
  manifest inferred** from room layout: the source archives for those
  rooms ship no annotation files. So the adjudicator's value on the
  false-alarm axis is **unmeasured by this gate, not refuted**: on a
  correctly labeled pool there were essentially no rules false alarms
  for anyone to clear (on the UP-Fall stratum, both arms produced
  zero).
- It was removed anyway. The burden of proof was the project's own,
  set in advance, and it was unmet: Spark demonstrated no measured
  benefit on any axis: identical missed falls, no clearances, and
  the weak standalone numbers above.
- The pool was also thin, and that is a design limitation of the gate
  itself, stated unprompted: rules-only produced only 4 false alarms,
  so the >= 3 absolute criterion always rested on 2–3 clips.

**The verdict in the two-level form this project uses for it:
procedurally genuine FAIL; substantively indeterminate on
criterion 2.** The adjudicator had to prove benefit. Indeterminate
means unproven; unproven means removed. The full run record is
`results/gate_d1_dev_summary.md`; the per-event results are
`results/gate_d1_dev_results.csv`.

In plain terms: the test was run fairly and the component failed
it. Two dataset subsets turned out to have no labels, so that one
criterion cannot be re-judged either way, and the component stays
out because the burden of proof was on it.

### Dataset audit: Le2i label provenance (post-hoc, dev only)

After the gate, two auditors independently extracted frames from the
dev split's discordant cases, each working from their own frame
sheets (the second without reading the first's findings), to check
the labels behind the scores. Method and limits: dev data only,
visual judgment against the dataset's own fall signature (rapid
descent onto the pre-positioned crash mat, then sustained lying), and
**no score and no verdict was changed by anything found**.

Scope, stated as what it is: the audit covered 16 dev events, chosen
because they were discordant: the 4 counted false alarms, the 1
gate-missed fall, a 6-event sample of falls both arms cleared, and
the 5 events the two arms disagreed on. The judgments were 11
label-supported, 5 label-doubtful, and 0 cannot-tell. It is a sample
of the hard cases, not a re-annotation of the dev split, and no
number in this repository is recomputed from it.

The provenance fact: in the Le2i archives as shipped, per-video
annotation files exist for three of the five room groups:
Coffee_room_01 ships 48 annotation files, Home_01 ships 30, and
Home_02 ships 30. The Lecture_room and Office archives ship none
(0 and 0). Every Lecture/Office clip's "daily activity" label in our
dev manifest was therefore an inference from the room's role, not an
annotation.

Findings, scoped to that stratum:

- All 4 of the gate's counted false alarms (Lecture videos 02 and
  03, Office videos 06 and 13) visibly show staged falls onto the
  crash mat, ending with the actor lying motionless. 4 of 4.
- One reverse discrepancy in the annotated stratum: Coffee_room_01
  video 30 carries an annotated fall interval (frames 80–104), and
  the footage inside it shows a controlled sit onto the mat edge
  followed by kneeling, no fall.

Both auditors agreed on all five clips. The reports are
`results/gate_d1_visual_audit.md` and
`results/gate_d1_visual_reaudit.md`. The confirmation set below does
not contain the affected stratum: its Le2i half is the annotated
Coffee_room_02, and its UP-Fall labels come from the recording
protocol's activity IDs.

Label provenance, in one place: the gate's dev labels for the
Lecture_room and Office subsets rest on archives that ship zero
annotation files, so those everyday-activity labels were inferred
from room role, and all 4 of the gate's counted false alarms come
from those subsets and are label-doubtful (the audit found staged
falls in all 4). The confirmation run's Le2i half, Coffee_room_02,
is not one of the zero-annotation subsets: its archive ships
per-video annotation files, and the clip manifest
(`results/le2i_manifest.csv`) ties each clip to its annotation
file. The frozen test was run once, with no tuning; nothing in it
was used to revise the pipeline after the run.

### Confirmation run (frozen test split, one run, shipped configuration)

68 clips / 44 events: UP-Fall Subject 2 plus the Le2i Coffee_room_02
holdout, run once under the same config hash
(`6d7c03257b12ab00`), no tuning. The 68 clips are the 44 scored
events: UP-Fall Subject 2 contributes 48 clips as 24 events (a
trial's two camera views count as one event), and Coffee_room_02
contributes 20 clips as 20 events. Every interval in this section
treats the event, not the clip, as the independent unit:

| Stratum | Falls routed to a human (confirmed or escalated) | False alarms | Definitive-alert precision | Escalation |
|---|---|---|---|---|
| Overall (44 events) | 19/27 = 0.704 [0.515, 0.841] | 0/17 | 7/7 = 1.000 [0.646, 1.000] | 24/44 = 0.545 [0.401, 0.683] |
| UP-Fall Subject 2 | 11/15 = 0.733 [0.480, 0.891] | 0/9 | 5/5 = 1.000 [0.566, 1.000] | 11/24 = 0.458 |
| Le2i Coffee_room_02 | 8/12 = 0.667 [0.391, 0.862] | 0/8 | 2/2 = 1.000 [0.342, 1.000] | 13/20 = 0.650 |

Of the 27 falls: 7 confirmed, 12 escalated, 8 cleared; none was lost
at the motion gate (gate recall 42/42 = 1.000). The burden side of
the same run: of the 17 everyday-activity events, 0 were confirmed
as falls, 12 were escalated to a human check, 4 were cleared, and 1
was missed at the motion gate. "Routed to a human" therefore covers
19 falls and 12 non-falls alike; the escalation count is the
workload, and it is stated with the result, not under it.
Definitive-alert precision was 7/7 (95% CI 0.646–1.000), against 24
of 44 events escalated for human review. False alarms: 0 definitive
false-positive confirmations in 0.18 h of ADL clips (exact Poisson
95% CI for the rate: 0–20.5/h; the exposure is far too short to
estimate an operational false-alarm rate). With zero observed across
the 17 everyday-activity events, the 95% upper bound is roughly 18%
per event. SAM: 1,524 keyframes, 14 empty (0.9%), $3.72 of API
spend. Full record: `results/confirmation_summary.md` and
`results/confirmation_results.csv`.

After the submission, a replication set held aside (UP-Fall
Subjects 3, 4, and 5, in neither split) will be run once with the
frozen pipeline and published whatever the result. The
pre-registration is `results/replication_addendum.md`, with its
file hashes published in advance in
`results/sealed_files_manifest.sha256`. The seal is a commitment
device, not verifiable proof.

### Supplementary analysis, post-hoc (2026-11-01): removing the SAM channels on the development set

This subsection reports a post-hoc supplementary analysis, defined
and run on 2026-11-01, after the confirmation run. It is not
pre-registered, and it is not a confirmation result. It was run on
the dev split, which is the design and tuning set, so absolute dev
numbers are optimistic for both arms; only the within-dev
comparison is informative. The D1 gate above could not measure the
effect of the SAM channels: it compared rules+SAM against
rules+SAM+LLM, so SAM evidence was present in both arms. This
analysis asks what changes when the SAM channels are removed.

The no-SAM arm uses identical rules, thresholds, timing, and
scoring. The SAM-derived phases (pre/post posture, keyframe-fallback
descent) are treated as evidence-absent, because no motion-signal
equivalent exists; stillness is replaced by a motion-signal
equivalent. Note what the arm removes: not SAM segmentation
evidence alone, but SAM-derived evidence together with the
SAM-dependent track logic in this pipeline (track-span windows and
the multi-track verdict merge); every delta below is attributable
to that bundle. The full definition, the stillness amendment,
per-event dispositions, and the joined comparison are preserved in
`results/sam_ablation_dev_2026-11-01/`.

What is robust across all three motion-stillness readings (v1, the
definition as originally written; v2a, isolating a window-anchor
correction; v2, the arm of record):

- Falls confirmed fall 26/99 → 0 under every reading. That is by
  construction: confirmation requires both SAM posture phases, and
  the no-SAM arm has none. Read it as what confirmation costs, not
  as a tuning result.
- The shipped joint operating point is unreachable under every
  motion-only operationalization tried. The shipped arm holds falls
  not-missed at 0.717 while clearing 36/92 everyday-activity
  events. The motion readings either clear most falls (not-missed
  0.222 under v1, 0.303 under v2a) or escalate essentially
  everything (0.990 under v2, with 92/92 everyday-activity events
  escalated). Falls not-missed and the escalation margin swing with
  the stillness construction, so they are reported only as that
  three-reading range, never as a single point.
- ADL false alarms (confirmed) fall 4/92 → 0 in all readings, with
  the trade-off stated beside it: the shipped arm clears 36/92
  everyday-activity events; the motion readings clear 70 (v1), 64
  (v2a), or 0 (v2).

By the shipped rules' structure, the only veto available on a slow
descent is the SAM posture phase, and the only stillness test reads
the SAM mask centroid; the attribution of the shipped clearances to
those channels is design inference from the rule structure, not a
tabulated finding of this comparison, whose tables count outcomes,
not phases. One event is traced end to end in the package
(`worked_example.md` in the directory above): a Le2i
Coffee_room_01 fall where both arms find the identical 0.57 s
motion descent window; without both SAM posture phases the event
caps at uncertain and escalates, and with them it confirms.

The frozen test was not touched by this analysis, and no headline
number changes. Zero SAM calls were made: the shipped side is the
gate's recorded output.

### Limitations, beside the numbers

- The falls in these datasets are staged, performed by young actors
  in lab rooms. Dataset performance is not deployment performance,
  and nothing here is a deployment claim.
- The system's operating cost is escalation: about half of all events
  (54.5% on confirmation) are handed to a human. That is the
  deliberate price of never clearing ambiguous evidence, and it is
  a real workload, not a footnote.
- The no-video-archive design has a cost: a disputed alert can
  never be reviewed after the fact, because no video is retained.
- 8 of 27 confirmation falls were cleared by the rules. Those clips
  were never visually audited: the audit covered dev cases only, and
  the confirmation split was opened only by the run itself. No miss
  mechanics are claimed for the confirmation misses.
- The dev misses that were audited fail in recognizable ways:
  descents staged through kneeling or sitting intermediates,
  hand-braked forward falls, rotating or leg-swing descents, landings
  cropped at the frame edge or split between mat and floor, and one
  slow, low descent in a dim room that the motion gate never
  selected.
- Hard-negative depth is thin: UP-Fall provides 3 events per everyday
  activity per split, against a target of ~12 per category.
  Stumble-and-recover and crouch do not exist as labeled categories
  in either headline dataset; the shortfall is reported, not papered
  over.
- Le2i is room×class confounded in dev (the audit section above), and
  the confirmation bounds generalization rather than establishing it:
  one UP-Fall subject, one Le2i room.
- Processing latency in the evaluation environment was a median of
  ~46 s per clip. This is an offline evaluation prototype.

Jaga was built for one house: my parents', in Indonesia. The
situation it was built for is not rare, and the reason is structural,
not statistical. Two people live together and are each other's
witness for most of the day. The dangerous window opens when one of
them goes out and the other is home alone, with nobody positioned to
notice for hours. The adult children live far away, in other cities
and other countries: close enough to coordinate, too far away to
open a door. Every house shaped like that has the same window. Jaga
was designed for that house, and for every house shaped like it.

## Path into the home (future work)

Jaga today is an evaluated pipeline on public datasets, plus a demo harness. It runs on recorded clips, not in anyone's house. This section describes what a first real pilot would look like if the family ever agrees to one, and what would have to be true before it could be trusted. Nothing here exists yet.

### The first pilot, as currently imagined

Two fixed cameras, and only two:

- **The family room**, mounted high in a corner. This is where the day is spent, where naps happen, and where an ordinary fall is most likely to be seen.
- **The corridor by the bathroom door.** The bathroom itself is where falls concentrate, and it will never hold a camera. The corridor camera sees someone enter, and how long they stay. A long dwell behind that door is a check-now signal on its own, and it costs no segmentation calls.

The **bathroom interior is permanently excluded**, by dignity, not by oversight. So are the bedrooms. That leaves real gaps, and they should be stated plainly:

- The night path from bedroom to bathroom crosses no covered room. A fall there is invisible to this setup.
- Coverage means living areas only. Anyone describing the system as watching the house is overstating it.
- Furniture occludes. A person who goes down behind a sofa may leave the frame or be partly hidden, and "person present, now vanished from the frame and not seen leaving" has to be treated as a signal in itself, not as the person leaving.

### The edge box

A small fanless computer in the house (N100 class, local storage, a DC uninterruptible power supply and surge protection, because heat and power cuts are normal) would run the same pipeline that was evaluated: the same code, stages, and rules, unmodified. The one thing the shadow period below adjusts is the threshold values in its config, fitted to that house. That is calibration of a deployment, and it means the measured dataset numbers are the pilot's starting point, not a promise about a recalibrated house. Cloud SAM would be retained on purpose. The measured numbers belong to that exact pipeline. Swapping in a local model to save money or latency would produce a different system whose recall and false-alarm behavior nobody has measured.

The camera feed would be held in a short rolling buffer on the box. That buffer is working memory: it exists so the pipeline can look at the seconds around a candidate event, and it is continuously overwritten. It is not an archive, no footage is kept for later viewing, and there is no playback feature.

### When the connection drops

The house connection will drop. In degraded mode the box falls back to local motion heuristics only. That fallback may raise a check-now. It may never raise urgent, because the evidence behind an urgent alert is exactly what the connection carries. And it may never silently clear an event: an event the degraded system cannot judge stays open until full processing resumes or a human closes it.

A heartbeat runs the other way. The box reports in at a fixed interval; a missed heartbeat is itself an alert to the family. A system that died quietly while everyone believed it was watching is worse than no system, so the design treats silence as a failure to report, never as "all clear."

### Who gets alerted, and what an answer means

Responder order is by distance, not by closeness. The nearest able person, a neighbor or relative who can be at the door in minutes and get in, receives the physical alert first. The son in Japan receives awareness and escalation in parallel and administers the system, but he is never the first responder; he cannot open a door from Tokyo.

The channel is WhatsApp, because that is what the household already uses. An alert leads with the decision-relevant facts: down, and has not moved for N minutes, which room, what time. Not a verdict word.

Acknowledgement is defined narrowly: it means "I am acting," and it does not end anything. Every alert also needs a resolution state, set when someone has actually reached the person and can say what they found. Without that, one tap from a phone in Japan could silence the ladder while nobody has moved. If the first responder does not acknowledge inside the window, the ladder escalates to the next person, and the last step is a voice call.

### Shadow calibration, per home

Before any alert reaches the family, the system would run in shadow for one to two weeks in that specific house: full processing, alerts delivered to the son only. This is not a formality. Floor life breaks the assumptions baked into dataset-trained thresholds. People eat sitting on the floor. They rest on the floor. Prayer involves prostration five times a day, which to a posture pipeline looks a great deal like a collapse followed by stillness. A system that cannot tell sujud from a fall will train the family to ignore it within days. The shadow period exists to measure that home's ordinary floor behavior and set its thresholds against it, and to count what the junk rate would have been before anyone had to live with it.

### Arming only the window that matters

Full verification is armed only when exactly one person is in the frame: the one-out, one-home-alone window the project was built for. When both parents are in frame, there is a witness in the room. Those events are logged, not alerted. This also keeps the alert burden honest: the system interrupts people for the situation it exists for, not for every ambiguous moment in a shared house.

### Cost, in round numbers

Order of magnitude only: roughly $500 to install (two cameras, the edge box, power backup), roughly $100 a month to run. The governing cost is not bandwidth or storage; it is the API duty cycle. Ungated, even a sparse sampling rate of one frame every four seconds across the covered rooms would mean on the order of 20,000 segmentation calls a day, and keyframing at the evaluation's 2 fps rate would mean roughly 173,000 calls per room per day. The local motion pre-filter exists to cut that to candidate events only, a few hundred to roughly a thousand calls a day, and that ratio is the number that decides whether the monthly cost holds.

### How a pilot would be judged

The success criteria would be written down and fixed before the pilot starts, in the same spirit as the evaluation protocol:

- **Burden:** urgent false alarms at most one per week after the shadow period; check-now at most about three per day, with at least 90% acknowledged within 30 minutes.

The escalation budget is a design parameter, fixed here in advance rather than discovered in use: at most one urgent false alarm per week after the shadow period, and check-now at most about three per day. If the measured burden runs over budget for two consecutive weeks, the pilot is failing on its own terms, and the response is to redesign coverage or thresholds, not to ask the family to tolerate more.
- **Reliability:** uptime at least 95%, measured by the heartbeat; zero days where the system was silently dead.
- **Capture:** staged simulations, acted by a younger family member and never by the parents, captured at 90% or better; zero simulations silently cleared.
- **Latency:** alert out within 3 minutes of the event.
- **Privacy defeats counted, not hidden:** every covered, moved, or unplugged camera is logged as a first-class result, because it is the household voting on the design.

The measurement method matters as much as the thresholds: a family diary, a weekly call, and the staged simulations, over six to eight weeks.

### The honest failure mode

The likeliest way this fails is not technical. It is social, and it happens around week two: a burst of junk alerts from scenes no dataset contained, the family gets tired of being interrupted, someone mutes the chat or unplugs a camera, and the system dies silently, discovered a month later when something real happens. The heartbeat is the counter to the silent part of that death. The shadow calibration and the burden limits above are the counter to the junk part. If the family still switches it off, that is a result too, and it would be reported as one.

## Datasets, citations, licenses

Dataset media is **not** redistributed in this repository: download
scripts, manifests, and checksums only.

- **UP-Fall** (headline): Martínez-Villaseñor, L. et al., "UP-Fall
  Detection Dataset: A Multimodal Approach," *Sensors* 19(9), 1988
  (2019). DOI: [10.3390/s19091988](https://doi.org/10.3390/s19091988).
  Fetched by `scripts/download_up_fall.py`; terms per the dataset's
  project page.
- **Le2i** (headline): "Fall Detection Dataset," dataUBFC record
  (creators J. Dubois and J. Miteran, ImViA, Université Bourgogne
  Europe). DOI:
  [10.25666/DATAUBFC-2024-04-09](https://doi.org/10.25666/DATAUBFC-2024-04-09).
  License CC BY-NC-SA. Original dataset description: Charfi et al.
  (2013).
- **UR Fall** (per-view diagnostics only, never pooled; in UR Fall
  the class determines the camera): Kwolek & Kępski, *Computer
  Methods and Programs in Biomedicine* 117(3), 2014. License
  CC BY-NC-SA 4.0. Fetched by `scripts/download_ur_fall.py` from
  http://fenix.ur.edu.pl/~mkepski/ds/uf.html.

## Repository map

- `src/jaga/`: the pipeline: `motion_gate`, `sam_runner` /
  `sam_parse` (SAM 3.1 transport and stream parsing), `features`,
  `timing`, `rules`, `traces` / `overlays` (evidence forms),
  `adjudicator` (retained from the gate experiment; not in the
  shipped disposition path), `alerts` (the D2 ladder), `harness`,
  `config` (frozen parameters; their hash stamps every record).
- `SPEC.md`: the evaluation protocol, frozen 2026-10-27; changes
  exist only as dated amendments inside it.
- `DECISIONS.md`: the published technical decision record:
  protocol adoption, dated amendments, and the 2026-10-29 gate
  outcome and pivot.
- `results/`: run artifacts. **Claim discipline: every public number
  traces to the run results files here** (`gate_d1_dev_results.csv`
  for dev, `confirmation_results.csv` for confirmation) as summarized
  in their companion summaries; if a number anywhere disagrees with
  those files, the files win and the text is wrong.
- `scripts/`: downloaders, assemblers, run drivers, and
  `audit_history.py` (the pre-push credential audit).
- `examples/`: the offline pinned example above.
- `tests/run_checks.py`: the regression suite (77 checks).

## Provenance and disclosures

- Built during the event window above; the commit history is the
  evidence. Pre-existing work: none; the repository was created for
  this event.
- **AI assistance:** substantial implementation was written with an AI
  coding agent under the author's direction, working as a
  pair. The author designed the
  architecture and the evaluation methodology, owns every public
  claim, and is responsible for this repository. Every build unit
  passed independent verification against the specification before
  acceptance.
- **Clean room:** an independent personal project. Public datasets
  and published methods only. No employer code, data, prompts,
  labels, or internal tools appear anywhere in this repository.
- **Demo footage:** no real footage was shot by anyone, and no
  dataset footage is published. The demo's visuals are the
  system's-eye overlay renders (mask silhouettes, kinematic traces,
  verdicts) rendered from processing outputs, charts from the results
  files, and code-drawn graphics; no synthetic footage is used.
- **Privacy, stated precisely:** in the design, only candidate-event
  keyframes leave the home for segmentation; continuous footage does
  not, and no video is archived. The prototype harness's local
  cache is disclosed under The shipped system. No video is stored
  by Jaga; event keyframes are processed by the hosted SAM 3.1 API.
  This prototype processed public dataset clips only.

## License

The code, tests, results, and documentation in this repository are
released under the Apache License 2.0. See `LICENSE` and `NOTICE`.

The datasets cited above are not covered by that license. They
remain under their own terms, as cited in the Datasets section. The
Meta models the pipeline calls (SAM 3.1 and Muse Spark) are
accessed through the Meta Model API under Meta's terms; no Meta
model or hosted service output is redistributed under this license.
