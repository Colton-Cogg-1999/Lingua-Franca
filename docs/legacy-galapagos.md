# Galapagos — distributed sociolinguistics laboratory

**Current deployment:** a six-region, 2,000-round fragmentation experiment now runs
in Kubernetes with Calico-enforced isolation and transactional Redpanda logging.
See [the run plan and controls](docs/experiments/roman-fracture.md).
Use `tools/galapagosctl status` to inspect progress. The sections below describe the
preceding local prototype; its statements that cluster/broker integration is pending
are historical and superseded by the deployment document. The current model has
12 concepts; the previous four-concept model is archived in `docs/model_versions/`.


Speakers produce short utterances from their own learned lexicons and constructions.
Listeners interpret them using their own knowledge. Misunderstanding can trigger
pointing and clarification, which teach a new word or construction. Learned forms
can then appear in the learner's later utterances. No language model is involved.

The communication game runs in one process, a process pool, or separate HTTP worker
processes. All three transports have been exercised on this machine. Redpanda and
kind remain prepared integration components, not a running cluster.

## Try the game

Python 3.11+ is sufficient; no packages are required for the simulator.

```sh
cd /home/colton/Projects/Galapagos
python -m galapagos.play --config examples/contact-game.json --rounds 50 --workers 3 --output runs/my-game
```

Output directories must be new. Start with the generated `report.md`: it includes
actual utterances, interpretations, repair exchanges, and the lexical evidence
before and after learning. It also finds an example of a learner later producing
an acquired form, when one exists.

For three independently launched HTTP worker processes on loopback:

```sh
python -m galapagos.network_demo --rounds 50 --output runs/my-http-game
```

This command owns and cleans up its workers. To run workers separately, start
`python -m galapagos.worker --port 8100` (and other ports), then provide repeated
`--worker-url http://127.0.0.1:8100` options to `galapagos.play`. URLs are assigned
to island tasks by island index. Workers use immutable request snapshots and do
not persist population state themselves. HTTP is for trusted local environments;
there is no authentication or TLS. The service binds to loopback by default.

## What is implemented

- Three initial island vocabularies over four visible objects: water, fruit, stone, seed.
- Two shared actions (`give`, `show`) and two learnable construction orders.
- Production sampled from an individual's positive lexical/construction evidence.
- Interpretation that cannot read the hidden intention or source speaker's knowledge.
- Binary success feedback; optional perfectly grounded pointing/repair on failure.
- Evidence updates after successful action or repair; unsuccessful ungrounded tokens do not teach meanings.
- Persistent friend IDs, local/remote contact, optional prestige influence, novel word tokens, migration, and sampled tutor-based cohort acquisition.
- Per-island deterministic random streams, round barriers, process and HTTP transports, retries, result ownership validation, and state integrity checks.
- Atomic per-round checkpoint/outbox bundles, readable traces, metrics, replicated controls, and optional static plots.

A concrete observed trace: agent 36 heard `koro give`, failed to understand, and
learned that `koro` names stone through pointing. The following round it produced
`give koro` itself, combining the learned noun with its own construction.

## Interpretation and limitations

This is a tiny artificial referential language, not fluent dialogue. Clarification
requests and gestures in brackets are fixed protocol annotations. Object concepts
and action meanings are shared in advance. Grounding is perfectly informative
when repair occurs, and knowledge does not decay. Those assumptions make learning
comparatively easy. First-attempt success is the learning metric; final success
also counts help from repair and must not be interpreted as independent mastery.

Grammatical variation is limited to verb–object versus object–verb order. Learned
word meanings and construction evidence are shared between comprehension and
production; construction and noun choice are sampled independently. The current
parser does not support compositional syntax beyond this two-token task. Homonyms
can cause ambiguity, but there is no pragmatic inference or natural-language text.

Friendship IDs persist across migration; ties to departed speakers are removed.
There is no homophily, relationship formation, register, identity resistance, or
institutional pressure yet. Cohort learners receive perfectly grounded tutor
samples. Prestige is a fixed random attribute; default experiments disable it.
Migration is uniform between other islands. All speakers remain equally likely
to be selected within the chosen contact pool.

During a round, production uses the frozen round-start population. Each worker
updates its own listeners sequentially. Learned forms become available for
production the next round. This explicit synchronous model is what makes worker
speed and message arrival order irrelevant; it differs from asynchronous learning.

## Artifacts and recovery

Each committed directory `rounds/000050/` contains:

- `checkpoint.json`: configuration, source fingerprint, and full population state.
- `events.jsonl`: a committed event batch, ready for later ledger publication.
- `summary.json`: communication rates and vocabulary distributions.
- `manifest.json`: SHA-256 integrity checks for those three files.

A staging directory is flushed and renamed only when the bundle is complete.
Stale `.pending-*` directories are ignored. At this stage, commit atomicity is
local to one filesystem, and the coordinator is a single point of control. This
is not distributed consensus or a highly available control plane.

Resume from the latest committed round into a new directory:

```sh
python -m galapagos.play --resume runs/my-game --rounds 20 --workers 3 --output runs/my-game-continued
```

Resumption rejects a changed model implementation or corrupted bundle. Random
streams are derived from seed, round, island, and phase rather than process
scheduling. Identical configuration/model version intentionally identifies the
same experiment; duplicate deliveries retain identical event IDs. Root-level
`events.jsonl`, `metrics.jsonl`, and `report.md` are derived exports; committed round
bundles are authoritative and survive interrupted export. A continuation's exports
contain only its initial checkpoint and new rounds; preserve its parent run.

## Controlled experiments and plots

```sh
python -m galapagos.game_experiments --replicates 10 --rounds 50 --output runs/my-controls
# If interrupted, repeat the same parameters with --resume.
python -m unittest discover -s tests -v
```

Controls compare repair+learning, no repair, no learning, and isolation. Migration,
turnover, and innovation are disabled to avoid alternative routes for acquisition.
Per-replicate files are committed before aggregation. Shared seeds do not guarantee
identical encounter streams across interventions because branching consumes random
numbers differently. Results describe this model, not empirical human populations.

For PNG and SVG figures, an isolated `.venv` with Matplotlib has been installed.
Exact analysis dependencies are recorded in `requirements-analysis.txt`.

```sh
.venv/bin/python -m galapagos.plot_game runs/my-game --ablations runs/my-controls
```

The existing demonstration is in `runs/communication-game/report.md`; plots and
control results are in `runs/communication-game/` and `runs/game-ablations/`.

See [the first measured results](docs/game-results.md) for the acquisition trace, controlled comparisons, transport timings, and validation evidence.

## Infrastructure direction

See [the distributed protocol](docs/communication-architecture.md). `infra/kind.yaml`
defines labeled island nodes; `infra/compose.yaml` defines a development Redpanda
broker. Neither has been deployed here: Docker socket access is denied to this
session, and kind/kubectl were not installed. The publisher is available as
`python -m galapagos.publish runs/my-game/events.jsonl` after installing `.[ledger]`.
It is untested against a live broker, preserves per-run partition ordering, and
requires consumer deduplication across repeated imports. Broker retention is not
an archive policy. The development broker image is mutable until a tested digest
is selected.

The earlier probability-only model remains available through `python -m galapagos`;
its old instructions are in [variant-prototype.md](docs/variant-prototype.md).
It is separate from the grounded communication game. Local inference options are
assessed in [feasibility.md](docs/feasibility.md); LLM experiments are deferred.
