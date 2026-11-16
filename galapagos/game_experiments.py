"""Controlled ablations, with atomic per-replicate files and resumable aggregation."""
import argparse
import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
from statistics import mean, stdev
import time
from .game import Game, GameConfig
from .play import source_hash, sync_directory, write_durable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replicates', type=int, default=10)
    parser.add_argument('--rounds', type=int, default=50)
    parser.add_argument('--population', type=int, default=20)
    parser.add_argument('--output', type=Path, default=Path('runs/game-ablations'))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.replicates < 2 or args.rounds < 1:
        parser.error('at least two replicates and one round required')
    base = GameConfig(population=args.population, contact=0.3, migration=0, turnover=0, innovation=0)
    scenarios = {'repair_learning': {}, 'no_repair': {'repair': 0},
                 'no_learning': {'learning': 0}, 'isolated': {'contact': 0}}
    design = dict(base=asdict(base), scenarios=scenarios, seeds=list(range(args.replicates)), rounds=args.rounds)
    if args.resume:
        if json.loads((args.output / 'design.json').read_text()) != design:
            parser.error('resume parameters do not match existing design')
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'design.json').write_text(json.dumps(design, indent=2))
    committed = args.output / 'replicates'
    committed.mkdir(exist_ok=True)
    aggregates = []
    start = time.perf_counter()
    with (args.output / 'trajectories.jsonl').open('w') as trajectory, (args.output / 'replicates.csv').open('w', newline='') as output:
        fields = ['scenario', 'seed', 'first_success', 'cross_first_success', 'final_success', 'distance']
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for scenario, settings in scenarios.items():
            measurements = []
            for seed in range(args.replicates):
                path = committed / f'{scenario}-{seed}.json'
                if path.exists():
                    saved = json.loads(path.read_text())
                    if saved['source_hash'] != source_hash() or saved['config'] != asdict(replace(base, seed=seed, **settings)):
                        raise ValueError('replicate source/config mismatch')
                    history = saved['history']
                    if [row['round'] for row in history] != list(range(1, args.rounds + 1)):
                        raise ValueError('incomplete replicate')
                else:
                    game = Game(replace(base, seed=seed, **settings))
                    history = []
                    for _ in range(args.rounds):
                        _, summary = game.step()
                        summary.pop('islands')
                        history.append(dict(scenario=scenario, seed=seed, **summary))
                    pending = path.with_suffix('.pending')
                    if pending.exists():
                        pending.unlink()
                    write_durable(pending, json.dumps(dict(source_hash=source_hash(), config=asdict(game.config), history=history)))
                    pending.replace(path)
                    sync_directory(committed)
                for row in history:
                    trajectory.write(json.dumps(row) + '\n')
                recent = history[-10:]
                def rate(group, name):
                    total = sum(s[group]['count'] for s in recent)
                    return sum((s[group][name] or 0) * s[group]['count'] for s in recent) / total if total else None
                row = dict(scenario=scenario, seed=seed, first_success=rate('overall', 'first_success'),
                           cross_first_success=rate('cross_island', 'first_success'),
                           final_success=rate('overall', 'final_success'), distance=history[-1]['mean_lexical_distance'])
                writer.writerow(row)
                output.flush()
                trajectory.flush()
                measurements.append(row)
            aggregate = dict(scenario=scenario, replicates=args.replicates)
            for metric in fields[2:]:
                values = [row[metric] for row in measurements if row[metric] is not None]
                aggregate[metric] = dict(mean=mean(values), sample_sd=stdev(values)) if len(values) > 1 else None
            aggregates.append(aggregate)
            print(json.dumps(aggregate), flush=True)
    (args.output / 'summary.json').write_text(json.dumps(dict(invocation_seconds=round(time.perf_counter() - start, 3),
             window_rounds=min(10, args.rounds), scenarios=aggregates), indent=2))


if __name__ == '__main__':
    main()
