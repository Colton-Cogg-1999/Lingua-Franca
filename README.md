# Lingua Franca

Watch a dialect form. Six towns around an imaginary Roman Mediterranean start
with the same vocabulary. Then the empire breaks up. What happens to the word
for *water* when most of the people you hear live in your own town?

## Play the dialect atlas

Open **[dialects.html](docs/dialects.html)** from your checkout in a browser and
press **Play**. The file works offline. If you’re on GitHub, use **Download raw file**
on that page, then open the downloaded file.

Pick a word, drag through the generations, and click any town’s pronunciation
to follow its history. The three societies start with the same towns and words.

| Society | When the empire breaks up |
|---|---|
| The empire falls | Most learning becomes local. Neighboring towns still exchange words. |
| Open roads | People keep hearing tutors from across the empire. |
| Closed borders | Each town learns entirely from its own people. |

The roads reopen after generation 50. Try **water** at generation **35**: in
the fractured empire, Roma says *pesa* and Genua says *tego*. In the open-roads
world both say *pilu*. The sounds and words are invented. The town names give
you somewhere to follow them.

To grow a different world, choose another seed and open the file it generates.

```sh
python -m pip install -e '.[analysis]'
python -m lingua_franca.explore --seed 911 --output runs/my-dialects.html
```

<details>
<summary>Earlier experiments, results, and reproduction instructions</summary>

## Understanding neighbors after reconnection

When communities heard more foreign speech but adopted only a quarter of foreign
tutors’ forms, word recognition rose from **14.4% to 34.6%** over 30 generations.
Listeners using only their own spoken vocabulary scored **17.6%** on those same
utterances. Pronunciations remained distinct across regions even among words
that shared a root. [Follow-up results and figure](docs/results/receptive-vocabulary/report.md)

## Roman fragmentation pilot

Across 24 matched worlds, listeners recognized **14.4%** of words from another
region after 40 generations of fragmented contact, versus **43.7%** under
sustained contact. In the fragmented worlds, **76.5%** of same-meaning word
pairs still shared a root. After 30 generations of renewed contact, the
recognition gap narrowed to 0.75 percentage points. The model tests a contact
mechanism suggested by Roman history. Its rates are synthetic.

[Results and figure](docs/results/contact-pilot/report.md) ·
[Experimental design](docs/results/contact-pilot/design.md)

## Earlier trade and communication study

How does learning what to say affect trade and shared vocabulary? Lingua Franca is a
Python simulation of six communities that barter for goods. A buyer requests a good
using a word it knows. The seller interprets the request using its own vocabulary and
available stock. Pointing can resolve a misunderstanding, at a cost to the buyer.

### Findings

Across three matched seeds, agents that learned which speaking strategy to use
completed **4.40% of attempted trades**, compared with **3.72%** for agents choosing
a strategy at random. Both groups could learn words. The adaptive agents also had
fewer shortages (58.96% versus 62.66%) and ended with more similar regional
vocabularies (mean lexical distance 0.3715 versus 0.6687). Average buyer reward
improved but remained negative after communication costs.

Giving all adaptive agents the same effective openness yielded a trade rate of
4.47% and a final lexical distance of 0.2900. Varying openness across agents gave a
higher mean reward in only one of the three matched seeds. The evidence concerns
these simulated communities. Lexical similarity measures shared word use, and
first-pass success also depends on whether the seller has the item in stock.

The completed study covers nine runs, 216,000 rounds, and 51,840,000 encounters.
The report includes the paired differences, contact phases, and ledger audits.
[Study report](docs/results/lingua-franca/report.md) ·
[Metrics by run](docs/results/lingua-franca/metrics.json) ·
[Individual trajectories](docs/results/lingua-franca/trajectories.png)

### Run one experiment

From the checkout, run this with Python 3.11 or newer. The simulator uses the
standard library. Its disk-space guard requires 20 GiB free on the output volume.

```sh
python -m lingua_franca.society --output runs/example --rounds 100 --population 4 --seed 476
```

Here, `--population 4` means four agents per community, or 24 total. Every round
gives each agent two opportunities to trade. SQLite commits the encounters,
summary, and checkpoint together. To resume, repeat the command with the same
settings and model. Give each concurrent writer its own output directory.

Inspect trade success and net reward by speaking strategy using the SQLite CLI.

```sh
sqlite3 -readonly runs/example/ledger.sqlite \
  'SELECT strategy, count(*), avg(traded), avg(reward) FROM events GROUP BY strategy;'
```

### Reproduce the study

The defaults run three conditions for each seed (476, 911, and 2026), with 20
agents per community and 24,000 rounds per run. The saved ledgers for the
completed study occupy about 4.1 GiB. Install the analysis extra to generate the figure.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[analysis]'
python -m lingua_franca.study --output runs/full-study
```

The runner writes logs, a manifest, and progress to the output directory. After
the last run it audits the ledgers and writes `report/report.md`, `metrics.json`,
and the figure in that report directory. To regenerate the report from saved
ledgers, point the reporter at the directory containing `manifest.json`.

```sh
python -m lingua_franca.report --root runs/full-study --output runs/full-study/report
```

On Linux, `tools/societyctl start` runs the study as a user service capped at one
CPU core and 2 GiB of memory. It uses the checkout’s `.venv` and writes under
`runtime/lingua-franca-study/`. Use `status`, `logs`, or `stop` to manage it.

### How the model works

- **Trade.** Agents specialize in production, consume six goods, and face a rotating
  drought. A one-for-one barter goes through when both parties gain inventory
  utility. The buyer pays communication effort even when a trade fails.
- **Communication.** The buyer can use a familiar word, reuse a word learned from
  another region, point explicitly, or coin a word. Successful interpretation can
  teach the seller a word even if the barter falls through.
- **Learning.** Adaptive agents learn a separate value for each strategy in local
  and cross-region encounters. The reward is immediate buyer utility gain less
  effort. The random-strategy baseline still learns words and partner preferences.
- **Contact and succession.** Regions pass through connected, fragmented, trade-route,
  mass-contact, and dense-contact phases. During succession, agents inherit physical
  goods and learn from three local tutors. Openness affects the cost of unfamiliar
  strategies, uptake of words, and the chance of repair.

Three communities start with variants of a shared vocabulary. Each of the other
three has its own starting vocabulary. Agents explore strategies on 12% of adaptive
decisions and update their values at a learning rate of 0.08. Each round gives an
agent a 0.15% chance of cultural succession. A drought shifts to the next good
every 600 rounds.

| Phase | Share of rounds | Chance of a cross-region encounter | Permitted contacts |
|---|---:|---:|---|
| Connected | 20% | 12% | All region pairs |
| Fragmented | 45% | 1% where linked | Regions 0–1 and 3–4 can trade. Regions 2 and 5 are isolated. |
| Trade routes | 25% | 8% | Neighbors along the chain from region 0 to region 5 |
| Mass contact | 8% | 20% | All region pairs |
| Dense contact | 2% | 45% | All region pairs |

The study compares strategy learning with a random policy. Establishing that
learning is *necessary* would require another baseline, such as always using a
familiar word. Isolating the effect of fragmentation would require a matched
continuous-contact control.

</details>

## Tests

```sh
python -m unittest discover -s tests
```
