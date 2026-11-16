# Communication-game architecture and next deployment steps

## Current executable architecture

Experiment CLI → authoritative coordinator → island tasks → in-process, process-pool,
or HTTP transport → validated results → demography → atomic checkpoint/outbox →
metrics and readable traces. The HTTP demo starts three independent worker processes.

Workers are stateless deterministic functions. A request includes configuration,
round, island, task ID, and a complete round-start snapshot with a SHA-256 hash.
The HTTP envelope also checks model version and source fingerprint. The worker
produces utterances from that snapshot and updates only listeners on its island.
A response carries the same task/snapshot identities, updated owned speakers,
and events. Its payload hash is checked by the transport.

The coordinator rejects missing, duplicate, stale, mismatched, or incorrectly owned
results. It sorts results by island before committing. Retrying the same task
recomputes identical results. Network failures receive bounded retries; a failed
round does not advance authoritative state. There is no worker-side mutable
population to update twice after a retry.

All results are collected before migration and cohort replacement. Those phases
use a distinct deterministic random stream. Randomness does not depend on wall
clock, process ID, host, or worker arrival order. Simulation time advances only
when the round can be committed.

Each round directory commits population state and its outgoing ledger events
together. Derived exports may be regenerated from those directories. A durable
publisher can later scan committed outboxes and deliver events at least once;
consumer deduplication uses stable event IDs. Current `galapagos.publish` imports
a completed export, not an automatic continuous outbox relay.

## What this proves and what it does not

This is a working distributed execution boundary, tested on one physical machine.
It is not yet a Kubernetes deployment, Redpanda-driven scheduler, multi-host
performance claim, or highly available service. The coordinator holds the full
population. Every island request currently includes the full snapshot. This is
simple and auditable, but serialization and copying can outweigh parallelism for
small simulations. Production ownership and snapshot distribution should be
optimized only after measurement.

Checkpoint hashes detect corruption, not malicious tampering. HTTP is unauthenticated
and intended for a trusted local network; workers bind to loopback by default.
Transport checks protect against accidental mismatches, not hostile workers.
A process crash can be recovered from the last committed bundle; losing the host
filesystem cannot. The model source is fingerprinted; exact replay across future
Python/runtime versions is not established, so preserve the environment for research.

## Kubernetes/Redpanda deployment plan

1. Build one immutable image containing the model, worker, coordinator, and publisher.
2. Run one worker Deployment per island, with node selectors matching the existing
   kind labels and one Service per worker. Workers use the same HTTP contract.
3. Run a coordinator Job with the experiment configuration and a persistent volume
   for round bundles. Avoid overlapping coordinators for the same run; distributed
   failover needs fencing/leases and is not provided by the local runner.
4. Run a separate outbox relay that scans committed round directories and publishes
   batches to Redpanda. Store relay progress separately; replay after a crash is
   safe only with consumer event-ID deduplication.
5. Consume the ledger into analytic storage (initially local files or DuckDB),
   keeping versioned event schemas and explicit experiment/replicate identifiers.
6. Test worker termination mid-task, duplicate delivery, coordinator termination
   before/after commit, broker outage, and restart from persistent storage.

Redpanda is deliberately not a random source or the simulation clock. Broker lag
must delay progress rather than change learning. Moving task coordination to
broker topics is a separate architectural choice; it is not necessary to gain an
independent, replayable research ledger.

## Scientific semantics that must survive distribution

- Intentions are visible to the experiment controller and ledger, not the listener parser.
- Parsing receives only utterance, visible scene, and listener knowledge.
- A failed ungrounded interaction does not teach a referent.
- Repair supplies a perfectly informative gesture by assumption, not by inference.
- Evidence affects later production, not just a displayed transcript.
- Speaker production is frozen within a round; listener learning is sequential within its owning island task.
- Migration and cohort replacement happen after all communication tasks finish.
- Local and cross-island success are reported separately; first-attempt and assisted success are different outcomes.
