# Six regions, 2,000 rounds: shared ancestry and fragmentation

This experiment completed 2,000 rounds in a project-owned, rootless kind cluster.
The committed audit and figures are in `../results/roman-fracture-2000/`. Its reference
plan is `examples/roman-fracture-2000.json`. It is inspired by fragmentation after
Roman imperial integration, not calibrated historical reconstruction. Region names
are experimental labels; generated speech is not Latin, French, Spanish, etc.

## Fixed plan

360 initial speakers (60 per region), 12 shared object concepts, 2 action verbs,
and 2 possible construction orders. Regions: Iberia, Gaul, Italia, Dacia, Sardinia,
Dalmatia. Every region begins with the same lexicon and construction.

| Rounds | Connectivity |
| --- | --- |
| 1–200 | All six regions connected |
| 201–1500 | All six completely isolated from one another |
| 1501–2000 | Iberia–Gaul, Gaul–Italia, Italia–Dalmatia reopened; Dacia and Sardinia remain isolated |

Edges permit direct encounters and migration, not automatic transitive contact.
Indirect diffusion can occur through people and their later interactions along
multiple edges. During total isolation, contact opportunities are redirected
locally and no speaker can migrate to a different region.

Each speaker has four listening opportunities per round. Remote contact probability
is 0.3 when a permitted remote population exists; migration probability is 0.003
when a destination is open. Other parameters: turnover 0.02, repair 0.7, learning
weight 0.8, prestige bias 0.4, novel lexical token probability 0.003, construction
innovation 0.004, memory retention per round 0.985, friendship preference 0.85.

A 0.03 sound-shift opportunity applies a stylized regional substitution:
Iberia k→g; Gaul t→d; Italia p→b; Dacia a→e; Sardinia s→h; Dalmatia r→l.
These directions are imposed experimental biases, not emergent historical sound
laws. Whether the resulting forms spread depends on encounters and learning.
Sound bias follows current region, so migrants immediately encounter that production
pressure. Lexical invention uses a finite syllable inventory; collisions can yield
homonymy. Grammar is only two-token order, not full syntax.

Memory evidence decays, and very weak forms are pruned while preserving at least
one form per concept/construction. Cohort acquisition samples three local tutors
with grounding. Repair remains perfectly informative when it occurs. These are
explicit simplifying assumptions. A measured divergence is not sufficient to label
populations as distinct real-world languages.

## Working distributed architecture

Seven kind nodes: one control plane plus six labeled region nodes. One worker
Deployment is pinned to each region. The coordinator and single Redpanda broker
run on the control-plane node with explicit tolerations. The broker and checkpoint
storage use project directories mounted into the kind control-plane container.

A coordinator stages **only a region's own population** on its worker. Workers
fetch permitted peers' snapshots directly from those peers. Kubernetes NetworkPolicy
blocks closed links; the coordinator never sends foreign populations as a bypass.
Workers validate assembled snapshot hashes. Closed links also prevent simulated
migration. The shared clock advances after all permitted tasks have completed.

Calico v3.33.0 uses VXLAN and iptables-nft to enforce policy. Every phase transition
reconciles region policies and probes the full 6×6 directed reachability matrix.
A mismatch stops progress. The ledger/control plane is separately permitted, so
isolation does not disable monitoring. Agents cannot read the shared ledger.

Each completed round atomically commits state plus an outbox on the host filesystem,
then publishes its events as a Redpanda transaction. The next round starts only
after successful publication. Restart resumes the latest committed checkpoint and
publishes pending outboxes. A crash after broker commit but before progress-marker
persistence may repeat a transaction: consumers must deduplicate stable event IDs.
This is not a claim of global exactly-once processing.

The topic is `galapagos.evolution.v2`, with one partition, one replica, and disabled
time/size retention for this bounded run. Write caching is disabled. Full event
batches are also retained locally. A single broker and one physical machine do not
provide host-failure availability. The runner stops before advancing if less than
20 GiB remains free on the data filesystem.

## Observe and control

From `/home/colton/Projects/Galapagos`:

```sh
tools/galapagosctl status
tools/galapagosctl logs
tools/galapagosctl pause
tools/galapagosctl resume
```

Pause suspends the Kubernetes Job; resume starts a coordinator from committed state.
It leaves broker and workers running. Do not run a second coordinator for this same
experiment or reapply initial region policies while a job is active.

Live state and research artifacts:

- `runtime/data/experiment/roman-fracture-2000/status.json`: latest broker-acknowledged round.
- `runtime/data/experiment/roman-fracture-2000/rounds/`: authoritative checkpoint/outbox bundles.
- `runtime/data/experiment/roman-fracture-2000/published.json`: last published round.
- `runtime/data/redpanda/`: broker data, outside disposable container storage.
- `runtime/kubeconfig`: access to this dedicated cluster.

Generate a current static report without changing the simulation:

```sh
.venv/bin/python -m galapagos.region_report runtime/data/experiment/roman-fracture-2000
```

Every 50 rounds and at boundaries, a separate seeded diagnostic tests pairwise
comprehension on copied/read-only population state. It supplies no observations to
agents and causes no learning. This distinguishes loss of mutual comprehension
from changes in production preferences without reconnecting isolated populations.

The run stops automatically at round 2,000. It runs independently of this chat,
but the host must remain awake and the user session active: the rootless Docker
service is a transient user service and user lingering is not enabled. Sleep pauses
computation; a host restart requires restarting the project Docker service/cluster.
Data remains on disk. This setup does not alter system Docker access or user groups.

## Validation before launch

28 unit/integration tests passed, including filtered regional inputs, zero isolated
migration, deterministic peer transport, forgetting bounds, and read-only audits.
A nine-round Kubernetes smoke experiment exercised all three network phases.
Every actual probe matched the intended matrix. Its isolated rounds contained zero
cross-region conversations and zero migrations. All 1,322 committed Redpanda records
matched their local event payloads exactly, with no duplicate IDs in that smoke run.
The coordinator recovered once during the preceding worker-image rollout; the
completed smoke artifacts and broker audit are retained under `runtime/`.

Runtime image tag: `galapagos-regions:v2r2`; image ID:
`sha256:ffee064bf39c2f67565d59f1748fdf27ecc171efdfbfc7b7b06ce382572b49c1`.
Redpanda v26.2.2; Docker rootless v29.9.3; kind v0.33.0; Kubernetes v1.37.0.
Official setup references: [rootless kind](https://kind.sigs.k8s.io/docs/user/rootless/),
[Calico on kind](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind),
and [Redpanda topic settings](https://docs.redpanda.com/streaming/current/reference/properties/topic-properties/).

## Independent analytics and completion audit

A separate Kubernetes Deployment consumes Redpanda with `read_committed` isolation.
It projects event counts, summary metrics, and geographic violations into
`runtime/data/analytics/projection.sqlite`. Event-ID deduplication and consumer
offsets are committed in the same SQLite transaction. Reassignment resumes from
those local offsets; an empty database rebuilds from the topic's beginning. A
repeated event ID with conflicting bytes fails rather than silently changing data.

This consumer checks conversation and migration endpoints against the most recent
recorded boundary topology. Its progress can lag the simulator, especially during
initial replay; always compare `last_complete_round` with the coordinator's round.
The analytics process does not feed anything back to speakers or the coordinator.
Its network permissions allow broker and DNS access only.

```sh
tools/galapagosctl audit
tools/galapagosctl report
```

A bounded user service (`galapagos-report`) refreshes the Markdown/PNG/SVG report
approximately every 100 rounds. After round 2,000 it waits for the independent
consumer, checks every round's conversation count against its committed local
summary, verifies zero geographic violations/unverifiable events and publication
through round 2,000, writes `completion-audit.json`, and exits. The final chart and
report are placed in the run directory. It does not send external notifications.

The analytics consumer remains available after the simulation finishes. It is a
separate image (`galapagos-analytics:v1`); the running simulation/worker images and
model parameters were not changed when it was added. Two additional analytics
tests verify duplicate replay and atomic rollback on conflicting event payloads.
