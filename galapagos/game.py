"""Grounded communication game and deterministic, transport-independent island tasks.

Interpretation receives an utterance, visible objects and listener knowledge only.
The environment reveals the intended referent exclusively during explicit repair.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random

VERSION = 'communication-game-v2-regions'
OBJECTS = ('water', 'fruit', 'stone', 'seed', 'bread', 'salt', 'fish', 'wood', 'cloth', 'tool', 'cup', 'rope')
ACTIONS = ('give', 'show')
ORDERS = ('verb_object', 'object_verb')
WORDS = (
    ('nara', 'poma', 'taku', 'sima', 'pane', 'sala', 'pisi', 'ligna', 'tela', 'faro', 'kupa', 'nodu'),
    ('aku', 'beli', 'koro', 'mepi', 'dani', 'zoli', 'feni', 'bora', 'muta', 'veko', 'cali', 'runi'),
    ('suli', 'fena', 'daku', 'nemi', 'banu', 'teli', 'zapa', 'vumi', 'kesi', 'gona', 'deli', 'palu'),
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def stream(seed, *parts):
    return random.Random(int(digest([seed, *parts]), 16))


@dataclass(frozen=True)
class GameConfig:
    seed: int = 42
    islands: int = 3
    population: int = 40
    encounters: int = 4
    contact: float = 0.25
    migration: float = 0.005
    turnover: float = 0.01
    repair: float = 0.8
    learning: float = 1.0
    prestige_bias: float = 0.0
    innovation: float = 0.002
    friendship_bias: float = 0.8
    shared_ancestry: bool = False
    sound_change: float = 0.0
    construction_innovation: float = 0.0
    retention: float = 1.0
    compact_events: bool = False

    def __post_init__(self):
        for name in ('islands', 'population', 'encounters'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        if type(self.seed) is not int:
            raise ValueError('seed must be an integer')
        for name in ('contact', 'migration', 'turnover', 'repair', 'prestige_bias',
                     'innovation', 'friendship_bias', 'learning', 'sound_change', 'construction_innovation', 'retention'):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f'{name} must be finite and in [0, 1]')


def choose(rng, weights):
    keys = sorted(weights)
    return rng.choices(keys, [weights[key] for key in keys])[0]


def normalize(weights):
    total = sum(weights.values())
    return {key: value / total for key, value in sorted(weights.items())} if total else {}


def initialize(config):
    rng = stream(config.seed, 'initialize')
    speakers = []
    for island in range(config.islands):
        for local in range(config.population):
            speaker_id = island * config.population + local
            dialect = 0 if config.shared_ancestry else island
            words = WORDS[dialect % len(WORDS)]
            suffix = str(dialect // len(WORDS)) if dialect >= len(WORDS) else ''
            friends = sorted({island * config.population + (local + delta) % config.population
                              for delta in (-2, -1, 1, 2)} - {speaker_id})
            speakers.append(dict(id=speaker_id, island=island, cohort=0, prestige=rng.random(),
                                 friends=friends,
                                 lexicon={obj: {word + suffix: 4.0} for obj, word in zip(OBJECTS, words)},
                                 constructions={ORDERS[dialect % 2]: 4.0}))
    return dict(round=0, next_id=len(speakers), speakers=speakers)


def produce(speaker, intention, rng, innovation=0, sound_change=0, construction_innovation=0):
    word = choose(rng, speaker['lexicon'][intention['object']])
    innovative = rng.random() < innovation
    if innovative:
        word = ''.join(rng.choice(('la', 'mi', 'ku', 'se', 'po', 'ra', 'ni', 'tu')) for _ in range(3))
    sound_shift = None
    if sound_change and rng.random() < sound_change:
        old, new = (('k', 'g'), ('t', 'd'), ('p', 'b'), ('a', 'e'), ('s', 'h'), ('r', 'l'))[speaker['island'] % 6]
        changed = word.replace(old, new)
        if changed != word:
            sound_shift = [old, new]
            word = changed
    order = choose(rng, speaker['constructions'])
    construction_changed = bool(construction_innovation and rng.random() < construction_innovation)
    if construction_changed:
        order = ORDERS[1 - ORDERS.index(order)]
    tokens = [intention['action'], word] if order == 'verb_object' else [word, intention['action']]
    return dict(text=' '.join(tokens), word=word, construction=order, innovative=innovative, sound_shift=sound_shift, construction_innovation=construction_changed)


def interpret(listener, utterance, scene, rng):
    """No intention, source lexicon or event metadata crosses this interface."""
    tokens = utterance.split()
    if len(tokens) != 2:
        return None
    candidates = {}
    for order, construction_weight in sorted(listener['constructions'].items()):
        action, word = tokens if order == 'verb_object' else tokens[::-1]
        if action not in ACTIONS:
            continue
        for obj in scene:
            evidence = listener['lexicon'][obj].get(word, 0)
            if evidence > 0:
                candidates[(action, obj)] = candidates.get((action, obj), 0) + evidence * construction_weight
    if not candidates:
        return None
    action, obj = choose(rng, candidates)
    return dict(action=action, object=obj)


def learn(listener, obj, word, construction, amount):
    if amount <= 0:
        return
    words = listener['lexicon'][obj]
    words[word] = words.get(word, 0) + amount
    orders = listener['constructions']
    orders[construction] = orders.get(construction, 0) + amount


def encounter(source, listener, intention, config, rng):
    utterance = produce(source, intention, rng, config.innovation, config.sound_change, config.construction_innovation)
    before = dict(lexicon=deepcopy(listener['lexicon'][intention['object']]),
                  constructions=deepcopy(listener['constructions']))
    interpretation = interpret(listener, utterance['text'], OBJECTS, rng)
    success = interpretation == intention
    # Environment gives binary success feedback. On repair it grounds the word by
    # pointing to the desired object and demonstrating the shared action.
    repaired = not success and rng.random() < config.repair
    grounded = success or repaired
    # Centered prestige influence avoids the old parameter's systematic mean-rate shift.
    weight = config.learning * (1 + config.prestige_bias * (2 * source['prestige'] - 1))
    if grounded:
        learn(listener, intention['object'], utterance['word'], utterance['construction'], weight)
    after = dict(lexicon=deepcopy(listener['lexicon'][intention['object']]),
                 constructions=deepcopy(listener['constructions']))
    turns = [dict(actor=source['id'], speech=utterance['text']),
             dict(actor=listener['id'], action=interpretation if interpretation else 'unrecognized')]
    if repaired:
        turns.extend([dict(actor=listener['id'], speech='[clarification request]'),
                      dict(actor=source['id'], gesture=f"[points to {intention['object']}; demonstrates {intention['action']}]"),
                      dict(actor=listener['id'], action=intention)])
    result = dict(kind='conversation', speaker=source['id'], listener=listener['id'],
                source_island=source['island'], island=listener['island'],
                cross_island=source['island'] != listener['island'], intention=intention,
                utterance=utterance, interpretation=interpretation, first_success=success,
                repaired=repaired, final_success=grounded, learning_weight=weight if grounded else 0,
                learning_cause='successful_action' if success else ('grounded_repair' if repaired else 'none'),
                before=before, after=after, turns=turns)
    if config.compact_events:
        result.pop('before')
        result.pop('after')
        result.pop('turns')
        result['evidence'] = dict(word_before=before['lexicon'].get(utterance['word'], 0),
                                word_after=after['lexicon'].get(utterance['word'], 0),
                                construction_before=before['constructions'].get(utterance['construction'], 0),
                                construction_after=after['constructions'].get(utterance['construction'], 0))
    return result


def island_task(task):
    """Pure request/result boundary: retrying an identical task returns identical data.

    Speakers produce from the immutable round-start snapshot; only listeners owned
    by this task learn, sequentially. Updates become visible to sources next round.
    """
    config = GameConfig(**task['config'])
    snapshot = task['snapshot']
    if digest(snapshot) != task['snapshot_hash']:
        raise ValueError('island task snapshot hash mismatch')
    island, round_number = task['island'], task['round']
    rng = stream(config.seed, round_number, island, 'encounters')
    sources = snapshot['speakers']
    local = [s for s in sources if s['island'] == island]
    remote = [s for s in sources if s['island'] != island]
    listeners = deepcopy(local)
    rng.shuffle(listeners)
    events = []
    for listener in listeners:
        if config.retention < 1:
            for evidence in [*listener['lexicon'].values(), listener['constructions']]:
                strongest = max(evidence, key=evidence.get)
                for key in list(evidence):
                    evidence[key] *= config.retention
                    if evidence[key] < 0.05 and key != strongest:
                        del evidence[key]
                evidence[strongest] = max(evidence[strongest], 0.05)
        for _ in range(config.encounters):
            pool = remote if rng.random() < config.contact and remote else [s for s in local if s['id'] != listener['id']]
            friends = [s for s in pool if s['id'] in listener['friends']]
            if friends and rng.random() < config.friendship_bias:
                pool = friends
            if not pool:
                continue
            source = rng.choice(pool)
            intention = dict(action=rng.choice(ACTIONS), object=rng.choice(OBJECTS))
            events.append(encounter(source, listener, intention, config, rng))
    return dict(task_id=task['task_id'], snapshot_hash=task['snapshot_hash'], island=island,
                speakers=sorted(listeners, key=lambda s: s['id']), events=events)


def summarize(state, events):
    speakers = state['speakers']
    conversations = [e for e in events if e['kind'] == 'conversation']
    def rates(group):
        return dict(count=len(group), first_success=sum(e['first_success'] for e in group) / len(group) if group else None,
                    final_success=sum(e['final_success'] for e in group) / len(group) if group else None,
                    repair_rate=sum(e['repaired'] for e in group) / len(group) if group else None)
    islands = []
    for island in sorted({s['island'] for s in speakers}):
        group = [s for s in speakers if s['island'] == island]
        frequencies = {}
        for obj in OBJECTS:
            frequencies[obj] = {}
            for speaker in group:
                for word, probability in normalize(speaker['lexicon'][obj]).items():
                    frequencies[obj][word] = frequencies[obj].get(word, 0) + probability / len(group)
        islands.append(dict(island=island, population=len(group), frequencies=frequencies))
    distances = []
    for index, a in enumerate(islands):
        for b in islands[index + 1:]:
            distances.append(sum(sum(abs(a['frequencies'][obj].get(word, 0) - b['frequencies'][obj].get(word, 0))
                                     for word in a['frequencies'][obj].keys() | b['frequencies'][obj].keys()) / 2
                                 for obj in OBJECTS) / len(OBJECTS))
    return dict(round=state['round'], population=len(speakers), overall=rates(conversations),
                cross_island=rates([e for e in conversations if e['cross_island']]),
                local=rates([e for e in conversations if not e['cross_island']]),
                mean_lexical_distance=sum(distances) / len(distances) if distances else None, islands=islands)


class Game:
    def __init__(self, config=GameConfig(), state=None):
        self.config = config
        self.state = deepcopy(state) if state is not None else initialize(config)
        self.run_id = digest(dict(version=VERSION, config=asdict(config)))[:20]

    def tasks(self, topology=None):
        topology = validate_topology(topology, self.config.islands)
        world_hash = digest(self.state)
        round_number = self.state['round'] + 1
        tasks = []
        for island in range(self.config.islands):
            snapshot = dict(round=self.state['round'], next_id=self.state['next_id'],
                            speakers=deepcopy(sorted([s for s in self.state['speakers']
                                                      if s['island'] in topology[island]], key=lambda s: s['id'])))
            tasks.append(dict(task_id=f'{self.run_id}:{round_number}:{island}:{digest(topology)[:12]}',
                              config=asdict(self.config), round=round_number, island=island,
                              snapshot=snapshot, snapshot_hash=digest(snapshot), world_hash=world_hash,
                              topology=topology))
        return tasks

    def apply(self, tasks, results):
        if len(results) != len(tasks) or len({r['island'] for r in results}) != len(tasks):
            raise ValueError('missing or duplicated island results')
        if not tasks or tasks[0]['world_hash'] != digest(self.state):
            raise ValueError('stale round snapshot')
        topology = validate_topology(tasks[0]['topology'], self.config.islands)
        if any(t['topology'] != topology or t['round'] != self.state['round'] + 1 or t['world_hash'] != digest(self.state) for t in tasks):
            raise ValueError('inconsistent topology/round task batch')
        expected = {t['island']: t for t in tasks}
        events, speakers = [], []
        for result in sorted(results, key=lambda r: r['island']):
            task = expected.get(result['island'])
            if task is None or any(result[k] != task[k] for k in ('task_id', 'snapshot_hash')):
                raise ValueError('result does not match task')
            owned = {s['id'] for s in self.state['speakers'] if s['island'] == result['island']}
            if (len(result['speakers']) != len(owned) or {s['id'] for s in result['speakers']} != owned
                    or any(s['island'] != result['island'] for s in result['speakers'])):
                raise ValueError('island ownership changed inside worker task')
            speakers.extend(deepcopy(result['speakers']))
            events.extend(deepcopy(result['events']))
        next_state = dict(round=self.state['round'] + 1, next_id=self.state['next_id'],
                          speakers=sorted(speakers, key=lambda s: s['id']))
        rng = stream(self.config.seed, next_state['round'], 'demography')
        for speaker in next_state['speakers']:
            destinations = [i for i in topology[speaker['island']] if i != speaker['island']]
            if destinations and rng.random() < self.config.migration:
                origin = speaker['island']
                speaker['island'] = rng.choice(destinations)
                events.append(dict(kind='migration', speaker=speaker['id'], source=origin, destination=speaker['island']))
        # Cultural acquisition from frozen post-interaction tutors, before replacements.
        replacements = []
        for index, adult in enumerate(next_state['speakers']):
            if rng.random() >= self.config.turnover:
                continue
            pool = [s for s in next_state['speakers'] if s['island'] == adult['island']]
            child = dict(id=next_state['next_id'], island=adult['island'], cohort=next_state['round'],
                         prestige=rng.random(), friends=[], lexicon={obj: {} for obj in OBJECTS}, constructions={})
            tutors = rng.choices(pool, k=3)
            for tutor in tutors:
                for obj in OBJECTS:
                    utterance = produce(tutor, dict(action='show', object=obj), rng)
                    learn(child, obj, utterance['word'], utterance['construction'], 1.0)
            child['friends'] = sorted({t['id'] for t in tutors})
            next_state['next_id'] += 1
            replacements.append((index, child))
            events.append(dict(kind='cohort_replacement', departed=adult['id'], tutors=[t['id'] for t in tutors], newcomer=deepcopy(child)))
        for index, child in replacements:
            next_state['speakers'][index] = child
        alive = {s['id'] for s in next_state['speakers']}
        for speaker in next_state['speakers']:
            speaker['friends'] = [friend for friend in speaker['friends'] if friend in alive]
        summary = summarize(next_state, events)
        events.append(dict(kind='round_completed', summary=summary))
        for sequence, event in enumerate(events):
            event.update(schema=2, model=VERSION, run_id=self.run_id, round=next_state['round'],
                         phase='demography' if event['kind'] in ('migration', 'cohort_replacement') else 'communication' if event['kind'] == 'conversation' else 'commit',
                         sequence=sequence, event_id=f"{self.run_id}:{next_state['round']}:{sequence}")
        # No mutation of authoritative state before every result has been validated.
        self.state = next_state
        return events, summary

    def step(self, executor=None, topology=None):
        tasks = self.tasks(topology)
        results = list(executor.map(island_task, tasks)) if executor else [island_task(t) for t in tasks]
        return self.apply(tasks, results)


def validate_topology(topology, islands):
    if topology is None:
        return [list(range(islands)) for _ in range(islands)]
    if len(topology) != islands:
        raise ValueError('one adjacency list per region required')
    result = []
    for island, neighbors in enumerate(topology):
        if island not in neighbors or any(type(n) is not int or not 0 <= n < islands for n in neighbors):
            raise ValueError('invalid region adjacency')
        result.append(sorted(set(neighbors)))
    if any(i not in result[j] for i, peers in enumerate(result) for j in peers):
        raise ValueError('geographic boundaries must be symmetric')
    return result
