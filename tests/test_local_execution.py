from copy import deepcopy
from pathlib import Path
import json
import unittest
from galapagos.game import Game, GameConfig, island_task
from galapagos.history import seed_variation
from galapagos.local_execution import LocalRegions, check_visibility
from galapagos.longrun import topology_for, parameters_for

class LocalExecutionTests(unittest.TestCase):
    def test_local_pool_matches_reference_across_phases(self):
        plan=json.loads((Path(__file__).resolve().parents[1]/'examples/historical-smoke.json').read_text())
        config=GameConfig(**plan['config'])
        reference,local=Game(config),Game(config)
        seed_variation(reference,plan);seed_variation(local,plan)
        pool=LocalRegions(2)
        try:
            for n in range(1,19):
                _,graph=topology_for(plan,n);parameters=parameters_for(plan,n)
                checks=check_visibility(local,graph)
                self.assertEqual(checks['expected'],checks['observed'])
                self.assertFalse(checks['network_isolation'])
                self.assertEqual(reference.step(topology=graph,parameters=parameters),local.step(pool,graph,parameters))
            self.assertEqual(reference.state,local.state)
        finally:pool.shutdown()

    def test_reject_foreign_population(self):
        game=Game(GameConfig(islands=2,population=2))
        tasks=game.tasks([[0],[1]])
        tasks[0]['snapshot']['speakers'].append(deepcopy(game.state['speakers'][-1]))
        pool=LocalRegions(1)
        try:
            with self.assertRaises(ValueError):pool.map(island_task,tasks)
        finally:pool.shutdown()

if __name__=='__main__':unittest.main()
