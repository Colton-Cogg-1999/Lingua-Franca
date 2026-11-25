"""Audit and report completed Lingua Franca experiments, including null results."""

import argparse
import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .society import STRATEGIES, schedule


def read_run(directory):
    db = sqlite3.connect(
        f"{(directory / 'ledger.sqlite').resolve().as_uri()}?mode=ro", uri=True
    )
    config = json.loads(db.execute("SELECT config FROM metadata").fetchone()[0])
    rows = [
        json.loads(row[0])
        for row in db.execute("SELECT payload FROM summaries ORDER BY round")
    ]
    expected = config["rounds"] * config["population"] * 6 * 2
    count, lo, hi, trades, rewards, gains = db.execute(
        "SELECT count(*),min(round),max(round),sum(traded),sum(reward),sum(buyer_gain+seller_gain) FROM events"
    ).fetchone()
    bad_events = db.execute("""SELECT count(*) FROM events WHERE buyer=seller OR
        (traded=1 AND (buyer_gain<=0 OR seller_gain<=0 OR grounded!=1 OR requested=offered)) OR
        (traded=0 AND (abs(buyer_gain)>1e-10 OR abs(seller_gain)>1e-10))""").fetchone()[
        0
    ]
    topology_violations = 0
    # Independent inspection of the actual logged pairs, grouped to keep memory small.
    for n, source, target in db.execute(
        "SELECT round,source_region,target_region FROM events WHERE source_region!=target_region GROUP BY round,source_region,target_region"
    ):
        if target not in schedule(n, config["rounds"])[2][source]:
            topology_violations += 1
    checkpoint = db.execute("SELECT round,state FROM checkpoint WHERE id=1").fetchone()
    final_state = json.loads(checkpoint[1])
    actual_inventory = sum(sum(a["inventory"]) for a in final_state["agents"])
    expected_inventory = config["population"] * 6 * 12 + sum(
        r["produced"] - r["consumed"] - r["discarded"] for r in rows
    )
    checks = {
        "sqlite_integrity": db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
        "complete_rounds": [r["round"] for r in rows]
        == list(range(1, config["rounds"] + 1)),
        "event_count": count == expected,
        "checkpoint": checkpoint[0] == config["rounds"],
        "per_round_counts": (lo, hi) == (1, config["rounds"])
        and all(
            n == config["population"] * 12
            for (n,) in db.execute("SELECT count(*) FROM events GROUP BY round")
        ),
        "valid_events": bad_events == 0,
        "topology": topology_violations == 0,
        "resource_balance": abs(actual_inventory - expected_inventory) < 1e-6,
        "summary_trades": trades == sum(r["trades"] for r in rows),
        "summary_rewards": abs(
            rewards - sum(r["mean_reward"] * r["encounters"] for r in rows)
        )
        < 1e-5,
        "summary_gains": abs(gains - sum(r["total_trade_gain"] for r in rows)) < 1e-5,
    }
    db.close()
    phases = {}
    for phase in dict.fromkeys(r["phase"] for r in rows):
        subset = [r for r in rows if r["phase"] == phase]
        encounters = sum(r["encounters"] for r in subset)
        phases[phase] = {
            "rounds": len(subset),
            "encounters": encounters,
            "trade_rate": sum(r["trades"] for r in subset) / encounters,
            "first_success": sum(r["first_success"] for r in subset) / encounters,
            "mean_reward": sum(r["mean_reward"] * r["encounters"] for r in subset)
            / encounters,
            "shortage": statistics.mean(r["shortage"] for r in subset),
            "utility": statistics.mean(r["mean_utility"] for r in subset),
            "remote_rate": sum(r["remote"] for r in subset) / encounters,
            "strategies": {
                a: sum(r.get(a, 0) for r in subset) / encounters for a in STRATEGIES
            },
        }
    lex = [r for r in rows if "lexical_distance" in r]
    result = {
        "config": config,
        "audit": checks,
        "events": count,
        "trades": trades,
        "trade_rate": trades / count,
        "mean_reward": rewards / count,
        "trade_gain": gains,
        "mean_shortage": statistics.mean(r["shortage"] for r in rows),
        "final_lexical_distance": lex[-1]["lexical_distance"] if lex else None,
        "final_region_utility": rows[-1]["region_utility"],
        "final_region_openness": rows[-1]["region_openness"],
        "successions": sum(r.get("successions", 0) for r in rows),
        "learned_novel_form_events": sum(r.get("new_form_learned", 0) for r in rows),
        "resource_balance_error": actual_inventory - expected_inventory,
        "phases": phases,
    }
    # Aggregate trajectories without publishing the large event databases or private checkpoints.
    trajectory = []
    for start in range(0, len(rows), 200):
        block = rows[start : start + 200]
        n = sum(r["encounters"] for r in block)
        trajectory.append(
            {
                "round": block[-1]["round"],
                "trade_rate": sum(r["trades"] for r in block) / n,
                "mean_reward": statistics.mean(r["mean_reward"] for r in block),
                "shortage": statistics.mean(r["shortage"] for r in block),
                "utility": statistics.mean(r["mean_utility"] for r in block),
                "lexical_distance": next(
                    (
                        r["lexical_distance"]
                        for r in reversed(block)
                        if "lexical_distance" in r
                    ),
                    None,
                ),
                "conventional": sum(r.get("conventional", 0) for r in block) / n,
            }
        )
    dominant = []
    for region in range(6):
        words = []
        for good in range(6):
            counts = Counter()
            for agent in final_state["agents"]:
                if agent["region"] == region:
                    lexicon = agent["lexicon"][good]
                    mass = sum(lexicon.values())
                    for word, value in lexicon.items():
                        counts[word] += value / mass
            words.append(counts.most_common(1)[0][0])
        dominant.append(words)
    result["dominant_words"] = dominant
    result["trajectory"] = trajectory
    return result


def plot_trajectories(results, output):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(3, 2, figsize=(13, 12), constrained_layout=True)
        colors = {"adaptive": "#187bcd", "fixed": "#d56b20", "uniform": "#6f42a8"}
        for ax, key, label in zip(
            axes.flat,
            (
                "trade_rate",
                "mean_reward",
                "shortage",
                "utility",
                "lexical_distance",
                "conventional",
            ),
            (
                "Trade success fraction",
                "Mean net reward",
                "Shortage fraction",
                "Mean inventory utility",
                "Regional lexical distance",
                "Conventional strategy fraction",
            ),
        ):
            for r in results:
                points = [p for p in r["trajectory"] if p[key] is not None]
                ax.plot(
                    [p["round"] for p in points],
                    [p[key] for p in points],
                    color=colors[r["config"]["condition"]],
                    alpha=0.65,
                    lw=1,
                    marker="." if len(points) == 1 else None,
                    label=r["config"]["condition"],
                )
            for fraction in (0.2, 0.65, 0.9, 0.98):
                ax.axvline(
                    fraction * results[0]["config"]["rounds"],
                    color="gray",
                    ls=":",
                    lw=0.7,
                )
            ax.set(xlabel="Round", ylabel=label)
            ax.grid(alpha=0.15)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        fig.legend(unique.values(), unique.keys(), loc="outside upper center", ncol=3)
        fig.suptitle("Lingua Franca — individual seed trajectories", y=1.04)
        fig.savefig(output / "trajectories.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    except ImportError:
        return False


def generate(root, output):
    manifest = json.loads((root / "manifest.json").read_text())
    results = []
    groups = defaultdict(dict)
    for spec in manifest["runs"]:
        run = read_run(root / spec["name"])
        config = run["config"]
        run["audit"]["study_configuration"] = all(
            config[k] == manifest[k] for k in ("rounds", "population", "source")
        ) and all(config[k] == spec[k] for k in ("seed", "condition"))
        groups[spec["condition"]][spec["seed"]] = run
        results.append(run)

    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    passed = all(all(r["audit"].values()) for r in results)
    rounds = manifest["rounds"]
    events = sum(r["events"] for r in results)
    seeds = list(groups["adaptive"])
    lines = [
        "# Trade and communication in Lingua Franca",
        "",
        (
            f"{len(results)} runs covered {events:,} encounters. Each run followed six communities "
            f"of {manifest['population']} agents for {rounds:,} rounds. "
            f"The matched seeds were {', '.join(map(str, seeds))}."
        ),
        "",
        "**All ledger integrity checks passed.**"
        if passed
        else "**Some ledgers failed integrity checks. See the audit table before interpreting outcomes.**",
        "",
        "## What changed when agents learned a speaking strategy?",
        "",
        (
            "Every agent can learn words and update its preferences for trading partners. "
            "The adaptive condition also learns which speaking strategies pay off. "
            "The fixed condition samples the four strategies uniformly at random throughout the run. "
            "The uniform condition learns strategies with effective openness set to 0.50 for everyone."
        ),
        "",
        "| Condition | Encounters ending in trade | Mean buyer reward | Mean shortage | Final lexical distance |",
        "|---|---:|---:|---:|---:|",
    ]
    for condition, group in groups.items():
        trade, reward, shortage, distance = [
            statistics.mean(r[key] for r in group.values())
            for key in (
                "trade_rate",
                "mean_reward",
                "mean_shortage",
                "final_lexical_distance",
            )
        ]
        lines.append(
            f"| {condition} | {trade:.2%} | {reward:.5f} | {shortage:.2%} | {distance:.4f} |"
        )

    lines += [
        "",
        (
            "Each row is a mean across seeds. Buyer reward is inventory utility gained minus "
            "communication effort. Shortage is the proportion of agent–good inventories below half "
            "a unit. Lexical distance measures how differently regions distribute word use for the "
            "same good, from 0 (identical) to 1 (disjoint)."
        ),
        "",
        "### Differences within matched seeds",
        "",
        (
            "Each difference below subtracts the comparison condition from the adaptive condition "
            "at the same seed. Trade and shortage differences are in percentage points (pp)."
        ),
        "",
        "| Comparison | Seed | Trade (pp) | Buyer reward | Shortage (pp) | Final lexical distance |",
        "|---|---:|---:|---:|---:|",
    ]
    for other in ("fixed", "uniform"):
        for seed in seeds:
            a, b = groups["adaptive"][seed], groups[other][seed]
            trade, reward, shortage, distance = [
                a[k] - b[k]
                for k in (
                    "trade_rate",
                    "mean_reward",
                    "mean_shortage",
                    "final_lexical_distance",
                )
            ]
            lines.append(
                f"| Adaptive minus {other} | {seed} | {100 * trade:+.3f} | "
                f"{reward:+.5f} | {100 * shortage:+.3f} | {distance:+.4f} |"
            )
    lines += [
        "",
        (
            "Net reward can improve when agents spend less effort communicating. The trade "
            "and shortage columns show whether an improvement also coincided with more exchanges "
            "and better-stocked inventories. Openness affects repair, word learning, and effort "
            "together, so this design cannot isolate their individual effects."
        ),
        "",
        "## Contact over time",
        "",
        (
            "The schedule starts with all regions connected, separates them into pairs or isolated "
            "regions, opens a chain of trade routes, then reconnects all regions with increasing "
            "frequency. Time, accumulated learning, resource availability, and turnover also change "
            "across phases. These phase comparisons are descriptive."
        ),
        "",
        "| Condition | Phase | Trade | First-pass success | Mean reward | Shortage | Encounters across regions |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for condition, group in groups.items():
        first_run = next(iter(group.values()))
        for phase in first_run["phases"]:
            trade, first, reward, shortage, remote = [
                statistics.mean(r["phases"][phase][k] for r in group.values())
                for k in (
                    "trade_rate",
                    "first_success",
                    "mean_reward",
                    "shortage",
                    "remote_rate",
                )
            ]
            lines.append(
                f"| {condition} | {phase.replace('_', ' ')} | {trade:.2%} | "
                f"{first:.2%} | {reward:.5f} | {shortage:.2%} | {remote:.2%} |"
            )
    lines += [
        "",
        (
            "First-pass success requires both recognition of the requested word and stock of the "
            "requested good. A separate comprehension task would be needed to measure mutual intelligibility."
        ),
        "",
    ]
    if plot_trajectories(results, output):
        lines += [
            "Each line follows one seed. Dotted lines mark contact-phase boundaries.",
            "",
            "![Trade, reward, shortages, utility, lexical distance, and conventional speech by seed](trajectories.png)",
            "",
        ]
    lines += [
        "## Ledger audit",
        "",
        (
            "The audit checks SQLite integrity, run configuration, completed rounds, encounter counts, "
            "checkpoint completion, legal contacts, and resource conservation. It also compares trades, "
            "rewards, and utility gains against the round summaries."
        ),
        "",
        "| Condition | Seed | Encounters | Checks |",
        "|---|---:|---:|---|",
    ]
    for r in results:
        failures = [k for k, v in r["audit"].items() if not v]
        lines.append(
            f"| {r['config']['condition']} | {r['config']['seed']} | {r['events']:,} | "
            f"{', '.join(failures) if failures else 'Pass'} |"
        )
    lines += [
        "",
        (
            "The metrics file includes each run’s model fingerprint, audit checks, strategy "
            "shares, dominant regional words, final regional utility and openness, and trajectories "
            "in blocks of up to 200 rounds. [Download metrics](metrics.json)"
        ),
        "",
    ]
    (output / "report.md").write_text("\n".join(lines))
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if generate(args.root, args.output) else 1)


if __name__ == "__main__":
    main()
