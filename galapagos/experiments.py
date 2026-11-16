"""Replicated intervention comparisons, without per-interaction disk logging."""
import argparse
import csv
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev
from .model import Config, Simulation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replicates', type=int, default=10)
    parser.add_argument('--rounds', type=int, default=100)
    parser.add_argument('--population', type=int, default=100)
    parser.add_argument('--output', type=Path, default=Path('runs/comparison.csv'))
    args = parser.parse_args()
    if args.replicates < 2 or args.rounds < 1:
        parser.error('use at least two replicates and one round')
    scenarios = {'isolated': dict(contact=0, migration=0),
                 'contact': dict(contact=0.15, migration=0.03),
                 'contact_no_prestige': dict(contact=0.15, migration=0.03, prestige_bias=0)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=['scenario', 'seed', 'distance'])
        writer.writeheader()
        for name, settings in scenarios.items():
            distances = []
            for seed in range(args.replicates):
                sim = Simulation(replace(Config(population=args.population, seed=seed), **settings))
                for _ in range(args.rounds):
                    sim.step()
                distance = sim.summary()['mean_between_island_distance']
                writer.writerow(dict(scenario=name, seed=seed, distance=distance))
                distances.append(distance)
            print(f'{name}: mean distance={mean(distances):.4f}, sample SD={stdev(distances):.4f}, n={len(distances)}')


if __name__ == '__main__':
    main()
