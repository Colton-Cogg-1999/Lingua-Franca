"""Run matched trade and communication experiments and audit the results."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from .provenance import model_source
from .report import generate


def write_json(path, data):
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(data, indent=2) + "\n")
    pending.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=24000)
    parser.add_argument(
        "--population", type=int, default=20, help="agents per community"
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[476, 911, 2026])
    args = parser.parse_args()
    if args.rounds < 1 or args.population < 2:
        parser.error(
            "each run requires positive rounds and at least two agents per community"
        )
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("each seed must be unique")

    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    runs = [
        {"name": f"{condition}-{seed}", "condition": condition, "seed": seed}
        for seed in args.seeds
        for condition in ("adaptive", "fixed", "uniform")
    ]
    manifest = {
        "rounds": args.rounds,
        "population": args.population,
        "runs": runs,
        "source": model_source(),
    }
    path = root / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("Study manifest mismatch")
    else:
        write_json(path, manifest)

    status = {
        "state": "running",
        "completed": 0,
        "total": len(runs),
        "started": time.time(),
    }

    def update(**changes):
        status.update(changes, updated=time.time())
        write_json(root / "study.json", status)

    try:
        for index, run in enumerate(runs):
            update(current=run["name"], completed=index)
            with (root / f"{run['name']}.log").open("a") as log:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "lingua_franca.society",
                        "--output",
                        str(root / run["name"]),
                        "--rounds",
                        str(args.rounds),
                        "--population",
                        str(args.population),
                        "--seed",
                        str(run["seed"]),
                        "--condition",
                        run["condition"],
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            update(completed=index + 1)
        report = root / "report"
        update(state="auditing", report=str(report))
        passed = generate(root, report)
        if not passed:
            update(audit_passed=False)
            raise RuntimeError(
                f"Integrity audit failed. Inspect {report / 'metrics.json'}"
            )
        update(state="complete", audit_passed=True)
        print(json.dumps(status), flush=True)
    except BaseException as error:
        update(state="failed", error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
