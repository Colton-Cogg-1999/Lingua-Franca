# Understanding a word and adopting its pronunciation

## Paired design

This follow-up starts at the end of fragmentation in the first pilot. Reconstruct
the generation-50 spoken vocabularies for seeds 1–24 using the published model.
For each seed, copy that same state into four worlds. Run 30 more generations.
At the split, all listeners know only their local spoken forms.

| Intervention | Levels |
|---|---|
| Future contact | Restore 25% cross-region exposure across all regions, or continue 5% exposure along neighboring links |
| Adoption in speech | Copy every foreign tutor, or copy a foreign tutor with 25% probability and otherwise retain the local form |

Keep one tutor exposure per region, meaning, and generation. Keep replacement,
sound change, and the random draws for contacts paired. On every foreign
exposure the listener hears the tutor's previous-generation form and learns its
meaning from context. Local sound changes affect production. The receptive
vocabulary stores the last three foreign exposures per meaning for at most eight
generations, with the oldest overwritten when full. These limits and rates are
assumptions. The memory belongs to the community and can survive cohort turnover.

Score the same utterances twice in every world. One listener can use only current
local pronunciations. The other can also use stored examples. Each meaning's
score is its closest sound match across available examples, with ties split
between meanings. The test covers all 40 meanings for each ordered region pair.
It supplies no learning, cues, root labels, or information about the speaker's
region. Memory has no effect on speaking decisions. This allows an exact
within-world comparison of listening rules.

## Planned comparisons

At generation 80, evaluate the following differences in percentage points,
pairing outcomes within seed and weighting seeds equally.

1. **Primary.** Under selective adoption with receptive memory, how much does
   restoring contact improve recognition versus continuing fragmentation?
2. Within the restored, selective-adoption world, how much does access to
   remembered pronunciations contribute to recognition?
3. Under restored contact, how much more pronunciation distance survives with
   selective adoption versus full adoption? Use the fraction of differing sound
   positions for words sharing a root, as in the first pilot. Also record the
   proportion of same-meaning words sharing a root.

Use five percentage points as the practical benchmark for each contrast and
report 95% paired percentile bootstrap intervals (10,000 seed resamples).
Comparisons 2 and 3 explain the mechanism. Intervals are marginal and reflect
simulation-seed uncertainty. Also report change from the split: a benefit
relative to continued fragmentation alone does not establish absolute recovery.
Report all arms even if an effect is small or reverses. The model is synthetic
and does not estimate a historical rate of change.
