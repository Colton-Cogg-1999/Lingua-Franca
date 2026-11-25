"""Build the native simulator and run matched histories. Requires Python 3.11+ and C++17."""

import argparse
import csv
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory

ENGINE = Path(__file__).with_name("provinces.cpp")
HISTORIES = ("breakup", "open", "sealed")


def records(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def audit(directory, size, rounds):
    rows = records(directory / "intervals.csv")
    routes = records(directory / "routes.csv")
    # Keys must cover every time and direction exactly once, including unused routes.
    split, step = rounds // 10, rounds // 20
    keys = {("common", t) for t in range(0, split + 1, step)}
    keys.update(
        (h, t) for h in HISTORIES for t in range(split + step, rounds + 1, step)
    )
    indexed = {(r["history"], int(r["round"])): r for r in rows}
    if set(indexed) != keys or len(rows) != len(keys):
        raise ValueError("missing or duplicate interval")
    seen = set()
    totals = {key: [0, 0] for key in keys}
    for r in routes:
        h, t = r["history"], int(r["round"])
        a, b, n = (
            int(r[k]) for k in ("listener_town", "speaker_town", "conversations")
        )
        key = (h, t, a, b)
        if key in seen or not (0 <= a < 6 and 0 <= b < 6 and n >= 0):
            raise ValueError("invalid contact matrix")
        seen.add(key)
        if (
            t <= 7 * rounds // 10
            and a != b
            and n
            and (h == "sealed" or (h == "breakup" and abs(a - b) > 1))
        ):
            raise ValueError("contact outside an allowed route")
        totals[h, t][0] += n
        totals[h, t][1] += n if a != b else 0
    if len(seen) != 36 * len(keys):
        raise ValueError("incomplete contact matrices")
    for key, r in indexed.items():
        n, remote, first, repair, adopted, coined = (
            int(r[k])
            for k in (
                "conversations",
                "remote",
                "understood",
                "repairs",
                "adoptions",
                "coins",
            )
        )
        if (
            totals[key] != [n, remote]
            or n != (step * 6 * size if key[1] else 0)
            or not 0 <= first <= first + repair <= n
            or not 0 <= adopted <= first + repair
            or not 0 <= coined <= n
        ):
            raise ValueError(f"event counts failed at {key}")
        for kind, expected in (("local", 6 * 24 * 32), ("remote", 30 * 24 * 32)):
            if (
                int(r[kind + "_probes"]) != expected
                or not 0 <= int(r[kind + "_probe_hits"]) <= expected
            ):
                raise ValueError("invalid probe count")
    return sum(v[0] for v in totals.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--seeds", type=int, default=256, help="independent seeds starting at 1"
    )
    parser.add_argument("--per-town", type=int, default=512)
    parser.add_argument(
        "--rounds", type=int, default=2000, help="multiple of 20, minimum 40"
    )
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if (
        min(args.seeds, args.jobs) < 1
        or args.per_town < 3
        or args.rounds < 40
        or args.rounds % 20
    ):
        parser.error("invalid seeds, jobs, population, or rounds")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    with TemporaryDirectory(dir=root, prefix=".build-") as build:
        binary = Path(build) / "provinces"
        subprocess.run(
            [
                os.getenv("CXX", "c++"),
                "-std=c++17",
                "-O3",
                str(ENGINE),
                "-o",
                str(binary),
            ],
            check=True,
        )

        def run_seed(seed):
            dest = root / f"seed-{seed:04d}"
            config = dict(
                seed=seed,
                model_sha256=source,
                per_town=args.per_town,
                rounds=args.rounds,
            )
            if dest.exists():
                if json.loads((dest / "config.json").read_text()) != config:
                    raise ValueError(f"{dest} contains a different experiment")
                return audit(dest, args.per_town, args.rounds)
            with TemporaryDirectory(dir=root, prefix=f".seed-{seed}-") as tmp:
                working = Path(tmp) / "out"
                working.mkdir()
                subprocess.run(
                    [
                        str(binary),
                        str(seed),
                        str(args.per_town),
                        str(args.rounds),
                        str(working),
                    ],
                    check=True,
                )
                total = audit(working, args.per_town, args.rounds)
                (working / "config.json").write_text(
                    json.dumps(config, indent=2) + "\n"
                )
                working.rename(dest)
            return total

        total = 0
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            tasks = [pool.submit(run_seed, seed) for seed in range(1, args.seeds + 1)]
            for i, task in enumerate(as_completed(tasks), 1):
                total += task.result()
                if i == 1 or i % 16 == 0 or i == args.seeds:
                    print(
                        f"{i}/{args.seeds} seeds audited | {total:,} conversations",
                        flush=True,
                    )
    manifest = dict(
        model_sha256=source,
        seeds=args.seeds,
        per_town=args.per_town,
        rounds=args.rounds,
        conversations=total,
        shared_rounds=args.rounds // 10,
        reopen_after=7 * args.rounds // 10,
    )
    path = root / "manifest.json"
    path.with_suffix(".pending").write_text(json.dumps(manifest, indent=2) + "\n")
    path.with_suffix(".pending").replace(path)


if __name__ == "__main__":
    main()
