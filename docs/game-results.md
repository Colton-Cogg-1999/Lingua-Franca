# First communication-game results — 2026-11-15

## Actual acquisition trace

Round 1: agent 44 said `koro give` to agent 36, intending a request for stone.
Agent 36 did not recognize the utterance. Repair pointed to stone and demonstrated
the action. Its stone lexicon changed from `{taku: 5}` to `{taku: 5, koro: 1}`.

Round 2: agent 36 produced `give koro` to agent 37. Agent 37 then learned the word
through another repair. The first learner used its own construction with the
acquired noun. These are actual logged events, not LLM-generated illustrations.
See `runs/communication-game/report.md` for event IDs and full traces.

## Main demonstration

Configuration: 120 speakers across three islands, 50 rounds, four listening
opportunities per person per round, seed 42. Includes migration, cohort replacement,
and rare novel-word production. Full configuration: `examples/contact-game.json`.

| Metric | Round 1 | Round 50 |
| --- | ---: | ---: |
| Overall first-attempt success | 73.8% | 97.9% |
| Cross-island first-attempt success | 3.1% | 98.6% |
| Overall success including repair | 95.2% | 99.4% |
| Mean lexical total variation distance | 0.946 | 0.305 |

Initial distance before encounters was 1.0. The final distance remaining above zero
while comprehension approaches one is meaningful: communities can understand each
other while retaining different production preferences.

![Main run](../runs/communication-game/results.png)

## Controlled mechanism checks

Ten seeds per scenario; 60 speakers, 50 rounds, contact probability 0.3. Migration,
cohort replacement, and innovation disabled in every scenario. Rates below use
count-weighted interactions over rounds 41–50 within each replicate, then average
across the ten replicates. Distance is measured at round 50.

| Scenario | Cross-island first-attempt success | Overall success including repair | Lexical distance |
| --- | ---: | ---: | ---: |
| Repair and learning | 99.945% | 99.992% | 0.362 |
| No repair | 0% | 70.150% | 1.000 |
| No learning | 0% | 93.892% | 1.000 |
| Isolated | No cross-island encounters | 100% | 1.000 |

Cross-island first-attempt success for repair+learning has sample SD 0.116 percentage
points across seeds. Raw observations and aggregate SDs are in
`runs/game-ablations/replicates.csv` and `summary.json`.

The zero results in the controls are expected by construction: initially disjoint
vocabularies cannot acquire foreign referents when both alternative acquisition
routes and grounded learning are disabled. These are mechanistic sanity checks,
not discoveries about human language. Perfect repair, shared action semantics,
small vocabulary, and no forgetting strongly favor convergence. Same seeds are
not perfectly paired encounter schedules because different branches consume
randomness differently.

![Controlled comparisons](../runs/game-ablations/comparison.png)

## Distributed execution checks

The same main experiment was run with:

| Transport | Measured round execution + commits |
| --- | ---: |
| In-process reference | 9.567 seconds |
| Three-process pool | 20.849 seconds |
| Three HTTP worker processes on loopback | 18.528 seconds |

These are individual local measurements under changing concurrent load, not a
controlled performance benchmark. Export time is excluded. Distribution is slower
at this small scale because copying, serialization, process communication, and
coordination dominate. Do not present this as a speedup claim.

All three complete event exports are byte-identical:
`e159c5204f1e2e606fef5fce3ecf56a924714d0bd1e0e8c8d73bd32186c098df` (SHA-256).
All final population state hashes match:
`4c873a559e4f8fa9008e69240c6b25a0996d7323aead8d2c186875451d2488ba`.

The final HTTP version additionally checks model/source fingerprints; its three-round
smoke test matched the corresponding reference checkpoint. A resumed run completed
rounds 51–52. Model implementation SHA-256:
`20ac5726e0624b13991bde88cc8bbfc43441dd05772e96592d0bd366f01ace66`.

22 tests passed, covering parsing without privileged intention, grounding,
production after learning, homonym interpretation, no-learning controls, isolated
communities, population conservation, retry determinism, result ordering, ownership
validation, process equivalence, checkpoint integrity/continuation, HTTP equivalence,
transport retries, unavailable workers, and source-version rejection. Transport
failure injection is simulated; full OS-level crash campaigns remain future work.

A session interruption occurred during the control sweep. Thirty-five completed
replicate histories were recovered from the recorded trajectories, and the remaining
five were rerun. All forty are now retained as individual complete files. The
experiment runner now commits each replicate before aggregation and supports resume.

## Remaining boundary

The research model and local distributed execution run. Redpanda publishing is
implemented but not broker-tested, and Kubernetes deployment remains outstanding.
Docker socket access is unavailable; kind and kubectl are not installed. No model
serving or LLM behavior was introduced. A project-local analysis environment with
Matplotlib was installed and its exact package versions recorded.
