"""Audit each seed, export its measurements, and draw the completed study."""

import argparse
import csv
import gzip
import io
import json
import statistics
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from run import HISTORIES, audit, records

TOWNS = ("Tarraco", "Narbo", "Massilia", "Genua", "Roma", "Neapolis")
MEANINGS = "water bread fire salt boat road stone moon fish hand rain sun barley wool oil wine house door net rope dog goat bird bee".split()


def pronounce(n):
    consonants, vowels = "ptkbdgmnsl", "aeiou"
    return (
        consonants[n // 250]
        + vowels[n // 50 % 5]
        + consonants[n // 5 % 10]
        + vowels[n % 5]
    )


@contextmanager
def compressed(path):
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz,
    ):
        with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
            yield csv.writer(text, lineterminator="\n")


def write_figure(rows, manifest, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(9, 6.8), sharex=True, layout="constrained")
    split, reopen = manifest["shared_rounds"], manifest["reopen_after"]
    colors = {"breakup": "#a34325", "open": "#176762", "sealed": "#665391"}
    styles = {"breakup": "-", "open": "--", "sealed": ":"}
    common = sorted(t for h, t in rows if h == "common")
    for ax, key, title in zip(
        axes,
        ("recognition", "shared_form"),
        (
            "Understanding a speaker from another province",
            "Using the same word for the same meaning",
        ),
    ):
        ax.axvspan(split, reopen, color="#f2ebe2")
        for h in HISTORIES:
            xs = common + sorted(t for history, t in rows if history == h)
            data = [rows["common" if t <= split else h, t][key] for t in xs]
            positions = (
                range(len(data))
                if h == "breakup"
                else range(len(common) - 1, len(data))
            )
            x = [xs[i] for i in positions]
            y = [100 * statistics.mean(data[i]) for i in positions]
            lo, hi = [], []
            for i in positions:
                q = (
                    statistics.quantiles(data[i], n=10, method="inclusive")
                    if len(data[i]) > 1
                    else data[i] * 9
                )
                lo.append(q[0] * 100)
                hi.append(q[-1] * 100)
            ax.fill_between(x, lo, hi, color=colors[h], alpha=0.09)
            ax.plot(
                x,
                y,
                styles[h],
                lw=2.4,
                color=colors[h],
                label={
                    "breakup": "Empire breaks up",
                    "open": "Open roads",
                    "sealed": "Sealed borders",
                }[h],
            )
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
        ax.set_ylabel("Percent")
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["right", "top"]].set_visible(False)
    axes[0].legend(frameon=False, ncols=3)
    axes[1].set_xlabel("Conversation round   ·   shaded period: contact restrictions")
    fig.suptitle("Speech across the provinces", fontsize=17, fontweight="bold")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.input / "manifest.json").read_text())
    probes = defaultdict(lambda: defaultdict(list))
    totals = defaultdict(int)
    with (
        compressed(out / "intervals.csv.gz") as intervals,
        compressed(out / "routes.csv.gz") as routes,
    ):
        for seed in range(1, manifest["seeds"] + 1):
            directory = args.input / f"seed-{seed:04d}"
            config = json.loads((directory / "config.json").read_text())
            if config != dict(
                seed=seed,
                model_sha256=manifest["model_sha256"],
                per_town=manifest["per_town"],
                rounds=manifest["rounds"],
            ):
                raise ValueError(f"Run metadata mismatch in {directory}")
            audit(directory, config["per_town"], config["rounds"])
            rows = records(directory / "intervals.csv")
            if seed == 1:
                intervals.writerow(["seed", *rows[0]])
            for r in rows:
                intervals.writerow([seed, *r.values()])
                for key in (
                    "conversations",
                    "understood",
                    "remote",
                    "repairs",
                    "adoptions",
                    "coins",
                    "births",
                ):
                    totals[key] += int(r[key])
                block = probes[r["history"], int(r["round"])]
                for field, numerator, denominator in [
                    ("recognition", "remote_probe_hits", "remote_probes"),
                    ("shared_form", "same_remote_form", "remote_probes"),
                    ("local_recognition", "local_probe_hits", "local_probes"),
                ]:
                    block[field].append(int(r[numerator]) / int(r[denominator]))
            matrix = records(directory / "routes.csv")
            if seed == 1:
                routes.writerow(["seed", *matrix[0]])
            routes.writerows([seed, *r.values()] for r in matrix)
    if totals["conversations"] != manifest["conversations"]:
        raise ValueError("Manifest and audited counts disagree")
    endpoints = {
        t: {
            h: {k: statistics.mean(v) for k, v in probes[h, t].items()}
            for h in HISTORIES
        }
        for t in (manifest["reopen_after"], manifest["rounds"])
    }
    t = manifest["reopen_after"]
    paired = [
        a - b
        for a, b in zip(
            probes["breakup", t]["recognition"],
            probes["open", t]["recognition"],
            strict=True,
        )
    ]
    result = dict(
        **manifest,
        totals=dict(totals),
        end_of_common={
            k: statistics.mean(v)
            for k, v in probes["common", manifest["shared_rounds"]].items()
        },
        endpoints=endpoints,
        breakup_minus_open_at_reopening=dict(
            mean=statistics.mean(paired), negative_seeds=sum(x < 0 for x in paired)
        ),
    )
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    example = args.input / "seed-0001"
    with (out / "water-lineages.csv").open("w", newline="") as f:
        source = records(example / "trace.csv")
        fields = (
            "round",
            "lineage",
            "speaker",
            "listener",
            "speaker_town",
            "listener_town",
            "word",
            "coined",
            "understood",
            "repaired",
            "adopted",
        )
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for r in source:
            r["word"] = pronounce(int(r.pop("form")))
            for side in ("speaker_town", "listener_town"):
                r[side] = TOWNS[int(r[side])]
            writer.writerow(r)
    with (out / "example-vocabulary.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(
            (
                "history",
                "round",
                "town",
                "meaning",
                "most_common_word",
                "speakers_using_it",
                "speakers_in_town",
            )
        )
        for r in records(example / "vocabulary.csv"):
            writer.writerow(
                (
                    r["history"],
                    r["round"],
                    TOWNS[int(r["town"])],
                    MEANINGS[int(r["meaning"])],
                    pronounce(int(r["modal_form"])),
                    r["speakers"],
                    r["total"],
                )
            )
    write_figure(probes, manifest, out / "provinces.png")
    print(
        f"{manifest['seeds']} seeds audited; {totals['conversations']:,} conversations"
    )


if __name__ == "__main__":
    main()
