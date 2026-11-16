"""Small process pool with explicit simulated geography; no network isolation."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from .game import island_task, validate_topology


class LocalRegions:
    def __init__(self, workers=2):
        if type(workers) is not int or workers < 1:
            raise ValueError('workers must be a positive integer')
        self.pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))

    def map(self, function, tasks):
        if function is not island_task:
            raise ValueError('unsupported regional function')
        tasks = list(tasks)
        for task in tasks:
            allowed = set(task['topology'][task['island']])
            if any(person['island'] not in allowed for person in task['snapshot']['speakers']):
                raise ValueError('foreign population outside permitted simulation geography')
        return self.pool.map(function, tasks)

    def shutdown(self):
        self.pool.shutdown(wait=True, cancel_futures=True)


def check_visibility(game, topology):
    graph = validate_topology(topology, game.config.islands)
    populated = {s['island'] for s in game.state['speakers']}
    expected = [[j in neighbors and j in populated for j in range(game.config.islands)] for neighbors in graph]
    observed = []
    for task in game.tasks(graph):
        visible = {s['island'] for s in task['snapshot']['speakers']}
        observed.append([j in visible for j in range(game.config.islands)])
    if expected != observed:
        raise ValueError('local task visibility violates geographic restrictions')
    return dict(expected=expected, observed=observed, method='local_snapshot_visibility',
                network_isolation=False, note='Checks task inputs; no network probes or OS sandbox claim.')
