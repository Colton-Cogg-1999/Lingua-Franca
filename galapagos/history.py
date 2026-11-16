"""Explicit synthetic ancestry and group diagnostics for historical analogues."""
from itertools import combinations
import math
from .game import OBJECTS, ORDERS


def validate_initialization(plan, config):
    initial = plan.get('initialization')
    if initial is None:
        return
    families, lexicons = initial['families'], initial['lexicons']
    shifts, share = initial['regional_shifts'], initial['regional_variant_share']
    if len(families) != config.islands or len(shifts) != config.islands:
        raise ValueError('initialization must specify each region')
    if not math.isfinite(share) or not 0 <= share < 1:
        raise ValueError('invalid regional variant share')
    for words in lexicons:
        if len(words) != len(OBJECTS) or len(set(words)) != len(words) or any(not isinstance(w, str) or not w or any(c.isspace() for c in w) for w in words):
            raise ValueError('family lexicon must contain distinct single-token forms')
    if len({w for words in lexicons for w in words}) != len(lexicons) * len(OBJECTS):
        raise ValueError('ancestral families must start with disjoint lexicons')
    if any(type(f) is not int or not 0 <= f < len(lexicons) for f in families):
        raise ValueError('invalid ancestry family')
    if any(shift is not None and (len(shift) != 2 or any(not isinstance(x, str) or not x for x in shift)) for shift in shifts):
        raise ValueError('invalid regional sound shift')
    for members in plan.get('measurement_groups', {}).values():
        if len(set(members)) != len(members) or any(type(i) is not int or not 0 <= i < config.islands for i in members):
            raise ValueError('invalid measurement group')


def seed_variation(game, plan):
    initial = plan.get('initialization')
    if initial is None:
        return
    validate_initialization(plan, game.config)
    for speaker in game.state['speakers']:
        region = speaker['island']
        family = initial['families'][region]
        words = initial['lexicons'][family]
        shift, share = initial['regional_shifts'][region], initial['regional_variant_share']
        speaker['lexicon'] = {}
        for concept, word in zip(OBJECTS, words):
            variant = word.replace(*shift) if shift else word
            speaker['lexicon'][concept] = ({word: 4 * (1-share), variant: 4 * share}
                                            if variant != word and share else {word: 4.0})
        speaker['constructions'] = {ORDERS[family % 2]: 4.0}


def group_metrics(summary, plan):
    groups = plan.get('measurement_groups', {})
    if not groups:
        return {}
    regions = {r['island']: r['frequencies'] for r in summary['islands']}
    def distance(a, b):
        if a not in regions or b not in regions:
            return None
        return sum(sum(abs(regions[a][c].get(w, 0) - regions[b][c].get(w, 0))
                       for w in regions[a][c].keys() | regions[b][c].keys()) / 2 for c in OBJECTS) / len(OBJECTS)
    within = {}
    for name, members in groups.items():
        values = [distance(a, b) for a, b in combinations(members, 2)]
        values = [v for v in values if v is not None]
        within[name] = sum(values)/len(values) if values else None
    between = {}
    for a, b in combinations(groups, 2):
        values = [distance(i, j) for i in groups[a] for j in groups[b] if i != j]
        values = [v for v in values if v is not None]
        between[a+'__'+b] = sum(values)/len(values) if values else None
    return dict(within_group_lexical_distance=within, between_group_lexical_distance=between)
