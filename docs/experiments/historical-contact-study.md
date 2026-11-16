# Historical contact study: 21,250 rounds per treatment

Current execution: local Python workers and a standalone Redpanda container.
Kubernetes execution was retired at the user's request before any long treatment
started. Use `tools/localctl status`. The timeline and treatments below remain
unchanged; the original Kubernetes deployment details are retained as history.
See `local-execution.md` for current controls and resource limits.

## Question and historical interpretation

Can pre-existing regional variants persist under sparse imperial contact, diverge
under a prolonged reduction/reorganization of contact, and remain distinct after a
very brief period of dense modern contact? Does initial shared ancestry change
that trajectory relative to initially disjoint vocabularies?

Roman Latin already varied regionally. Western political fragmentation did not
mean a uniform disappearance of trade, religious networks, or eastern imperial
connections. We therefore use selective, weighted routes and low contact rates,
not a single complete blackout called a Dark Age. We do not claim to reconstruct
Latin, Romance languages, or actual continental linguistic histories.

Sources informing the qualitative design:
- J. N. Adams, *The Regional Diversification of Latin 200 BC–AD 600*:
  https://www.cambridge.org/core/books/regional-diversification-of-latin-200-bc-ad-600/E1ADF63B49D0C01B1566BCE9B72AC13A
- English Heritage, early medieval networks and surviving Mediterranean contacts:
  https://www.english-heritage.org.uk/learn/story-of-england/early-medieval/networks/

The phase boundaries and probabilities below are researcher-chosen treatments,
not historical estimates inferred from those sources. Geography and population
labels are analogies; the model omits bilingual registers, institutions, education,
conquest, unequal political power, literacy and standard-language maintenance.

## Clock and treatments

Ten abstract learning ticks per illustrative year, from year -100 to 2025 in
astronomical year numbering (approximately 100 BCE onward). Each tick gives four
listening opportunities per person. A tick is not a generation or an actual census
of conversations. The clock establishes duration ratios; it does not calibrate
linguistic change per historical year.

| Period analogue | Ending round | Duration in rounds | Remote encounter probability | Migration probability per person/tick |
| --- | ---: | ---: | ---: | ---: |
| -100–200: imperial regional variation | 3,000 | 3,000 | 5% | 0.00015 |
| 200–450: late imperial fragmentation | 5,500 | 2,500 | 2.5% | 0.00010 |
| 450–700: post-imperial localization | 8,000 | 2,500 | 0.3% | 0.00002 |
| 700–1000: early medieval networks | 11,000 | 3,000 | 0.6% | 0.00003 |
| 1000–1500: medieval trade growth | 16,000 | 5,000 | 1.5% | 0.00008 |
| 1500–1800: early modern exchange | 19,000 | 3,000 | 2.5% | 0.00015 |
| 1800–1950: industrial transport | 20,500 | 1,500 | 6% | 0.00030 |
| 1950–1990: mass travel/broadcast | 20,900 | 400 | 12% | 0.00050 |
| 1990–2025: digital contact | 21,250 | 350 | 25% | 0.00070 |

The final phase is 1.65% of the full timeline. Industrialization, broadcast and
internet contact are distinct phases. Modern network expansion grants permission
for all pairs to interact; it does not guarantee every pair communicates each tick.
Broadcast remains represented as pairwise encounters, not a literal broadcast model.

`edges` in each plan contain [region_a, region_b, relative_weight]. Conditional on
remote contact, choose a region with route-weight proportional probability, then a
person within it. Friendship preference can further condition the eligible pool.
This avoids automatically treating a large population as a stronger trade route.
Migration follows permitted weighted edges separately from encounter probability.
Closed edges are blocked by NetworkPolicy and direct reachability checks.

## Populations and initial variation

Ten regions, 30 people each, 300 total. Six Romance-analogue regions: Iberia, Gaul,
Italia, Balkan interior, Sardinia and Adriatic. Four additional synthetic populations
External-A through External-D start with distinct lexicons and alternating word
orders. They are not proxies for all of Africa, China, North America or the Middle
East; those labels would conceal enormous real linguistic diversity and contact.

The six related populations share ancestral vocabulary but eligible regional forms
start with 15% probability, 85% ancestral probability. Only words affected by the
region's substitution have two forms. Sound biases remain explicitly imposed, with
unequal coverage of the tiny vocabulary; report that limitation in interpretation.
External-A/B have selected early links; C/D enter the wider network only in the early
modern phase. These are controlled exposure schedules, not reconstructed trade maps.

All initial external lexicons are disjoint from the related populations, including
seeded regional variants (tested through held-out comprehension). Common concepts
and the two action words remain universal scaffolding. Thus these are different
object vocabularies/construction conventions, not fully unrelated natural languages.
No ancestry-specific penalty inhibits learning. A distant population may converge
if contact and repair suffice; that outcome is part of the experiment.

Other parameters: turnover 0.002 per tick (roughly 50 illustrative years of expected
residence before replacement), retention 0.9985 (approximately 46-year evidence
half-life before reinforcement/pruning), innovation 0.0005, regional sound change
0.003, construction innovation 0.0004, repair 0.2, learning 0.8, prestige bias 0.2,
friendship preference 0.85. Replacement is local tutor learning, not biological
inheritance. A migration floor of 15 residents prevents regional extinction and
keeps all encounter counts comparable; this is an explicit demographic constraint.

Repair remains perfectly informative when it occurs, but is less frequent than in
the first experiment. Distance has no intrinsic borrowing barrier. There is no
phonological generalization in comprehension: forms must have been learned.

## Comparison design

Three sequential runs on the same workers, each 21,250 rounds:

1. `historical-main`: the staged history and initially unrelated external groups.
2. `historical-continuous`: during phases 2–6 retain imperial Romance routes and the
   imperial global contact/migration probabilities. External route opening dates
   remain the same, but available external routes also use the preserved global
   encounter probability. This tests the bundled sustained-contact intervention;
   it does not isolate each edge, migration or exposure effect independently.
3. `historical-related`: the main schedule with all ten populations initialized
   from the common ancestral lexicon/order; the six core regional variants remain.
   This tests initial vocabulary/construction ancestry under the same opportunity
   schedule, not a claim of genetically determined linguistic capacity.

All use seed 476 and the same remaining parameters. Same-seed runs are matched
initial designs, not identical later random draws: state-dependent sampling paths
can diverge. One seed per treatment is exploratory. Do not compute population-level
significance treating 76.5 million encounters as independent experimental replicates.
A later independent-seed replication set is required before claiming robustness.

Each run has 25.5 million encounters; all three have 76.5 million. Workers never run
two treatments simultaneously, which would otherwise conflict through shared
network policies. A failed child run stops the suite; restart resumes committed
rounds and skips completed simulations without restarting their histories.

## Measurements and falsifiable outcomes

Every 250 ticks and at both sides of every phase transition, run read-only held-out
comprehension tests (160 trials per ordered region pair), with no feedback to agents.
Save initial diagnostics too. Every round stores global, within-related,
within-external and between-group lexical distances. Preserve word distributions,
first-attempt success, repair, migration, population and cohort events in the ledger.

Questions specified before seeing results:
- Does the related group diverge more under historical fragmentation than sustained
  contact, particularly at rounds 8,000, 11,000 and 16,000?
- How much of the pre-modern divergence remains at 20,900 and 21,250?
- Does shared ancestry alter late cross-group comprehension/recovery under identical
  contact opportunities? Report directionality, not one symmetric score.
- Do changes come from local acquisition, migration or surviving earlier forms?
  The ledger supplies evidence, but causal separation needs further ablations.

Do not classify outputs as separate languages from a distance threshold. Success
is informative regardless of whether the desired historical-looking pattern appears.

## Original Kubernetes execution (superseded), storage and provenance

A separate eleven-node rootless kind cluster: one control plane and ten region
workers, each geographically labeled. The completed baseline cluster's containers
are stopped, not deleted, to free host keyring capacity. Baseline raw data and the
old images remain intact. The new host directory is `runtime/history-data/`; its
kubeconfig is `runtime/history-kubeconfig`. The old `tools/galapagosctl` addresses
the stopped baseline; use `tools/historyctl` for this study.

Redpanda uses durable host-mounted storage, transactional publication, disabled
retention for the bounded study, and an independent SQLite analytics projection.
Each round has a durable state/outbox before ledger publication. The next round
waits for broker acknowledgement. Stable IDs permit replay deduplication. One host
and one broker do not provide host-failure availability.

Model source checksums cover the game, initialization, runner, regional transport,
policy and checkpoint implementation. Plan hashes distinguish treatments. Before
launch, commit source and record the immutable image ID. Reproduction of the old
baseline requires its old image/source commit, not the new model version.

An 18-round smoke run exercises every phase and all 100 directed reachability
checks at each transition. Its independent ledger counts must match local outboxes
before the long suite starts. Unit/integration tests also cover weighted exclusion,
ancestry, clock boundaries, population floors and resume equivalence.

The suite is expected to take hours per treatment; measure live throughput before
quoting an ETA. It can run after this chat ends while the machine stays awake and
the user service remains active. Filesystem capacity is checked before every round;
less than 20 GiB free stops progress. All raw data stay outside Git. Monitor actual
growth; estimates must include checkpoints, broker storage and the SQLite index.

```sh
tools/historyctl status
tools/historyctl logs
tools/historyctl audit
tools/historyctl report historical-main
tools/historyctl pause
tools/historyctl resume
```

A user service runs `tools/watch-history`, refreshing reports and producing a
completion audit for each treatment after the independent consumer catches up.
Pause affects the suite job; the broker and consumer stay running.

## Runtime resumption note

The eleven-node cluster exceeded the host user keyring quota even with the old
cluster stopped. Each project node now sets containerd runc `NoNewKeyring = true`;
this is recorded in `infra/kind-history.yaml` and its renderer. It avoids allocating
a fresh session keyring per workload. No host sysctl or desktop configuration was
changed. This trusted local research cluster does not use kernel keyrings for
agent isolation; geographic isolation is still independently tested with Calico.

Simulation image ID: `sha256:447b9ac2f56aa1f5ded3f3541436ae4b56750882cb361ff8c89f291b90fc6719`.
Model and study source commit before launch: `0766785`.
