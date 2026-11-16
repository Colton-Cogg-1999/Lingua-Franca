# Historical study without Kubernetes

The user requested local execution after Kubernetes setup repeatedly consumed too
many resources. All eighteen saved kind node containers are stopped and have
`restart=no`; neither cluster is needed for this study. Their data remain intact.

The scientific plans in `examples/historical-{main,continuous,related}.json` are
unchanged: 300 people, ten regions, 21,250 rounds per treatment, three sequential
treatments. No paid API or LLM inference is involved.

## Runtime

- Coordinator plus two Python worker processes, sharing a systemd CPU quota of
  200% (two CPU cores), a 2 GiB memory limit and lower scheduling priority.
- One standalone Redpanda container, limited to one CPU and 1.5 GiB RAM, with a
  1 GiB broker memory setting. Kafka listens on host loopback port 19092 only.
- Independent local analytics consumer: 512 MiB memory and 50% CPU quota.
- Periodic reports/completion audits: 512 MiB memory and 25% CPU quota. Reports
  run every 1,000 rounds and retain only compact plotting fields in memory.

These are upper limits, not measured consumption or reserved host RAM. The combined
CPU quotas permit up to 3.75 cores; the simulation itself is capped at two. The
project-owned rootless Docker daemon is still required for the single broker.
No Kubernetes services, CNI, etcd, or per-region container runtimes are running.

## Geographic meaning

The coordinator submits a region's own population and only permitted peer snapshots
to each task. The local executor validates those inputs, and the runner rejects any
conversation or migration outside the declared topology. Logical visibility is
checked at phase changes. The ledger explicitly records
`method=local_snapshot_visibility` and `network_isolation=false`.

These are simulation restrictions, not operating-system security boundaries.
Trusted Python processes share a machine and a reusable process pool. We make no
claim that hostile agent code could not inspect other state. The model's listener
interface still receives only utterances, scenes and its private lexical evidence.

## Durability and validation

Redpanda still receives every committed round transaction. Local checkpoints and
outboxes support restart; consumers deduplicate stable event IDs. Source provenance
now covers the local executor too, and run identity includes the execution mode.
The local run uses a new data directory so it cannot accidentally resume a checkpoint
from a different implementation. The original completed 2,000-round baseline is
untouched. No long historical treatment had started under Kubernetes.

All 38 unit/integration tests passed, including equality of local two-worker and
reference results through all nine historical phases and rejection of forbidden
population inputs. The local 18-round smoke run completed with 2,880 conversations;
its independent consumer matched every round, with zero simulated geographic
violations and no unverifiable events. Compact evidence is committed under
`docs/results/historical-local-smoke/`.

## Controls

From the project directory:

```sh
tools/localctl start       # broker readiness and topic first, then consumers/suite
tools/localctl status
tools/localctl logs
tools/localctl audit
tools/localctl report historical-main
tools/localctl pause       # stop simulation; preserve broker and consumer
tools/localctl resume      # resume latest committed round
tools/localctl shutdown    # stop local services, broker and project Docker daemon
```

The transient user services require an active user session and an awake host. No
boot/login autostart has been installed. Once running, they continue independently
of this chat. A service failure is visible in status/logs; it does not silently
claim completion. A later `resume` retries from durable state. Do not modify model
source during a run: provenance checks intentionally reject mismatched continuation.

Data: `runtime/local-data/experiment/`, `runtime/local-data/redpanda/`, and
`runtime/local-data/analytics/`. Each treatment receives its own report and final
ledger audit. The suite schedules treatments sequentially; reports wait for each
independent projection to catch up. The 20 GiB free-space guard remains active.
