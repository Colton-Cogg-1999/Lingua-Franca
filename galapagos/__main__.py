import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from .model import Config, Simulation


def main():
    parser = argparse.ArgumentParser(description='Synthetic language contact across island communities')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--rounds', type=int, default=100)
    parser.add_argument('--output', type=Path, default=Path('runs/demo'))
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    if args.rounds < 0:
        parser.error('--rounds must be nonnegative')
    if args.config and args.resume:
        parser.error('--config and --resume are mutually exclusive')
    config = Config(**json.loads(args.config.read_text())) if args.config else Config()
    # Exclusive directory creation prevents mixing or overwriting runs.
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    with (args.output / 'events.jsonl').open('w') as ledger, (args.output / 'metrics.jsonl').open('w') as metrics:
        def emit(event):
            ledger.write(json.dumps(event, separators=(',', ':')) + '\n')
        sim = Simulation.restore(args.resume, emit) if args.resume else Simulation(config, emit)
        (args.output / 'config.json').write_text(json.dumps(asdict(sim.config), indent=2))
        if args.resume:
            sim.event('resumed', checkpoint=str(args.resume.resolve()))
        metrics.write(json.dumps(sim.summary()) + '\n')
        for _ in range(args.rounds):
            metrics.write(json.dumps(sim.step()) + '\n')
        sim.checkpoint(args.output / 'checkpoint.json')
    elapsed = time.perf_counter() - start
    print(json.dumps(dict(output=str(args.output), seconds=round(elapsed, 3),
                          speakers=len(sim.speakers), rounds=args.rounds,
                          final_distance=sim.summary()['mean_between_island_distance']), indent=2))


if __name__ == '__main__':
    main()
