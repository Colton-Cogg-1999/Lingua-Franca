# Inside the provinces simulation

Each seed starts 512 individuals in each of Tarraco, Narbo, Massilia, Genua, Roma
and Neapolis, in that order along a chain. All speakers within a seed begin with
the same 24 distinct words. Each word has four sound positions, alternating
between ten consonants and five vowels. Speakers store one word they use and
one additional form they can understand for each meaning.

## A conversation

Each resident takes one turn as listener per round. The starting listener rotates
by a seeded random offset. A remote encounter selects a speaker in an allowed
province. In a local encounter, six times out of ten the speaker is drawn from
a circle of up to eight slots on either side of the listener. Other local
encounters can reach any other local resident. Slot neighbors stand in for
recurring social contacts. Updates take effect immediately, so somebody can use
a word they learned earlier in the same round.

The speaker requests one of 24 objects by name. The listener sees the target
and three distractors. Each object has the same chance of being the target.
Recognition succeeds when the word uniquely matches the target among those
four objects in the listener’s active or receptive vocabulary. There is no
credit for guessing. A failed attempt has a 55% chance of repair by pointing.
After a repair the listener can remember the form even if they keep saying
their own word. When the spoken forms differ, the chance of adopting the
speaker’s word is 34% following recognition and 12% following repair.

## Where variation comes from

- A speaker coins a new form with probability 1/4,000 per utterance. It gets a
  new lineage ID even if it happens to sound like an existing word. Adoption and
  inheritance copy the lineage along with the word.
- Every 40 rounds, each slot has an 8% chance of receiving a successor. Each
  successor has a new person ID, learns each word from one of two sampled local
  tutors from the previous population, and starts with empty receptive memory.
  The two sampled tutor slots can coincide.
- At the same round boundary, each province draws a sound position and a
  substitution. Around 30% of its residents apply it wherever the old sound
  occurs in that position across their vocabularies. They can still recognize
  the previous form. This introduces a local source of variation into all three
  histories. Its spread or disappearance depends on subsequent encounters.
  Word lineages survive these sound changes.

## Comparing histories

The first 10% of rounds are executed once. The engine copies the entire population
into three branches, including receptive memory and person IDs. For the next
60%, the breakup branch retains sparse neighboring links and the sealed branch
has no external contacts. All three use the open network for the final 30%.
Random draws for a conversation depend on the seed, round, and listener slot,
which keeps contact opportunities and exogenous events paired across branches.
Round numbers have no conversion to historical dates.

In the full run there were **256 independent starting populations**, **768 branch
histories** and **1,433,600 executed population rounds**. Multiplying the latter
by 3,072 listeners yields 4,404,019,200 conversations. Reporting the prefix
three times would inflate that count.

## Measurements and files

Every 5% of the run, a separate read-only probe samples 32 speaker/listener pairs
for each of 24 meanings and all 36 ordered province pairs. It uses a separate
random stream. A remote recognition score pools the 30 cross-province directions.
The same-form score checks whether speaker and listener would produce exactly
the same form for that meaning. A listening score can therefore exceed a
same-form score. Neither score is an estimate of human mutual intelligibility.

| File | Contents |
|---|---|
| `intervals.csv.gz` | Conversation, repair, adoption, innovation and succession counts during each interval, plus probe results at its endpoint. The `common` rows belong to all three histories. |
| `routes.csv.gz` | Actual counts for every ordered listener–speaker province pair in every interval of every seed, including zeros. Province indices follow the order in the first paragraph. |
| `example-vocabulary.csv` | Most frequent spoken form by meaning, province and snapshot for seed 1, with the number using it. Ties use the lower numeric form ID. |
| `water-lineages.csv` | Coinages and conversational adoptions for new water lineages in the breakup branch of seed 1 after the common period. Forms copied by children or changed locally first appear here if later spoken in a qualifying event. |
| `summary.json` | Exact event totals, model source fingerprint, mean endpoint scores and the paired breakup/open comparison. |

Every seed is written to a temporary directory, audited, and renamed into place.
The audit checks the event budget, round coverage, probe denominators, all 36 route
counts per interval, and forbidden contacts. Raw output is kept locally. The
reporter exports the audited counts for every seed and the full selected trace
without storing billions of individual rows.

```sh
python -m unittest discover -s tests
```
