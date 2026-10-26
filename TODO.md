# TODO (repo-resident; survives any single session or machine)

## Now
- [ ] Author decisions on SPEC.md: gate rule, alert policy, evidence loop
- [ ] Meta Model API key via secure entry → API client + hour-3 billing/latency check
- [ ] Frame sampling + motion gate smoke test on the synthetic sit-down clip

## Build order (eval code first, reviewed hardest)
- [ ] Dataset download scripts + frozen clip manifest (UR Fall, Le2i)
- [ ] Cached, resumable SAM runner (cache keys: clip ID + prompt hash + model ID)
- [ ] Feature extraction (mask-derived kinematics) + IoU tracking
- [ ] Rules state machine, tuned on dev for recall
- [ ] Muse adjudicator, dev iteration only, iteration count logged
- [ ] FREEZE spec → run gate ablation once → decision
- [ ] Harden winner path + alert stub + labeled cached demo mode

## Submission runway
- [ ] Feature freeze Nov 3 (also a review freeze)
- [ ] Video script drafted Nov 2 evening; record Nov 3; lock Nov 4 18:00 JST
- [ ] Author clean-clone run on his own laptop before submission
- [ ] Submit Nov 4 evening JST; Nov 5 morning is insurance only
- [ ] Explain-back gate before the video script; teach-back rehearsal before Nov 9
