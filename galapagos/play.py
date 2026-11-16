"""Run the communication game locally, with optional process-isolated island tasks."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import time

from . import game as model
from .game import Game, GameConfig, VERSION, digest, summarize


def source_hash():
    root = Path(model.__file__).parent
    names = ('game.py', 'history.py', 'longrun.py', 'regions.py', 'policies.py', 'play.py')
    return hashlib.sha256(b''.join(name.encode() + b'\0' + (root / name).read_bytes() for name in names)).hexdigest()


def write_durable(path, text):
    with path.open('x') as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())


def commit(root, game, events, summary):
    """Atomic visibility of state+outbox within one filesystem; no broker claim."""
    rounds = root / 'rounds'
    rounds.mkdir(exist_ok=True)
    sync_directory(root)
    destination = rounds / f"{game.state['round']:06d}"
    if destination.exists():
        raise FileExistsError(destination)
    staging = Path(tempfile.mkdtemp(prefix='.pending-', dir=rounds))
    try:
        checkpoint = dict(model=VERSION, source_hash=source_hash(), run_id=game.run_id,
                          config=asdict(game.config), state=game.state)
        write_durable(staging / 'checkpoint.json', json.dumps(checkpoint, sort_keys=True, allow_nan=False))
        write_durable(staging / 'events.jsonl', ''.join(json.dumps(e, sort_keys=True, allow_nan=False) + '\n' for e in events))
        write_durable(staging / 'summary.json', json.dumps(summary, sort_keys=True, allow_nan=False))
        manifest = {name: hashlib.sha256((staging / name).read_bytes()).hexdigest()
                    for name in ('checkpoint.json', 'events.jsonl', 'summary.json')}
        write_durable(staging / 'manifest.json', json.dumps(manifest, sort_keys=True))
        sync_directory(staging)
        staging.rename(destination)
        sync_directory(rounds)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def restore(path):
    if (path / 'rounds').is_dir():
        candidates = sorted(p for p in (path / 'rounds').iterdir() if p.is_dir() and p.name.isdigit())
        if not candidates:
            raise ValueError('no committed rounds found')
        path = candidates[-1]
    manifest = json.loads((path / 'manifest.json').read_text())
    expected = {'checkpoint.json', 'events.jsonl', 'summary.json'}
    if set(manifest) != expected:
        raise ValueError('invalid checkpoint manifest')
    for name, checksum in manifest.items():
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != checksum:
            raise ValueError(f'checkpoint integrity failure: {name}')
    data = json.loads((path / 'checkpoint.json').read_text())
    if data['model'] != VERSION or data['source_hash'] != source_hash():
        raise ValueError('checkpoint model/source mismatch; use the original model implementation')
    game = Game(GameConfig(**data['config']), state=data['state'])
    if data['run_id'] != game.run_id:
        raise ValueError('checkpoint run identity mismatch')
    return game


def export(root):
    summaries, examples = [], []
    acquired = {}
    reuse = None
    with (root / 'events.jsonl').open('w') as ledger, (root / 'metrics.jsonl').open('w') as metrics:
        for folder in sorted((root / 'rounds').iterdir()):
            if not folder.name.isdigit():
                continue
            summary = json.loads((folder / 'summary.json').read_text())
            summaries.append(summary)
            metrics.write(json.dumps(summary) + '\n')
            with (folder / 'events.jsonl').open() as source:
                for line in source:
                    ledger.write(line)
                    event = json.loads(line)
                    if event['kind'] != 'conversation':
                        continue
                    word = event['utterance']['word']
                    key = (event['speaker'], event['intention']['object'], word)
                    if reuse is None and key in acquired and event['round'] > acquired[key]['round'] and not event['utterance']['innovative']:
                        reuse = (acquired[key], event)
                    if event['repaired'] and word not in event['before']['lexicon'] and event['learning_weight'] > 0:
                        acquired.setdefault((event['listener'], event['intention']['object'], word), event)
                    if event['cross_island'] and event['repaired'] and not examples:
                        examples.append(event)
    lines = ['# Communication-game run', '',
             'This is a synthetic referential game. Shared actions are given; object words and word-order constructions are learned.', '',
             '| Round | First-attempt success | Cross-island first-attempt success | Success after repair | Lexical distance |',
             '| --- | ---: | ---: | ---: | ---: |']
    def percentage(value):
        return f'{100 * value:.1f}%' if value is not None else 'n/a'
    indexes = sorted({0, 1, len(summaries) // 2, len(summaries) - 1} & set(range(len(summaries))))
    for index in indexes:
        item = summaries[index]
        distance = item['mean_lexical_distance']
        lines.append(f"| {item['round']} | {percentage(item['overall']['first_success'])} | {percentage(item['cross_island']['first_success'])} | {percentage(item['overall']['final_success'])} | {distance:.3f} |" if distance is not None else
                     f"| {item['round']} | {percentage(item['overall']['first_success'])} | {percentage(item['cross_island']['first_success'])} | {percentage(item['overall']['final_success'])} | n/a |")
    lines.extend(['', '## Inspectable interaction traces', '',
                  'Bracketed clarification and pointing are fixed protocol annotations, not learned dialogue. First-attempt success excludes repair.'])
    if reuse:
        examples = list(reuse)
    for event in examples:
        lines.extend(['', f"### Round {event['round']} — event `{event['event_id']}`", '',
                      f"Speaker {event['speaker']} → listener {event['listener']}; intention: {event['intention']['action']} {event['intention']['object']}.", ''])
        for turn in event['turns']:
            value = turn.get('speech', turn.get('gesture', turn.get('action')))
            lines.append(f"- Agent {turn['actor']}: {value}")
        lines.extend(['', f"Learning cause: `{event['learning_cause']}`; evidence increment: {event['learning_weight']:.3f}.",
                      f"Listener's lexical evidence: `{event['before']['lexicon']}` → `{event['after']['lexicon']}`."])
    if reuse:
        lines.extend(['', 'The second trace shows the earlier learner producing the acquired form in a later round. This is model-state-driven production, not generated narration.'])
    (root / 'report.md').write_text('\n'.join(lines) + '\n')
    return summaries


def main():
    parser = argparse.ArgumentParser(description='Run an inspectable language communication game')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--rounds', type=int, default=50)
    parser.add_argument('--workers', type=int, default=1, help='1 = in-process reference, >1 = process pool')
    parser.add_argument('--output', type=Path, default=Path('runs/communication'))
    parser.add_argument('--resume', type=Path, help='previous run directory or committed round directory')
    parser.add_argument('--worker-url', action='append', default=[], help='HTTP worker endpoint, repeat for each island')
    args = parser.parse_args()
    if args.rounds < 0 or args.workers < 1:
        parser.error('rounds must be nonnegative and workers positive')
    if args.worker_url and args.workers != 1:
        parser.error('--worker-url and --workers are mutually exclusive')
    if args.resume and args.config:
        parser.error('resume and config are mutually exclusive')
    game = restore(args.resume) if args.resume else Game(GameConfig(**json.loads(args.config.read_text())) if args.config else GameConfig())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'config.json').write_text(json.dumps(asdict(game.config), indent=2))
    commit(args.output, game, [dict(schema=2, kind='resumed' if args.resume else 'initialized',
           model=VERSION, run_id=game.run_id, event_id=f"{game.run_id}:{game.state['round']}:initial",
           round=game.state['round'], phase='initialize', sequence=0, state=game.state,
           parent=str(args.resume.resolve()) if args.resume else None)], summarize(game.state, []))
    start = time.perf_counter()
    if args.worker_url:
        from .worker import RemoteWorkers
        context = RemoteWorkers(args.worker_url)
    else:
        context = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) if args.workers > 1 else nullcontext(None)
    with context as executor:
        for index in range(args.rounds):
            events, summary = game.step(executor)
            commit(args.output, game, events, summary)
            if (index + 1) % 10 == 0:
                print(f"Committed round {game.state['round']}", flush=True)
    elapsed = time.perf_counter() - start
    summaries = export(args.output)
    metadata = dict(seconds=round(elapsed, 3), workers=len(args.worker_url) or args.workers,
                    transport='http' if args.worker_url else 'process' if args.workers > 1 else 'in-process',
                    source_hash=source_hash(),
                    final_state_hash=digest(game.state), population=len(game.state['speakers']),
                    rounds_executed=args.rounds, model=VERSION)
    (args.output / 'runtime.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(dict(output=str(args.output), **metadata,
                         final_cross_island=summaries[-1]['cross_island']), indent=2))


if __name__ == '__main__':
    main()
