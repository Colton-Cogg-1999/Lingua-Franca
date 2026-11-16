from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest

from galapagos.game import Game, GameConfig, OBJECTS, digest, island_task, summarize
from galapagos.history import seed_variation, group_metrics
from galapagos.longrun import validate_plan, parameters_for, topology_for, load_latest, diagnostic
from galapagos.play import commit

ROOT = Path(__file__).resolve().parents[1]

class HistoryTests(unittest.TestCase):
    def plan(self):
        return json.loads((ROOT/'examples/historical-smoke.json').read_text())

    def test_initial_variation_and_unrelated_comprehension(self):
        plan=self.plan(); config=validate_plan(plan); game=Game(config); seed_variation(game,plan)
        people=game.state['speakers']; self.assertNotEqual(people[0]['lexicon'],people[4]['lexicon'])
        for i in range(6):
            a=people[i*config.population]
            for j in range(6,10):
                b=people[j*config.population]
                self.assertFalse(set(w for forms in a['lexicon'].values() for w in forms) & set(w for forms in b['lexicon'].values() for w in forms))
        matrix=diagnostic(game, samples=10)['source_by_listener']
        self.assertTrue(all(matrix[i][j]==0 for i in range(6) for j in range(6,10)))
        self.assertTrue(all(matrix[i][i]==1 for i in range(10)))
        metrics=group_metrics(summarize(game.state,[]),plan)
        self.assertAlmostEqual(metrics['between_group_lexical_distance']['romance_analogue__external_comparisons'],1)

    def test_schedule_and_resume_identical_across_transition(self):
        plan=self.plan(); config=validate_plan(plan)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'rounds').mkdir()
            game=load_latest(root,config,'test-history',plan)
            for n in range(1,5):
                _,graph=topology_for(plan,n)
                events,summary=game.step(topology=graph,parameters=parameters_for(plan,n))
                commit(root,game,events,summary)
                self.assertEqual(game.config,config)
            resumed=load_latest(root,config,'test-history',plan)
            for n in range(5,19):
                _,graph=topology_for(plan,n); params=parameters_for(plan,n)
                self.assertEqual(game.step(topology=graph,parameters=params),resumed.step(topology=graph,parameters=params))
            self.assertEqual(game.state,resumed.state)

    def test_weighted_routes_exclude_zero_weight_peer(self):
        config=GameConfig(islands=3,population=10,encounters=10,contact=1,migration=0,friendship_bias=0,
                          route_weights=[[0,1,0],[1,0,1],[0,1,0]])
        game=Game(config); events,_=game.step()
        remote=[e for e in events if e['kind']=='conversation' and e['island']==0]
        self.assertTrue(remote); self.assertEqual({e['source_island'] for e in remote},{1})

    def test_minimum_population_and_temporary_config_on_failure(self):
        config=GameConfig(islands=3,population=5,migration=1,minimum_population=4)
        game=Game(config)
        for _ in range(10):
            game.step()
            self.assertTrue(all(sum(s['island']==i for s in game.state['speakers'])>=4 for i in range(3)))
        class Broken:
            def map(self,*args):raise RuntimeError('injected failure')
        before=deepcopy(game.state)
        with self.assertRaises(RuntimeError):game.step(Broken(),parameters={'contact':.001})
        self.assertEqual(game.config,config); self.assertEqual(game.state,before)

    def test_reject_invalid_phase_and_ancestry(self):
        plan=self.plan(); plan['phases'][0]['parameters']['population']=100
        with self.assertRaises(ValueError):validate_plan(plan)
        plan=self.plan(); plan['phases'][0]['edges'][0][2]=-1
        with self.assertRaises(ValueError):validate_plan(plan)
        plan=self.plan(); plan['initialization']['lexicons'][1][0]='nara'
        with self.assertRaises(ValueError):validate_plan(plan)

    def test_controls_match_declared_treatments(self):
        main=json.loads((ROOT/'examples/historical-main.json').read_text())
        related=json.loads((ROOT/'examples/historical-related.json').read_text())
        self.assertEqual(main['phases'],related['phases'])
        self.assertEqual(main['config'],related['config'])
        self.assertEqual(related['initialization']['families'],[0]*10)
        self.assertEqual(main['rounds'],(main['calendar']['end_year']-main['calendar']['start_year'])*main['calendar']['ticks_per_year'])
        self.assertEqual(main['rounds']-main['phases'][-2]['through'],350)

if __name__=='__main__':unittest.main()
