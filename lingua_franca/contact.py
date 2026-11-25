"""Paired contact-network experiment on the transmission of regional vocabularies."""

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import NamedTuple

import numpy as np

REGIONS, MEANINGS = 6, 40
SPLIT, RECONNECT, END = 10, 50, 80
SEEDS = tuple(range(1, 25))
BRANCHES = ("sustained", "fragmented", "isolated")
METRICS = ("comprehension", "shared_root", "sound_distance")
REGION = np.arange(REGIONS)[:, None]
MEANING = np.arange(MEANINGS)
# Sound IDs 0–9 are consonants and IDs 10–14 are vowels.
LOW = (0, 10, 0, 10)
HIGH = (10, 15, 10, 15)


class Lexicon(NamedTuple):
    roots: np.ndarray
    sounds: np.ndarray


def sound_change(forms, rng, probability):
    active = rng.random(REGIONS) < probability
    source = rng.integers(15, size=REGIONS)
    base = np.where(source < 10, 0, 10)
    alphabet = np.where(source < 10, 10, 5)
    target = base + (source - base + rng.integers(1, alphabet)) % alphabet
    affected = active[:, None, None] & (forms == source[:, None, None])
    return np.where(affected, target[:, None, None], forms).astype(np.int8)


def initial_world(seed):
    rng = np.random.default_rng([seed, 0])
    # Sample without replacement so the ancestral inventory has no homophones.
    codes = rng.choice(2500, MEANINGS, replace=False)
    forms = np.stack(
        (codes // 250, 10 + codes // 50 % 5, codes // 5 % 10, 10 + codes % 5), axis=-1
    )
    shape = (REGIONS, MEANINGS)
    return Lexicon(
        np.broadcast_to(MEANING, shape).copy(),
        sound_change(np.broadcast_to(forms, (*shape, 4)), rng, 1.0),
    )


def transmit(previous, seed, generation, branch):
    # Reset to the same stream for each branch. Draw counts do not depend on contact.
    rng = np.random.default_rng([seed, generation])
    exposure = rng.random((REGIONS, MEANINGS))
    choice = rng.random((REGIONS, MEANINGS))
    if branch == "fragmented" and SPLIT < generation <= RECONNECT:
        neighbor = np.where(choice < 0.5, REGION - 1, REGION + 1)
        remote = neighbor
        remote[0] = 1
        remote[-1] = REGIONS - 2
        tutors = np.where(exposure < 0.05, remote, REGION)
    elif branch == "isolated" and SPLIT < generation <= RECONNECT:
        tutors = np.broadcast_to(REGION, exposure.shape)
    else:
        remote = (REGION + 1 + (choice * (REGIONS - 1)).astype(int)) % REGIONS
        tutors = np.where(exposure < 0.25, remote, REGION)
    replacements = rng.random(exposure.shape) < 0.004
    new_forms = rng.integers(LOW, HIGH, size=(*exposure.shape, 4), dtype=np.int8)
    new_roots = MEANINGS + ((generation - 1) * REGIONS + REGION) * MEANINGS + MEANING
    roots = np.where(replacements, new_roots, previous.roots[tutors, MEANING])
    forms = np.where(
        replacements[:, :, None], new_forms, previous.sounds[tutors, MEANING]
    )
    return Lexicon(roots, sound_change(forms, rng, 0.45)), int((tutors != REGION).sum())


def measure(world):
    """Score every ordered region pair independently of transmission."""
    rows = []
    for speaker in range(REGIONS):
        # Compare each utterance with every candidate meaning in each listener.
        mismatch = (
            world.sounds[speaker, :, None, :] != world.sounds[:, None, :, :]
        ).sum(axis=-1)
        best = mismatch == mismatch.min(axis=-1, keepdims=True)
        correct = np.diagonal(best, axis1=1, axis2=2) / best.sum(axis=-1)
        same_root = world.roots[speaker] == world.roots
        position_errors = np.diagonal(mismatch, axis1=1, axis2=2)
        for listener in range(REGIONS):
            if speaker != listener:
                shared = same_root[listener]
                rows.append(
                    (
                        speaker,
                        listener,
                        float(correct[listener].mean()),
                        int(shared.sum()),
                        int(position_errors[listener, shared].sum()),
                    )
                )
    return rows


def simulate(seed):
    state = initial_world(seed)
    observations = []
    contacts = []

    def record(label, gen, current):
        observations.extend((label, gen, *row) for row in measure(current))

    record("common", 0, state)
    for gen in range(1, SPLIT + 1):
        state, remote = transmit(state, seed, gen, "sustained")
        contacts.append(("common", gen, remote))
        if gen % 5 == 0:
            record("common", gen, state)
    for branch in BRANCHES:
        current = state
        for gen in range(SPLIT + 1, END + 1):
            current, remote = transmit(current, seed, gen, branch)
            contacts.append((branch, gen, remote))
            if gen % 5 == 0:
                record(branch, gen, current)
    return observations, contacts


def run(db):
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(source TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS probes(
            seed INTEGER, branch TEXT, generation INTEGER, speaker INTEGER, listener INTEGER,
            comprehension REAL, shared INTEGER, differences INTEGER,
            PRIMARY KEY(seed, branch, generation, speaker, listener));
        CREATE TABLE IF NOT EXISTS contacts(
            seed INTEGER, branch TEXT, generation INTEGER, remote INTEGER,
            PRIMARY KEY(seed, branch, generation));
    """)
    row = db.execute("SELECT source FROM metadata").fetchone()
    if row and row[0] != source:
        raise ValueError(
            "Source differs from this pilot ledger. Use a new ledger path."
        )
    with db:
        db.execute("INSERT OR IGNORE INTO metadata VALUES (?)", (source,))
    done = {row[0] for row in db.execute("SELECT DISTINCT seed FROM contacts")}
    for seed in SEEDS:
        if seed in done:
            continue
        probes, contacts = simulate(seed)
        with db:
            db.executemany(
                "INSERT INTO probes VALUES (?,?,?,?,?,?,?,?)",
                ((seed, *row) for row in probes),
            )
            db.executemany(
                "INSERT INTO contacts VALUES (?,?,?,?)",
                ((seed, *row) for row in contacts),
            )


def summarize(db, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(exist_ok=True, parents=True)
    rows = db.execute(
        """
        SELECT seed, branch, generation, avg(comprehension), avg(shared) / ?,
               sum(differences) / (4.0 * sum(shared))
        FROM probes GROUP BY seed, branch, generation ORDER BY seed, branch, generation
    """,
        (float(MEANINGS),),
    ).fetchall()
    with (output / "trajectories.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("seed", "branch", "generation", *METRICS))
        writer.writerows(rows)
    values = {
        (seed, branch, gen): np.array(metrics, dtype=float)
        for seed, branch, gen, *metrics in rows
    }

    def sample(branch, gen):
        return np.stack(
            [values[seed, "common" if gen <= SPLIT else branch, gen] for seed in SEEDS]
        )

    delta = (sample("fragmented", RECONNECT) - sample("sustained", RECONNECT))[:, 0]
    bootstrap = (
        np.random.default_rng(2026).choice(delta, (10000, len(delta))).mean(axis=1)
    )
    endpoints = {
        g: {b: sample(b, g).mean(axis=0).tolist() for b in BRANCHES}
        for g in (SPLIT, RECONNECT, END)
    }
    encounters = db.execute(
        "SELECT branch, SUM(remote), COUNT(*) * ? FROM contacts "
        "WHERE generation > ? AND generation <= ? GROUP BY branch",
        (REGIONS * MEANINGS, SPLIT, RECONNECT),
    ).fetchall()
    stats = dict(
        seeds=list(SEEDS),
        source=db.execute("SELECT source FROM metadata").fetchone()[0],
        metrics=METRICS,
        endpoints=endpoints,
        primary_mean=float(delta.mean()),
        primary_interval=np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        primary_negative_seeds=int((delta < 0).sum()),
        treatment_contacts={b: dict(remote=r, total=t) for b, r, t in encounters},
    )
    (output / "summary.json").write_text(json.dumps(stats, indent=2) + "\n")

    fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True, layout="constrained")
    generations = list(range(0, END + 1, 5))
    for i, (ax, title) in enumerate(
        zip(
            axes,
            (
                "Cross-region word comprehension",
                "Same meaning, shared root",
                "Sound positions differing among shared roots",
            ),
        )
    ):
        ax.axvspan(SPLIT, RECONNECT, color="#f1ede5")
        for b, color, style in zip(
            BRANCHES, ("#14647d", "#b15313", "#605489"), ("-", "--", ":")
        ):
            # Draw the common history once.
            xs = (
                generations
                if b == "sustained"
                else [g for g in generations if g >= SPLIT]
            )
            y = np.array([sample(b, g)[:, i] for g in xs])
            lo, hi = np.quantile(y, (0.1, 0.9), axis=1)
            ax.fill_between(xs, lo * 100, hi * 100, color=color, alpha=0.09)
            ax.plot(
                xs,
                y.mean(axis=1) * 100,
                style,
                color=color,
                lw=2.3,
                label=b.capitalize(),
            )
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_ylabel("Percent")
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["right", "top"]].set_visible(False)
    axes[0].legend(ncols=3, frameon=False)
    axes[-1].set_xlabel("Generation  ·  altered contact from generation 11 through 50")
    fig.suptitle(
        "Language change under three contact schedules", fontweight="bold", fontsize=15
    )
    fig.savefig(output / "contact.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.ledger.parent.mkdir(exist_ok=True, parents=True)
    with sqlite3.connect(args.ledger) as db:
        run(db)
        summarize(db, args.output)


if __name__ == "__main__":
    main()
