# Lingua Franca: trade, learning, and cultural change

Completed 9 runs, 216,000 rounds, and 51,840,000 recorded encounters.

**Integrity audit: PASS.**

This is a controlled experiment in an artificial society. It does not establish facts about people, historical language change, or the fall of Rome. The historical analogy supplies a contact schedule, not an empirical calibration.

## Design and mechanisms

Six communities each contain 20 agent slots in the full study. Regions 0–2 initially share a common lexicon with regional variants; regions 3–5 have distinct lexicons. There are six concrete goods: grain, water, timber, ore, cloth, and medicine. Agents produce specialized goods, consume all six, and prefer a diverse inventory through a weighted logarithmic utility function. A rotating drought reduces production of one good every 600 rounds. Storage above 20 units per good is discarded before encounters.

Each agent attempts two trades per round. It samples a desired good with weight taste/(1+inventory)^2, offers its least valuable available alternative, and requests the desired good using a word from its own lexicon. A seller interprets that word using its own lexicon and available stock. A barter exchanges one unit each and happens only when both agents gain inventory utility. Goods and willingness to accept are observable; no agent can inspect another agent’s private vocabulary. Trade acceptance evaluates inventory utility before the buyer’s communication cost; a completed trade can therefore still earn a negative learning reward.

Four strategies compete: conventional speech, accommodation using previously heard successful regional words, explicit clarification through pointing, and a newly coined word. A successful grounded encounter strengthens the word in the listener’s lexicon. Unknown words can receive probabilistic pointing-based repair. New words are not automatically rewarded. Words decay, and each agent slot has a 0.0015 chance per round of cultural succession: a successor samples three local tutors, inherits physical resources, and resets strategy learning and social memory. Tutors can include the previous occupant. This is cultural turnover, not a demographic or survival model.

Learning is an epsilon-greedy contextual bandit (epsilon 0.12, learning rate 0.08), with separate local and remote action values. Reward is the buyer’s actual inventory utility gain minus communication effort. Conventional cost is 0.01; accommodation adds 0.025×(1−openness); innovation adds 0.04×(1−openness); clarification or repair adds 0.06. Learning optimizes the agent’s immediate reward, not a collective linguistic goal. Successful trades also update partner preference, which affects later partner sampling.

Initial cultural openness is 0.15, 0.50, or 0.85 in each vocabulary group. It affects the effort of accommodation and innovation, listener uptake, and the probability of repair. Successors inherit tutor-average openness plus bounded noise. This bundles several mechanisms into one synthetic attitude variable; it is not a validated measurement of culture.

## Timeline

| Phase | Share of run | Full-study rounds | Remote encounter probability | Allowed links |
|---|---:|---:|---:|---|
| Connected | 20% | 1–4,800 | 12% | All pairs |
| Fragmented | 45% | 4,801–15,600 | 1% where connected | 0↔1 and 3↔4; 2 and 5 completely isolated |
| Trade routes | 25% | 15,601–21,600 | 8% | Neighboring regions along a chain |
| Mass contact | 8% | 21,601–23,520 | 20% | All pairs |
| Dense contact | 2% | 23,521–24,000 | 45% | All pairs |

Round counts scale proportionally for smoke tests. Rounds have no mapping to historical years. Isolation is enforced by the simulator’s partner graph, not network namespaces. The audit checks actual event pairs against that graph.

## Controls and reproducibility

The full study uses seeds 476, 911, and 2026 for each of three conditions: **adaptive** (learned strategies and heterogeneous culture), **fixed** (uniform random strategies and heterogeneous culture), and **uniform** (learned strategies with effective openness fixed at 0.50). Production, initial conditions, succession draws, and the contact schedule are seeded. Conditions share exogenous seeds, but behavioral decisions consume different random draws and create different trajectories; they are not identical encounter-by-encounter counterfactuals. The fixed baseline still learns vocabulary and partner preferences. It disables only strategy-value learning.

The seeds were chosen before the full run. Three repetitions support exploratory comparisons, not strong statistical generalizations. All complete runs appear below, including unfavorable outcomes. Differences between adaptive and fixed estimate the effect of strategy learning relative to this particular random policy; differences between adaptive and uniform bundle attitude level, variation, and its modeled consequences.

## Per-run results

| Condition | Seed | Trades / encounters | Mean reward | Mean shortage | Final lexical distance |
|---|---:|---:|---:|---:|---:|
| adaptive | 476 | 4.330% | -0.00757 | 59.080% | 0.37920 |
| fixed | 476 | 3.639% | -0.02567 | 62.903% | 0.67028 |
| uniform | 476 | 4.388% | -0.00778 | 58.799% | 0.30705 |
| adaptive | 911 | 4.399% | -0.00763 | 58.809% | 0.34216 |
| fixed | 911 | 3.737% | -0.02524 | 62.501% | 0.66804 |
| uniform | 911 | 4.470% | -0.00749 | 58.425% | 0.28106 |
| adaptive | 2026 | 4.465% | -0.00757 | 59.001% | 0.39308 |
| fixed | 2026 | 3.776% | -0.02460 | 62.585% | 0.66773 |
| uniform | 2026 | 4.556% | -0.00680 | 58.536% | 0.28190 |

Shortage is the fraction of agent–good inventory cells below 0.5 units; it is not mortality. Lexical distance is the mean pairwise total-variation distance between normalized regional word distributions, averaged across six goods (0 identical, 1 disjoint). It measures form distributions, not mutual intelligibility. First-pass success below additionally requires seller stock and therefore mixes comprehension with resource availability.

## Matched comparisons and unwanted outcomes

### Adaptive minus fixed

| Metric | Mean difference | Per-seed differences |
|---|---:|---|
| trade_rate | +0.006807 | +0.006912, +0.006618, +0.006890 |
| mean_reward | +0.017579 | +0.018098, +0.017611, +0.017028 |
| mean_shortage | -0.036996 | -0.038228, -0.036921, -0.035840 |
| final_lexical_distance | -0.297201 | -0.291079, -0.325877, -0.274647 |

Adaptive reward was higher in 3/3 matched seeds. Mean reward difference was +0.017579. The advantage was consistent across these seeds, within this model only.

### Adaptive minus uniform

| Metric | Mean difference | Per-seed differences |
|---|---:|---|
| trade_rate | -0.000733 | -0.000579, -0.000712, -0.000908 |
| mean_reward | -0.000236 | +0.000212, -0.000145, -0.000774 |
| mean_shortage | +0.003767 | +0.002807, +0.003839, +0.004654 |
| final_lexical_distance | +0.081479 | +0.072148, +0.061104, +0.111184 |

Adaptive reward was higher in 1/3 matched seeds. Mean reward difference was -0.000236. This comparison did not show a consistent reward advantage.

Learning can raise net reward simply by reducing costly clarification rather than improving trade. Compare reward, trade rate, and shortages together. Cultural differences can also disappear through the tutor mechanism, and linguistic similarity need not imply an economically healthier society. No outcome was a pass/fail criterion except implementation integrity.

## Phase-level results

| Condition | Phase | Trade rate | First-pass success | Reward | Shortage | Remote fraction |
|---|---|---:|---:|---:|---:|---:|
| adaptive | connected | 5.684% | 18.609% | -0.00157 | 52.061% | 12.011% |
| adaptive | fragmented | 3.083% | 9.413% | -0.01289 | 66.377% | 0.667% |
| adaptive | trade_routes | 4.469% | 14.499% | -0.00653 | 58.592% | 7.999% |
| adaptive | mass_contact | 7.248% | 27.797% | 0.00109 | 43.162% | 19.951% |
| adaptive | dense_contact | 8.839% | 36.378% | 0.00335 | 29.030% | 44.959% |
| fixed | connected | 4.699% | 8.369% | -0.01977 | 57.533% | 12.011% |
| fixed | fragmented | 2.746% | 4.805% | -0.02990 | 68.033% | 0.667% |
| fixed | trade_routes | 3.779% | 6.225% | -0.02472 | 62.282% | 7.999% |
| fixed | mass_contact | 5.557% | 7.519% | -0.01664 | 52.420% | 19.951% |
| fixed | dense_contact | 7.630% | 9.580% | -0.01244 | 38.892% | 44.959% |
| uniform | connected | 5.784% | 19.504% | -0.00116 | 51.551% | 12.011% |
| uniform | fragmented | 3.117% | 9.805% | -0.01271 | 66.230% | 0.667% |
| uniform | trade_routes | 4.554% | 15.582% | -0.00644 | 58.131% | 7.999% |
| uniform | mass_contact | 7.441% | 30.131% | 0.00174 | 42.194% | 19.951% |
| uniform | dense_contact | 8.901% | 37.984% | 0.00335 | 28.253% | 44.959% |

## What changed across the contact timeline?

- **adaptive:** trade success averaged 5.68% during initial contact, 3.08% during fragmentation, and 8.84% during dense contact. Late-minus-fragmented shortage was -37.35 percentage points. Mean lexical distance changed from the first recorded snapshot (0.7932) to 0.3715 at the end.
- **fixed:** trade success averaged 4.70% during initial contact, 2.75% during fragmentation, and 7.63% during dense contact. Late-minus-fragmented shortage was -29.14 percentage points. Mean lexical distance changed from the first recorded snapshot (0.8072) to 0.6687 at the end.
- **uniform:** trade success averaged 5.78% during initial contact, 3.12% during fragmentation, and 8.90% during dense contact. Late-minus-fragmented shortage was -37.98 percentage points. Mean lexical distance changed from the first recorded snapshot (0.7905) to 0.2900 at the end.

Phase differences are descriptive: time, learning, drought, and succession change alongside connectivity. There is no continuous-contact control in this study, so these comparisons alone cannot isolate the causal effect of fragmentation or reconnection.


## Learned strategy use

| Condition | Phase | Conventional | Accommodation | Clarification | Innovation |
|---|---|---:|---:|---:|---:|
| adaptive | connected | 70.03% | 17.51% | 6.08% | 6.39% |
| adaptive | dense_contact | 68.66% | 20.08% | 6.05% | 5.21% |
| fixed | connected | 24.96% | 25.01% | 24.98% | 25.05% |
| fixed | dense_contact | 24.89% | 25.10% | 25.03% | 24.97% |
| uniform | connected | 74.74% | 14.54% | 5.85% | 4.88% |
| uniform | dense_contact | 72.01% | 17.54% | 5.87% | 4.57% |

## End-state regional differences

| Condition / seed | Regional utility (0 through 5) | Regional inherited openness |
|---|---|---|
| adaptive / 476 | 6.935, 6.855, 7.356, 4.645, 7.427, 6.513 | 0.146, 0.449, 0.756, 0.150, 0.483, 0.786 |
| fixed / 476 | 5.454, 5.430, 6.266, 3.811, 5.940, 5.630 | 0.146, 0.449, 0.756, 0.150, 0.483, 0.786 |
| uniform / 476 | 6.856, 6.779, 7.321, 4.420, 7.106, 6.071 | 0.146, 0.449, 0.756, 0.150, 0.483, 0.786 |
| adaptive / 911 | 6.295, 7.099, 7.948, 4.538, 7.468, 6.617 | 0.118, 0.424, 0.829, 0.166, 0.488, 0.855 |
| fixed / 911 | 5.591, 5.453, 6.401, 3.591, 5.873, 5.667 | 0.118, 0.424, 0.829, 0.166, 0.488, 0.855 |
| uniform / 911 | 6.935, 7.005, 7.746, 4.567, 7.415, 6.822 | 0.118, 0.424, 0.829, 0.166, 0.488, 0.855 |
| adaptive / 2026 | 7.298, 7.158, 7.052, 4.491, 7.489, 6.678 | 0.104, 0.692, 0.900, 0.140, 0.456, 0.834 |
| fixed / 2026 | 5.166, 6.488, 5.954, 3.478, 5.555, 5.749 | 0.104, 0.692, 0.900, 0.140, 0.456, 0.834 |
| uniform / 2026 | 6.912, 7.431, 7.171, 4.498, 7.464, 6.828 | 0.104, 0.692, 0.900, 0.140, 0.456, 0.834 |

## Final vocabulary examples

These are the highest-weight regional words for grain, water, timber, ore, cloth, and medicine. They are arbitrary labels, not natural-language utterances. Full word distributions remain in the local summaries.

| Condition / seed | Region | Grain | Water | Timber | Ore | Cloth | Medicine |
|---|---:|---|---|---|---|---|---|
| adaptive / 476 | 0 | nnara | poma | taku | sima | pane | sala |
| adaptive / 476 | 1 | nara | poma | taku | sepoku | pane | sala |
| adaptive / 476 | 2 | nnara | poma | taku | tuponi | pane | sala |
| adaptive / 476 | 3 | nnara | posetu | ntaku | sima | npane | nsala |
| adaptive / 476 | 4 | nnara | opoma | taku | sima | pane | sala |
| adaptive / 476 | 5 | nnara | poma | taku | psima | pane | sala |
| fixed / 476 | 0 | ninise | npoma | kusemi | rakula | kulatu | sala |
| fixed / 476 | 1 | ninise | npoma | mipomi | nirani | nipotu | minira |
| fixed / 476 | 2 | ninise | npoma | mipomi | tupomi | nipotu | sala |
| fixed / 476 | 3 | ninise | npoma | nirara | ramipo | ramimi | tumira |
| fixed / 476 | 4 | ninise | npoma | tukuku | tupomi | nipotu | minipo |
| fixed / 476 | 5 | ninise | npoma | sesepo | nikula | tumimi | sala |
| uniform / 476 | 0 | nnara | poma | taku | sima | pane | sala |
| uniform / 476 | 1 | nara | poma | taku | senise | pane | sala |
| uniform / 476 | 2 | nnara | poma | ptaku | sima | pane | sala |
| uniform / 476 | 3 | nnara | npoma | ntaku | sima | pane | nsala |
| uniform / 476 | 4 | nnara | poma | ptaku | sima | pane | sala |
| uniform / 476 | 5 | nnara | poma | ptaku | psima | pane | sala |
| adaptive / 911 | 0 | nnara | poma | taku | sima | pane | sala |
| adaptive / 911 | 1 | nnara | npoma | taku | sima | pane | sala |
| adaptive / 911 | 2 | nnara | npoma | taku | sima | pane | sala |
| adaptive / 911 | 3 | nnara | npoma | ntaku | sima | pane | nsala |
| adaptive / 911 | 4 | onara | npoma | ptaku | sima | pane | osala |
| adaptive / 911 | 5 | nnara | npoma | ptaku | sima | pane | sala |
| fixed / 911 | 0 | posera | miponi | lasemi | sima | larara | sala |
| fixed / 911 | 1 | posera | npoma | tumipo | tukumi | turapo | sala |
| fixed / 911 | 2 | posera | rakura | lakula | sima | sesela | sala |
| fixed / 911 | 3 | posera | npoma | lakula | tukumi | rarala | semitu |
| fixed / 911 | 4 | tukuni | npoma | rarapo | kulani | larara | tunira |
| fixed / 911 | 5 | mikuse | npoma | lamila | misetu | posemi | sala |
| uniform / 911 | 0 | pnara | npoma | taku | sima | pane | sala |
| uniform / 911 | 1 | nara | npoma | taku | sima | pane | sala |
| uniform / 911 | 2 | pnara | poma | ptaku | sima | pane | sala |
| uniform / 911 | 3 | pnara | npoma | ntaku | sima | pane | sala |
| uniform / 911 | 4 | pnara | npoma | ptaku | psima | pane | sala |
| uniform / 911 | 5 | pnara | npoma | ptaku | psima | pane | sala |
| adaptive / 2026 | 0 | nnara | poma | taku | sima | pane | sala |
| adaptive / 2026 | 1 | nnara | npoma | taku | sima | pane | sala |
| adaptive / 2026 | 2 | nnara | npoma | taku | sima | pane | kukumi |
| adaptive / 2026 | 3 | nnara | npoma | ntaku | sima | npane | nsala |
| adaptive / 2026 | 4 | onara | npoma | taku | sima | pane | osala |
| adaptive / 2026 | 5 | nnara | npoma | ptaku | ramimi | pane | nsala |
| fixed / 2026 | 0 | nnara | npoma | sekula | kukuku | tutura | nikuku |
| fixed / 2026 | 1 | nnara | npoma | mikupo | kukuku | pane | kupora |
| fixed / 2026 | 2 | nnara | npoma | lanimi | kukutu | pane | kupose |
| fixed / 2026 | 3 | nnara | npoma | semise | kukuku | pane | misela |
| fixed / 2026 | 4 | nnara | npoma | ninipo | mirami | pane | osala |
| fixed / 2026 | 5 | nnara | npoma | lanimi | lanipo | kutura | nikuku |
| uniform / 2026 | 0 | nnara | poma | taku | sima | pane | sala |
| uniform / 2026 | 1 | nara | npoma | taku | sima | pane | sala |
| uniform / 2026 | 2 | nara | mikula | ptaku | sima | pane | sala |
| uniform / 2026 | 3 | nnara | npoma | ntaku | sima | pane | sala |
| uniform / 2026 | 4 | nnara | npoma | ptaku | sima | pane | osala |
| uniform / 2026 | 5 | nnara | npoma | ptaku | psima | pane | sala |

The uniform treatment uses effective openness 0.50 throughout; its inherited openness above is recorded state but has no behavioral effect. Regional utility is a final snapshot; trajectories and phase averages are more informative about sustained welfare.

## Integrity and limitations

Each SQLite transaction commits a round’s encounters, summary, and checkpoint together. The report independently counts event rows, checks per-round counts and checkpoint completion, verifies resource balance from production/consumption/discard flows, checks logged trades and rewards against summaries, inspects forbidden contact pairs, and runs SQLite quick_check. Audit details and the model source hash are in metrics.json.

- adaptive/476: PASS; 5,760,000 events; resource residual -2.44e-09.
- fixed/476: PASS; 5,760,000 events; resource residual -2.48e-09.
- uniform/476: PASS; 5,760,000 events; resource residual -2.43e-09.
- adaptive/911: PASS; 5,760,000 events; resource residual -1.96e-09.
- fixed/911: PASS; 5,760,000 events; resource residual -2.04e-09.
- uniform/911: PASS; 5,760,000 events; resource residual -1.95e-09.
- adaptive/2026: PASS; 5,760,000 events; resource residual -2.24e-09.
- fixed/2026: PASS; 5,760,000 events; resource residual -2.31e-09.
- uniform/2026: PASS; 5,760,000 events; resource residual -2.2e-09.

There are no LLMs, grammar, identities, political institutions, migration, prices, credit, long-term planning, or observed human data in this version. Trade is one-for-one barter with a shared nonlinguistic representation of goods and pointing. Trust measures trading success, not human social trust. Single-word labels and a finite innovation space can converge by construction or accidental form collision. The language, economy, and openness rules were designed together and may strongly determine outcomes. A causal claim is therefore limited to interventions inside this program.

Further tests should independently vary production geography, repair availability, innovation cost, tutor count, strategy exploration, and each attitude mechanism. Add an always-conventional policy and no-trade control before claiming reinforcement is necessary. Calibrate against empirical data before making a sociolinguistic or historical claim.

## Artifacts and reproduction

metrics.json contains every condition/seed summary, phase statistics, audit checks, and 200-round trajectories. trajectories.png shows individual seeds, not just a selected run. Raw SQLite ledgers remain on the experiment machine and are excluded from Git because of their size. Re-run with the command in the project README. The simulator source hash is recorded per run; a changed model cannot silently resume an old ledger.

![Individual-seed trajectories](trajectories.png)
