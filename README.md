# Lingua Franca

If speakers start with the same language, do local dialects emerge when their
communities stop talking to one another? What happens when contact returns?

**In this run, some local words emerged, but the communities stayed mutually
intelligible.** At the end of isolation, speakers understood 98.85% of requests
from other groups on the first attempt, compared with 98.99% under sustained
contact. After reconnection the scores were 99.14% and 99.18%. Lexical divergence
was greater under isolation in four of eight paired seeds. The notebook shows
all eight, including the cases that went the other way. [Executed results notebook](results.ipynb)

## The experiment

Three groups of twelve speakers start with the same twelve nouns, the actions
*give* and *show*, and verb–object order (*give taku* means “give stone”).
Speakers choose words and word order from their own learned preferences. They
occasionally coin a noun or reverse the order. A listener tries to interpret
the request; pointing and demonstrating the action can repair a misunderstanding.
A grounded encounter reinforces the word and construction. A speaker can later
accommodate someone by using a form heard from that person's group. Successors
learn from a finite sample of three local tutors.

After 20 shared rounds, each seed's population is copied. In the control, each
encounter has a 25% chance of drawing a speaker from another group. In the
other copy, that chance drops to zero for 160 rounds, then returns to 25% for
80 rounds. Each listener has four encounters per round in both copies. All
groups use the same innovation and learning rules.

At the split and both endpoints, we compare group word-use and word-order
distributions. A separate listening test samples every cross-group direction
equally, even during isolation. It scores the intended action **and** object on
the first attempt. Test encounters never change a speaker's knowledge.

For example, one group in the first seed learned *sesetu* for salt alongside
the founding *sala*. At the end of isolation, its speakers had a 10.5% average
chance of saying *sesetu*; nobody in the other two groups had it in their
learned vocabulary. After reconnection its share was 13.7% in the first group
and 4.4% in the second. Another local word, *sekumi* for cup, faded from 12.3%
to 0.9% in its home group. These were the two most regionally concentrated
variants in that seed, selected to illustrate what the aggregate measures count.

## Reproduce it

[simulation.py](simulation.py) uses only the Python standard library.
[config.json](config.json) contains the rates, phase lengths, and seeds used for
the published run. Open [results.ipynb](results.ipynb) in Jupyter with a Python 3
kernel and run all cells from the repository root. The saved notebook also reads
directly on GitHub.

## Recovery from the original implementation

The core comes from the weighted production, interpretation, learning, memory
decay and three-tutor acquisition rules in the original communication game.
The only audience-specific rule comes from the original trade model: remember
a grounded word heard from a group and sometimes reuse it with that audience.
Here a fixed probability selects accommodation. Partner choice is uniform
within the selected local or remote pool. Individuals stay in their group.
The recovery omits prestige weighting, economic rewards, regional starting
variants and island-specific sound substitutions.
[Original game](https://github.com/Colton-Cogg-1999/Lingua-Franca/blob/cfc6471/galapagos/game.py) ·
[Original accommodation rule](https://github.com/Colton-Cogg-1999/Lingua-Franca/blob/cfc6471/galapagos/society.py#L98-L102) ·
[Archived pre-recovery project](https://github.com/Colton-Cogg-1999/Lingua-Franca/tree/archive/before-recovery)
