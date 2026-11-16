"""Bounded Kubernetes experiment with committed outboxes and Redpanda transactions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import time

from .game import Game, GameConfig, VERSION, OBJECTS, ACTIONS, digest, interpret, produce, stream, summarize, validate_topology
from .play import commit, source_hash
from .policies import KubernetesPolicies, verify
from .regions import RegionTransport


def topology_for(plan, round_number):
    for phase in plan['phases']:
        if round_number <= phase['through']:
            n = len(plan['regions'])
            if phase['edges'] == 'all':
                graph = [list(range(n)) for _ in range(n)]
            else:
                graph = [[i] for i in range(n)]
                for a, b in phase['edges']:
                    graph[a].append(b)
                    graph[b].append(a)
            return phase['name'], validate_topology(graph, n)
    raise ValueError('round outside experiment schedule')


def validate_plan(plan):
    config = GameConfig(**plan['config'])
    if config.islands != len(plan['regions']) or plan['rounds'] < 1 or plan['diagnostic_interval'] < 1:
        raise ValueError('invalid experiment dimensions')
    boundaries = [p['through'] for p in plan['phases']]
    if boundaries != sorted(set(boundaries)) or boundaries[0] < 1 or boundaries[-1] != plan['rounds']:
        raise ValueError('phase boundaries must increase and end at requested rounds')
    for phase in plan['phases']:
        topology_for(plan, phase['through'])
    return config


def diagnostic(game, samples=80):
    rng = stream(game.config.seed, game.state['round'], 'held-out-comprehension')
    groups = [[s for s in game.state['speakers'] if s['island'] == i] for i in range(game.config.islands)]
    matrix = []
    for sources in groups:
        row = []
        for listeners in groups:
            if not sources or not listeners:
                row.append(None)
                continue
            successes = 0
            for _ in range(samples):
                source, listener = rng.choice(sources), rng.choice(listeners)
                intention = dict(action=rng.choice(ACTIONS), object=rng.choice(OBJECTS))
                utterance = produce(source, intention, rng)
                successes += interpret(listener, utterance['text'], OBJECTS, rng) == intention
            row.append(successes / samples)
        matrix.append(row)
    return dict(round=game.state['round'], samples_per_pair=samples, source_by_listener=matrix,
                note='Read-only diagnostic; no simulated contact, repair, or learning occurs.')


class Ledger:
    def __init__(self, brokers, topic, run_id):
        from confluent_kafka import Producer
        self.topic = topic
        self.run_id = run_id
        self.producer = Producer({'bootstrap.servers': brokers, 'enable.idempotence': True,
                                  'transactional.id': 'galapagos-' + run_id,
                                  'transaction.timeout.ms': 120000,
                                  'delivery.timeout.ms': 60000, 'message.max.bytes': 4194304})
        self.producer.init_transactions(60)

    def publish(self, path):
        errors = []
        def delivered(error, message):
            if error:
                errors.append(str(error))
        self.producer.begin_transaction()
        try:
            with path.open() as file:
                for line in file:
                    while True:
                        try:
                            self.producer.produce(self.topic, key=self.run_id, value=line, on_delivery=delivered)
                            break
                        except BufferError:
                            self.producer.poll(0.1)
                    self.producer.poll(0)
            self.producer.flush(60)
            if errors:
                raise RuntimeError(errors[0])
            self.producer.commit_transaction(60)
        except Exception:
            self.producer.abort_transaction(30)
            raise


def load_latest(root, config, run_id):
    folders = sorted(p for p in (root / 'rounds').glob('[0-9]*') if p.is_dir())
    if not folders:
        game = Game(config)
        game.run_id = run_id
        return game
    folder = folders[-1]
    manifest = json.loads((folder / 'manifest.json').read_text())
    import hashlib
    for name, checksum in manifest.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != checksum:
            raise ValueError('committed checkpoint corruption')
    checkpoint = json.loads((folder / 'checkpoint.json').read_text())
    if checkpoint['source_hash'] != source_hash() or checkpoint['run_id'] != run_id or checkpoint['config'] != asdict(config):
        raise ValueError('checkpoint provenance mismatch')
    game = Game(config, checkpoint['state'])
    game.run_id = run_id
    return game


def durable_json(path, value):
    from .play import sync_directory
    import os
    staging = path.with_suffix('.pending')
    with staging.open('w') as file:
        json.dump(value, file)
        file.flush()
        os.fsync(file.fileno())
    staging.replace(path)
    sync_directory(path.parent)


def publish_pending(root, ledger):
    progress = root / 'published.json'
    last = json.loads(progress.read_text())['round'] if progress.exists() else -1
    for folder in sorted((root / 'rounds').glob('[0-9]*')):
        if int(folder.name) <= last:
            continue
        ledger.publish(folder / 'events.jsonl')
        durable_json(progress, {'round': int(folder.name)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--brokers', default='redpanda:9092')
    parser.add_argument('--topic', default='galapagos.evolution.v2')
    parser.add_argument('--worker-url', action='append', required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    config = validate_plan(plan)
    if len(args.worker_url) != config.islands:
        parser.error('one worker endpoint per region required')
    run_id = digest(dict(model=VERSION, source=source_hash(), plan=plan))[:20]
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    (root / 'rounds').mkdir(exist_ok=True)
    plan_path = root / 'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError('output belongs to another experiment')
    durable_json(plan_path, plan)
    game = load_latest(root, config, run_id)
    ledger = Ledger(args.brokers, args.topic, run_id)
    transport = RegionTransport(args.worker_url)
    policies = KubernetesPolicies()
    if game.state['round'] == 0 and not (root / 'rounds' / '000000').exists():
        event = dict(schema=2, kind='initialized', event_id=f'{run_id}:0:initial', run_id=run_id,
                     model=VERSION, round=0, plan=plan, state=game.state)
        commit(root, game, [event], summarize(game.state, []))
    publish_pending(root, ledger)
    active_phase = None
    while game.state['round'] < plan['rounds']:
        if shutil.disk_usage(root).free < 20 * 1024**3:
            raise RuntimeError('less than 20 GiB free; pausing before next round')
        next_round = game.state['round'] + 1
        phase, topology = topology_for(plan, next_round)
        boundary = None
        if phase != active_phase:
            policies.apply(topology)
            checks = verify(topology, args.worker_url)
            boundary = dict(kind='geography_changed', schema=2, run_id=run_id, round=next_round,
                            event_id=f'{run_id}:{next_round}:geography', phase=phase, topology=topology, checks=checks)
            active_phase = phase
            print(json.dumps(dict(status='boundaries_verified', phase=phase, next_round=next_round, checks=checks)), flush=True)
        # If tasks fail, no state is committed; Kubernetes restarts from the last durable round.
        events, summary = game.step(transport, topology)
        for event in events:
            event['geographic_phase'] = phase
        for event in events:
            if event['kind'] == 'conversation' and event['source_island'] not in topology[event['island']]:
                raise RuntimeError('illegal cross-boundary communication')
            if event['kind'] == 'migration' and event['destination'] not in topology[event['source']]:
                raise RuntimeError('illegal cross-boundary migration')
        summary['geographic_phase'] = phase
        summary['topology'] = topology
        if boundary:
            events.insert(0, boundary)
        if game.state['round'] % plan['diagnostic_interval'] == 0 or boundary:
            measurement = diagnostic(game)
            summary['held_out_comprehension'] = measurement
            events.insert(-1, dict(kind='comprehension_audit', schema=2, run_id=run_id, round=game.state['round'],
                                 event_id=f"{run_id}:{game.state['round']}:audit", measurement=measurement))
        folder = commit(root, game, events, summary)
        ledger.publish(folder / 'events.jsonl')
        durable_json(root / 'published.json', {'round': game.state['round']})
        durable_json(root / 'status.json', dict(state='running', run_id=run_id, round=game.state['round'],
                    total_rounds=plan['rounds'], phase=phase, population=len(game.state['speakers']),
                    lexical_distance=summary['mean_lexical_distance'], updated_unix=time.time()))
        if game.state['round'] % 10 == 0:
            print(json.dumps(dict(round=game.state['round'], phase=phase, population=len(game.state['speakers']),
                                  lexical_distance=summary['mean_lexical_distance'], ledger='committed')), flush=True)
    status = json.loads((root / 'status.json').read_text())
    status['state'] = 'complete'
    durable_json(root / 'status.json', status)
    print(json.dumps(status), flush=True)


if __name__ == '__main__':
    main()
