# Initial validation — 2026-11-15

Seven standard-library unit tests pass: exact event reproducibility, checkpoint
continuation, conservation and probability bounds under maximal migration and
turnover, isolation, no-learning invariance, singleton behavior, parameter bounds.
CLI resume was also exercised. Python compilation and Docker Compose config
validation pass. Broker publishing, container build, and Kubernetes deployment
were not exercised because Docker daemon access is unavailable.

Baseline: 300 speakers, three islands, 100 rounds, four interactions per speaker
per round. Wall time 1.684 seconds including JSONL ledger writes, on the inspected
host. Ledger size approximately 29 MB. This is one measurement, not a throughput
guarantee. Event storage will become a constraint before small probability tables.

Ten replicate seeds (0–9), 300 speakers, 100 rounds each:

| Scenario | Mean between-island distance | Sample SD |
| --- | ---: | ---: |
| Isolated: contact=0, migration=0 | 0.6922 | 0.0211 |
| Contact: contact=0.15, migration=0.03 | 0.0384 | 0.0041 |
| Contact, prestige_bias=0 | 0.0391 | 0.0044 |

All other parameters use defaults. Distance is mean total variation distance
across meanings and occupied-island pairs. Raw values are in
`runs/comparison.csv` (generated, ignored by version control). This result verifies
an expected qualitative behavior of the implemented rules. It is not validation
against human linguistic data. Contact and migration are changed together, so the
comparison does not isolate their separate causal effects. The prestige toggle
also changes average learning intensity; it is not a controlled prestige-only
experiment. Same seeds are used but random streams can diverge across scenarios.

Scale smoke test: 3,000 speakers, 20 rounds, 2.099 seconds, process peak RSS
24.44 MiB as reported by Linux `getrusage`. Events were constructed but discarded;
this excludes ledger disk I/O, broker, Kubernetes, and any model inference. Raw
measurement: `runs/benchmark.json`. No claim of linear scaling: candidate-pool
construction currently includes population scans and should be optimized before
much larger runs.
