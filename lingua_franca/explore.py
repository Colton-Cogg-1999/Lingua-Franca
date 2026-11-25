"""Make a self-contained, playable word atlas from a seeded contact simulation."""

import argparse
import json
from pathlib import Path

from . import contact

# Readable display symbols and glosses for the model's abstract sound/meaning IDs.
SOUNDS = "ptkbdgmnslaeiou"
MEANINGS = (
    "water bread fire salt boat road stone moon fish hand rain sun"
    " barley wool oil wine house door net rope dog goat bird bee"
    " night wind hill sea mother child eye foot tree leaf river shore"
    " pot cart knife star"
).split()
WORLDS = ("fragmented", "sustained", "isolated")


def make_atlas(seed):
    dictionary = []
    entries = {}

    def snapshot(state):
        towns = []
        for words, roots in zip(state.sounds, state.roots, strict=True):
            town = []
            for sounds, root in zip(words, roots, strict=True):
                key = ("".join(SOUNDS[s] for s in sounds), int(root))
                if key not in entries:
                    entries[key] = len(dictionary)
                    dictionary.append(key)
                town.append(entries[key])
            towns.append(town)
        return towns

    start = contact.initial_world(seed)
    common = [snapshot(start)]
    for generation in range(1, contact.SPLIT + 1):
        start, _ = contact.transmit(start, seed, generation, "sustained")
        common.append(snapshot(start))
    histories = {}
    for branch in WORLDS:
        state = start
        histories[branch] = []
        for generation in range(contact.SPLIT + 1, contact.END + 1):
            state, _ = contact.transmit(state, seed, generation, branch)
            histories[branch].append(snapshot(state))
    return dict(
        seed=seed,
        meanings=MEANINGS,
        words=dictionary,
        common=common,
        histories=histories,
        split=contact.SPLIT,
        reconnect=contact.RECONNECT,
        end=contact.END,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=476)
    parser.add_argument("--output", type=Path, default=Path("dialects.html"))
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("seed must be nonnegative")
    data = json.dumps(make_atlas(args.seed), separators=(",", ":"))
    template = Path(__file__).with_name("atlas.html").read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace("<!--WORLD-->", data), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
