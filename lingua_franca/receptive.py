"""Reconnection experiment with separate receptive vocabulary and spoken forms."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from . import contact as pilot

VOCAB_SHAPE = (pilot.REGIONS, pilot.MEANINGS)
SLOTS, LIFETIME = 3, 8
NETWORKS = ("restored", "restricted")
ADOPTIONS = {"full": 1.0, "selective": 0.25}
METRICS = ("spoken_only", "with_memory", "sound_distance", "shared_root")


class Memory:
    def __init__(self):
        self.forms = np.zeros((*VOCAB_SHAPE, SLOTS, 4), dtype=np.int8)
        self.forms[...] = pilot.LOW
        self.heard = np.full((*VOCAB_SHAPE, SLOTS), -LIFETIME, dtype=int)

    def learn(self, forms, foreign, generation):
        region, meaning = np.nonzero(foreign)
        oldest = self.heard[region, meaning].argmin(axis=-1)
        self.heard[region, meaning, oldest] = generation
        self.forms[region, meaning, oldest] = forms[region, meaning]


def advance(previous, memory, seed, generation, network, adoption):
    # Match the pilot's tutor, replacement and sound-change streams exactly.
    rng = np.random.default_rng([seed, generation])
    exposure = rng.random(VOCAB_SHAPE)
    choice = rng.random(VOCAB_SHAPE)
    if network == "restored":
        foreign = exposure < 0.25
        neighbor = (
            pilot.REGION + 1 + (choice * (pilot.REGIONS - 1)).astype(int)
        ) % pilot.REGIONS
    else:
        foreign = exposure < 0.05
        neighbor = pilot.REGION + np.where(choice < 0.5, -1, 1)
        neighbor[0], neighbor[-1] = 1, pilot.REGIONS - 2
    tutor = np.where(foreign, neighbor, pilot.REGION)
    memory.learn(previous.sounds[tutor, pilot.MEANING], foreign, generation)
    adoption_rng = np.random.default_rng([seed, generation, 1])
    copied = foreign & (adoption_rng.random(VOCAB_SHAPE) < adoption)
    model = np.where(copied, tutor, pilot.REGION)
    replace = rng.random(VOCAB_SHAPE) < 0.004
    coined = rng.integers(pilot.LOW, pilot.HIGH, size=(*VOCAB_SHAPE, 4), dtype=np.int8)
    new_roots = (
        pilot.MEANINGS
        + ((generation - 1) * pilot.REGIONS + pilot.REGION) * pilot.MEANINGS
        + pilot.MEANING
    )
    roots = np.where(replace, new_roots, previous.roots[model, pilot.MEANING])
    sounds = np.where(
        replace[:, :, None], coined, previous.sounds[model, pilot.MEANING]
    )
    return (
        pilot.Lexicon(roots, pilot.sound_change(sounds, rng, 0.45)),
        int(foreign.sum()),
        int(copied.sum()),
    )


def form_ids(forms):
    # Perfect encoding of the four CVCV positions in 0..2499.
    f = forms.astype(np.int32)
    return ((f[..., 0] * 5 + f[..., 1] - 10) * 10 + f[..., 2]) * 5 + f[..., 3] - 10


def distance_table():
    ids = np.arange(2500)
    positions = (ids // 250, ids // 50 % 5, ids // 5 % 10, ids % 5)
    return sum((p[:, None] != p).astype(np.uint8) for p in positions)


def recognition(distances):
    choices = distances == distances.min(axis=-1, keepdims=True)
    credit = np.diagonal(choices, axis1=-2, axis2=-1) / choices.sum(axis=-1)
    return credit.mean(axis=-1)


def probe(world, memory, generation, table):
    spoken = form_ids(world.sounds)
    # Invalid memory slots are masked before scoring.
    remembered = form_ids(memory.forms)
    available = generation - memory.heard < LIFETIME
    local_scores, memory_scores = [], []
    differences = shared_count = 0
    for listener in range(pilot.REGIONS):
        others = np.arange(pilot.REGIONS) != listener
        words = spoken[others, :, None]
        local = table[words, spoken[listener]]
        receptive = local.copy()
        for slot in range(SLOTS):
            matches = table[words, remembered[listener, :, slot]]
            receptive = np.minimum(
                receptive, np.where(available[listener, :, slot], matches, 5)
            )
        local_scores.extend(recognition(local))
        memory_scores.extend(recognition(receptive))
        same = world.roots[others] == world.roots[listener]
        shared_count += int(same.sum())
        differences += int(np.diagonal(local, axis1=-2, axis2=-1)[same].sum())
    pairs = pilot.REGIONS * (pilot.REGIONS - 1) * pilot.MEANINGS
    return (
        np.mean(local_scores),
        np.mean(memory_scores),
        differences / (4 * shared_count) if shared_count else np.nan,
        shared_count / pairs,
    )


def observations(seed, table):
    split = pilot.initial_world(seed)
    for generation in range(1, pilot.RECONNECT + 1):
        split, _ = pilot.transmit(split, seed, generation, "fragmented")
    for network in NETWORKS:
        for policy, adoption in ADOPTIONS.items():
            world, memory = split, Memory()
            exposures = copies = 0
            for generation in range(pilot.RECONNECT, pilot.END + 1):
                if generation > pilot.RECONNECT:
                    world, heard, adopted = advance(
                        world, memory, seed, generation, network, adoption
                    )
                    exposures += heard
                    copies += adopted
                if generation % 5 == 0:
                    scores = probe(world, memory, generation, table)
                    yield (
                        seed,
                        network,
                        policy,
                        generation,
                        exposures,
                        copies,
                        *scores,
                    )


def summarize(rows):
    samples = {}
    for _, network, policy, gen, _, _, *scores in rows:
        samples.setdefault((network, policy, gen), []).append(scores)
    samples = {key: np.array(values) for key, values in samples.items()}
    selective = samples["restored", "selective", pilot.END]
    differences = {
        "restore_contact": selective[:, 1]
        - samples["restricted", "selective", pilot.END][:, 1],
        "use_receptive_memory": selective[:, 1] - selective[:, 0],
        "distance_with_selective_adoption": selective[:, 2]
        - samples["restored", "full", pilot.END][:, 2],
        "recognition_change_since_split": selective[:, 1]
        - samples["restored", "selective", pilot.RECONNECT][:, 1],
    }
    indices = np.random.default_rng(2026).integers(
        len(pilot.SEEDS), size=(10000, len(pilot.SEEDS))
    )
    contrasts = {}
    for name, delta in differences.items():
        intervals = np.quantile(delta[indices].mean(axis=1), [0.025, 0.975])
        contrasts[name] = {
            "mean": delta.mean(),
            "interval": intervals.tolist(),
            "positive_seeds": int((delta > 0).sum()),
        }
    return samples, contrasts


def plot(samples, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), sharey=True, layout="constrained")
    gens = list(range(pilot.RECONNECT, pilot.END + 1, 5))
    for ax, network in zip(axes, NETWORKS):
        for k, label, color in (
            (1, "Spoken + remembered", "#216980"),
            (0, "Spoken only", "#ad5524"),
        ):
            ax.plot(
                gens,
                [100 * samples[network, "selective", g][:, k].mean() for g in gens],
                marker="o",
                ms=3,
                color=color,
                label=label,
            )
        ax.set_title(f"{network.capitalize()} contact\nWord recognition", loc="left")
    for policy, color in (("selective", "#6c528f"), ("full", "#65737a")):
        axes[2].plot(
            gens,
            [100 * samples["restored", policy, g][:, 2].mean() for g in gens],
            marker="o",
            ms=3,
            color=color,
            label=f"{policy.capitalize()} adoption",
        )
    axes[2].set_title("Restored contact\nPronunciation distance", loc="left")
    for ax in axes:
        ax.legend(frameon=False, fontsize=8)
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("Generation")
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("Percent")
    fig.suptitle(
        "Listening and speaking after fragmentation", fontsize=15, fontweight="bold"
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    table = distance_table()
    rows = [row for seed in pilot.SEEDS for row in observations(seed, table)]
    samples, contrasts = summarize(rows)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "trajectories.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "seed",
                "network",
                "adoption",
                "generation",
                "cumulative_foreign_exposures",
                "cumulative_foreign_copies",
                *METRICS,
            )
        )
        writer.writerows(rows)
    sources = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__), Path(pilot.__file__))
    }
    (output / "summary.json").write_text(
        json.dumps(
            {"sources": sources, "seeds": pilot.SEEDS, "contrasts": contrasts}, indent=2
        )
        + "\n"
    )
    plot(samples, output / "reconnection.png")


if __name__ == "__main__":
    main()
