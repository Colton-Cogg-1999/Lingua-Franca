# Galapagos: a language-contact laboratory

A Python simulation of cultural transmission across synthetic island communities.
Speakers hold probability distributions over variants for shared meanings. They
interact, accommodate, innovate, migrate, and learn from older cohorts. No LLM,
GPU, third-party Python dependency, or cluster is required for the local model.

This initial implementation prioritizes computational sociolinguistics. It does
not implement the earlier biological genome/finch proposal.

## Run

From this directory, using Python 3.11 or newer:

```sh
python -m galapagos --rounds 100 --output runs/my-run
python -m unittest discover -s tests -v
python -m galapagos.experiments --replicates 10 --rounds 100 --output runs/my-comparison.csv
```

Output directories must be new to prevent accidental overwrites. Each run writes:

- `events.jsonl`: initialized population, interactions, innovations, migration, cohort replacement, round summaries.
- `metrics.jsonl`: population, variant frequencies, entropy, between-island distance, expected agreement before accommodation.
- `checkpoint.json`: complete population and pseudorandom-generator state.
- `config.json`: all model parameters.

Resume into a **new** output directory:

```sh
python -m galapagos --resume runs/my-run/checkpoint.json --rounds 100 --output runs/continued
```

Continuation metrics start with the checkpoint's current state. The new ledger is
a segment; retain the original segment and checkpoint. Checkpoints support clean
resumption, not atomic recovery of an interrupted streaming transaction.

Pass `--config experiment.json` to override parameters with a JSON object. Example:

```json
{"seed": 123, "islands": 3, "population": 300, "contact": 0.1, "migration": 0.02}
```

## Model and interpretation

Each speaker has an independent synthetic prestige value and a probability vector
for every meaning. Different islands begin with different preferred variants.
There is no intrinsically superior variant. Innovation switches a sampled token
to another existing variant; open-ended vocabulary creation is not implemented.

A shuffled listener order receives several interactions per round. Sources come
from local ring neighbors, the local community, or cross-island contact. Listener
probabilities move toward the heard token, scaled by learning rate and source
prestige. Prestige bias also changes average learning rate: the no-prestige
scenario is a bundled intervention, not a clean estimate of prestige alone.

After interactions, migration is applied simultaneously. Cohort replacement learns
from three sampled local tutors (with replacement), then replaces departing
speakers simultaneously. Population size is conserved globally. Empty islands are
allowed. The cohort process models cultural learning, not genetic inheritance or
individual biological reproduction. There is no explicit age structure yet.

Local ring ties are rebuilt from ID order each round; they are a deliberately
simple contact structure, not a calibrated human social network. Migration is
uniform between other islands; geographic distance, homophily, persistent ties,
register, bilingualism, and institutions are future extensions.

Between-island distance is mean total variation distance across meaning-specific
probability distributions (0 = identical; 1 = disjoint). Entropy measures variation
inside the community aggregate. Expected agreement is the listener's pre-learning
probability for the emitted variant; it is not measured comprehension. Run multiple
seeds; one trajectory does not establish a causal or empirical claim.

## Redpanda and kind

The broker publishing adapter and infrastructure configurations are prepared, but
have not been integration-tested here: Docker socket access is denied, and kind
and kubectl are absent. The current simulator runs in one process; island worker
coordination is the next implementation phase, not an existing feature.

When Docker access is available:

```sh
docker compose -f infra/compose.yaml up -d
# In a project virtual environment:
pip install -e '.[ledger]'
python -m galapagos.publish runs/my-run/events.jsonl
# With kind installed:
kind create cluster --name galapagos --config infra/kind.yaml
```

The development broker uses a mutable image tag; select and record a tested image
digest before repeatable infrastructure experiments. Broker data persists in a
Docker volume but is not an indefinite archive. Preserve the local ledger. Import
is at-least-once across publisher restarts; deduplicate `event_id` downstream.
Events are keyed by run to preserve their order within a partition. Identical
configuration and seed produce the same run/event IDs intentionally.

The planned distributed protocol uses coordinator-issued `(run, round, phase)`
commands, island-local checkpoints, explicit migration batches, and a barrier
before advancement. Do not deploy independent copies of the local simulator as
island workers: that would create disconnected full-world simulations. Broker
transactions alone cannot commit arbitrary in-memory Python state. A durable
outbox/checkpoint commit protocol is still required.

## Local feasibility

See [the hardware and inference assessment](docs/feasibility.md). LLMs are optional
for rendering sampled utterances; they do not drive this first model. The project
uses a standalone Python kernel rather than Mesa initially so transition rules
and recovery are easy to inspect. A Mesa adapter can provide richer networks and
interactive exploration later.
