"""A two-word communication game, recovered from cfc6471."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations, permutations
from random import Random
from statistics import mean

OBJECTS = "water fruit stone seed bread salt fish wood cloth tool cup rope".split()
WORDS = "nara poma taku sima pane sala pisi ligna tela faro kupa nodu".split()
ACTIONS = ("give", "show")
ORDERS = ("verb_object", "object_verb")
SYLLABLES = ("la", "mi", "ku", "se", "po", "ra", "ni", "tu")


@dataclass
class Speaker:
    lexicon: dict
    orders: dict
    heard: dict = field(default_factory=dict)  # (group, object) -> last grounded word


def founders(cfg):
    def adult():
        return Speaker({obj: {word: 4.0} for obj, word in zip(OBJECTS, WORDS)}, {ORDERS[0]: 4.0})
    return [[adult() for _ in range(cfg["speakers_per_group"])] for _ in range(cfg["groups"])]


def choose(weights, rng):
    keys = sorted(weights)
    return rng.choices(keys, [weights[k] for k in keys])[0]


def produce(speaker, action, obj, rng, cfg=None, audience=None):
    word = choose(speaker.lexicon[obj], rng)
    order = choose(speaker.orders, rng)
    if cfg is not None:
        if rng.random() < cfg["innovation"]:
            word = "".join(rng.choice(SYLLABLES) for _ in range(3))
        elif rng.random() < cfg["accommodation"]:
            word = speaker.heard.get((audience, obj), word)
        if rng.random() < cfg["order_innovation"]:
            order = ORDERS[1 - ORDERS.index(order)]
    tokens = (action, word) if order == ORDERS[0] else (word, action)
    return tokens, word, order


def interpret(listener, tokens, rng):
    candidates = Counter()
    for order, weight in listener.orders.items():
        action, word = tokens if order == ORDERS[0] else reversed(tokens)
        if action in ACTIONS:
            for obj, words in listener.lexicon.items():
                if word in words:
                    candidates[action, obj] += weight * words[word]
    return choose(candidates, rng) if candidates else None


def learn(listener, obj, word, order, amount):
    words = listener.lexicon[obj]
    words[word] = words.get(word, 0) + amount
    listener.orders[order] = listener.orders.get(order, 0) + amount


def round_of_talk(groups, contact, cfg, rng):
    sources = deepcopy(groups)  # Speakers produce from the round-start population.
    for i, group in enumerate(groups):
        slots = list(range(len(group)))
        rng.shuffle(slots)
        for slot in slots:
            listener = group[slot]
            for weights in [*listener.lexicon.values(), listener.orders]:
                strongest = max(weights, key=weights.get)
                for key in list(weights):
                    weights[key] *= cfg["retention"]
                    if weights[key] < 0.05 and key != strongest:
                        del weights[key]
                weights[strongest] = max(0.05, weights[strongest])
            for _ in range(cfg["encounters_per_round"]):
                j = i
                if rng.random() < contact:
                    j = rng.choice([j for j in range(len(groups)) if j != i])
                pool = sources[j] if j != i else sources[i][:slot] + sources[i][slot+1:]
                source = rng.choice(pool)
                action, obj = rng.choice(ACTIONS), rng.choice(OBJECTS)
                tokens, word, order = produce(source, action, obj, rng, cfg, audience=i)
                if interpret(listener, tokens, rng) == (action, obj) or rng.random() < cfg["repair"]:
                    learn(listener, obj, word, order, cfg["learning"])
                    listener.heard[j, obj] = word

    # Sample three local tutors. Commit all replacements after all children learn.
    for group in groups:
        replacements = []
        for slot in range(len(group)):
            if rng.random() < cfg["turnover"]:
                child = Speaker({obj: {} for obj in OBJECTS}, {})
                for tutor in rng.choices(group, k=3):
                    for obj in OBJECTS:
                        _, word, order = produce(tutor, "show", obj, rng)
                        learn(child, obj, word, order, 1.0)
                replacements.append((slot, child))
        for slot, child in replacements:
            group[slot] = child


def profile(group, obj=None):
    """Mean of individual production distributions; each speaker gets equal weight."""
    result = Counter()
    for person in group:
        weights = person.orders if obj is None else person.lexicon[obj]
        mass = sum(weights.values())
        for k, v in weights.items():
            result[k] += v / mass / len(group)
    return result


def distance(a, b):
    return sum(abs(a[k] - b[k]) for k in sorted(a.keys() | b.keys())) / 2


def measure(groups, cfg, seed, t):
    pairs = list(combinations(groups, 2))
    lexical = mean(distance(profile(a, obj), profile(b, obj)) for a, b in pairs for obj in OBJECTS)
    grammar = mean(distance(profile(a), profile(b)) for a, b in pairs)
    hits = trials = 0
    rng = Random(f"probe:{seed}:{t}")  # Read-only, including during complete isolation.
    for a, b in permutations(groups, 2):
        for _ in range(cfg["probes_per_direction"]):
            speaker, listener = rng.choice(a), rng.choice(b)
            action, obj = rng.choice(ACTIONS), rng.choice(OBJECTS)
            tokens, _, _ = produce(speaker, action, obj, rng)
            hits += interpret(listener, tokens, rng) == (action, obj)
            trials += 1
    return lexical, grammar, hits / trials


def experiment(cfg, seed):
    """Yield the shared baseline and the two matched histories at both endpoints."""
    groups = founders(cfg)
    split = cfg["shared_rounds"]
    end_isolation = split + cfg["isolation_rounds"]
    end = end_isolation + cfg["reconnection_rounds"]
    for t in range(1, split + 1):
        round_of_talk(groups, cfg["contact"], cfg, Random(f"talk:{seed}:{t}"))
    yield "shared", split, groups, measure(groups, cfg, seed, split)
    for arm in ("sustained", "isolated"):
        world = deepcopy(groups)
        for t in range(split + 1, end + 1):
            contact = 0 if arm == "isolated" and t <= end_isolation else cfg["contact"]
            round_of_talk(world, contact, cfg, Random(f"talk:{seed}:{t}"))
            if t in (end_isolation, end):
                yield arm, t, deepcopy(world), measure(world, cfg, seed, t)
