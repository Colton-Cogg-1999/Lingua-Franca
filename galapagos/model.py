from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random


@dataclass(frozen=True)
class Config:
    seed: int = 42
    islands: int = 3
    population: int = 100  # per island, initially
    meanings: int = 8
    variants: int = 3
    interactions: int = 4  # per speaker per round
    learning_rate: float = 0.15
    innovation: float = 0.005
    migration: float = 0.01
    contact: float = 0.03
    turnover: float = 0.02
    prestige_bias: float = 0.5
    local_ties: float = 0.8

    def __post_init__(self):
        for key in ('islands', 'population', 'meanings', 'variants', 'interactions'):
            value = getattr(self, key)
            if type(value) is not int or value < 1:
                raise ValueError(f'{key} must be a positive integer')
        if self.variants < 2:
            raise ValueError('at least two variants are required')
        for key in ('learning_rate', 'innovation', 'migration', 'contact',
                    'turnover', 'prestige_bias', 'local_ties'):
            value = getattr(self, key)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f'{key} must be between zero and one')


@dataclass
class Speaker:
    id: int
    island: int
    prestige: float
    repertoire: list[list[float]]


class Simulation:
    """Sequential stochastic interaction, followed by simultaneous migration/turnover.

    Prestige is a synthetic individual attribute, independent of language variant.
    Island-local ring contacts are rebuilt each round, so ties do not survive moves.
    """
    def __init__(self, config=Config(), emit=None):
        self.config = config
        self.rng = random.Random(config.seed)
        self.round = 0
        self.sequence = 0
        self.emit = emit or (lambda event: None)
        self.run_id = hashlib.sha256(json.dumps(asdict(config), sort_keys=True).encode()).hexdigest()[:16]
        self.speakers = []
        self.next_id = 0
        for island in range(config.islands):
            for _ in range(config.population):
                # Shared vocabulary, different initial frequencies; no variant is superior.
                rows = []
                for meaning in range(config.meanings):
                    row = [0.2 / (config.variants - 1)] * config.variants
                    row[(island + meaning) % config.variants] = 0.8
                    rows.append(row)
                self.speakers.append(Speaker(self.next_id, island, self.rng.random(), rows))
                self.next_id += 1
        self.event('initialized', config=asdict(config), speakers=[asdict(s) for s in self.speakers])

    def event(self, kind, **payload):
        self.emit(dict(schema=1, run_id=self.run_id, event_id=f'{self.run_id}:{self.sequence}',
                       sequence=self.sequence, round=self.round, kind=kind, **payload))
        self.sequence += 1

    def step(self):
        c, rng = self.config, self.rng
        self.round += 1
        groups = [[s for s in self.speakers if s.island == i] for i in range(c.islands)]
        neighbors = {}
        for group in groups:
            for index, speaker in enumerate(group):
                neighbors[speaker.id] = list({group[(index + offset) % len(group)].id:
                    group[(index + offset) % len(group)] for offset in (-2, -1, 1, 2)
                    if group[(index + offset) % len(group)].id != speaker.id}.values())
        order = self.speakers[:]
        rng.shuffle(order)
        success, count = 0.0, 0
        for listener in order:
            for _ in range(c.interactions):
                if rng.random() < c.contact:
                    pool = [s for s in self.speakers if s.island != listener.island]
                elif rng.random() < c.local_ties:
                    pool = neighbors[listener.id]
                else:
                    pool = [s for s in groups[listener.island] if s.id != listener.id]
                if not pool:
                    continue
                source = rng.choice(pool)
                meaning = rng.randrange(c.meanings)
                variant = rng.choices(range(c.variants), source.repertoire[meaning])[0]
                innovative = rng.random() < c.innovation
                if innovative:
                    variant = (variant + rng.randrange(1, c.variants)) % c.variants
                old = listener.repertoire[meaning]
                # Expected agreement before learning; not an empirical comprehension metric.
                success += old[variant]
                count += 1
                rate = c.learning_rate * ((1 - c.prestige_bias) + c.prestige_bias * source.prestige)
                listener.repertoire[meaning] = [p * (1 - rate) + rate * (v == variant)
                                                for v, p in enumerate(old)]
                self.event('interaction', island=listener.island, speaker=source.id,
                           listener=listener.id, meaning=meaning, variant=variant,
                           innovation=innovative, learning_rate=rate)
        # Determine all moves before changing island membership.
        moves = []
        for s in self.speakers:
            if c.islands > 1 and rng.random() < c.migration:
                destination = (s.island + rng.randrange(1, c.islands)) % c.islands
                moves.append((s, destination))
        for s, destination in moves:
            self.event('migration', speaker=s.id, source=s.island, destination=destination)
            s.island = destination
        groups = [[s for s in self.speakers if s.island == i] for i in range(c.islands)]
        replacements = []
        for index, adult in enumerate(self.speakers):
            if rng.random() < c.turnover:
                tutors = rng.choices(groups[adult.island], k=3)
                rows = []
                for meaning in range(c.meanings):
                    # Finite cultural samples allow stochastic intergenerational change.
                    counts = [0] * c.variants
                    for tutor in tutors:
                        counts[rng.choices(range(c.variants), tutor.repertoire[meaning])[0]] += 1
                    rows.append([n / len(tutors) for n in counts])
                child = Speaker(self.next_id, adult.island, rng.random(), rows)
                self.next_id += 1
                replacements.append((index, child))
                self.event('cohort_replacement', departed=adult.id, tutors=[s.id for s in tutors],
                           newcomer=asdict(child))
        for index, child in replacements:
            self.speakers[index] = child
        summary = self.summary()
        summary['expected_agreement'] = success / count if count else None
        summary['interactions'] = count
        self.event('round_completed', summary=summary)
        return summary

    def summary(self):
        c = self.config
        islands = []
        for island in range(c.islands):
            group = [s for s in self.speakers if s.island == island]
            frequencies = [[sum(s.repertoire[m][v] for s in group) / len(group)
                            for v in range(c.variants)] for m in range(c.meanings)] if group else None
            entropy = (sum(-sum(p * math.log2(p) for p in row if p) for row in frequencies)
                       / c.meanings) if group else None
            islands.append(dict(island=island, population=len(group), frequencies=frequencies,
                                mean_entropy_bits=entropy))
        occupied = [i['frequencies'] for i in islands if i['population']]
        distances = [sum(abs(a[m][v] - b[m][v]) for m in range(c.meanings)
                         for v in range(c.variants)) / (2 * c.meanings)
                     for index, a in enumerate(occupied) for b in occupied[index + 1:]]
        return dict(round=self.round, islands=islands,
                    mean_between_island_distance=sum(distances) / len(distances) if distances else 0)

    def checkpoint(self, path):
        from pathlib import Path
        payload = dict(config=asdict(self.config), round=self.round, sequence=self.sequence,
                       next_id=self.next_id, speakers=[asdict(s) for s in self.speakers],
                       rng=self.rng.getstate())
        target = Path(path)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload))
        temporary.replace(target)

    @classmethod
    def restore(cls, path, emit=None):
        from pathlib import Path
        data = json.loads(Path(path).read_text())
        sim = cls(Config(**data['config']))
        sim.emit = emit or (lambda event: None)
        sim.round, sim.sequence, sim.next_id = data['round'], data['sequence'], data['next_id']
        sim.speakers = [Speaker(**s) for s in data['speakers']]
        def tuples(value):
            return tuple(tuples(x) for x in value) if isinstance(value, list) else value
        sim.rng.setstate(tuples(data['rng']))
        return sim
