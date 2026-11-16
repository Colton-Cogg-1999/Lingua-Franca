from copy import deepcopy
from dataclasses import replace
from http.server import ThreadingHTTPServer
import threading
import unittest
from galapagos.game import Game, GameConfig, digest, validate_topology
from galapagos.longrun import diagnostic, topology_for
from galapagos.regions import RegionHandler, RegionTransport


class RegionTests(unittest.TestCase):
    def test_shared_ancestry_and_isolated_inputs(self):
        game = Game(GameConfig(islands=3,population=3,shared_ancestry=True,migration=1))
        self.assertEqual(game.state['speakers'][0]['lexicon'],game.state['speakers'][-1]['lexicon'])
        graph=[[0],[1],[2]]
        for task in game.tasks(graph):
            self.assertEqual({s['island'] for s in task['snapshot']['speakers']},{task['island']})
        events,_=game.step(topology=graph)
        self.assertFalse(any(e['kind']=='migration' for e in events))
        self.assertTrue(all(not e['cross_island'] for e in events if e['kind']=='conversation'))

    def test_selective_migration_and_contact(self):
        game=Game(GameConfig(islands=3,population=5,migration=1,contact=1))
        graph=[[0,1],[0,1],[2]]
        events,_=game.step(topology=graph)
        for event in events:
            if event['kind']=='migration':
                self.assertIn(event['destination'],graph[event['source']])
            if event['kind']=='conversation':
                self.assertIn(event['source_island'],graph[event['island']])

    def test_peer_transport_matches_reference_and_stages_only_own_region(self):
        servers,threads,urls=[],[],[]
        try:
            for region in range(3):
                server=ThreadingHTTPServer(('127.0.0.1',0),RegionHandler)
                server.region=region
                server.snapshots={}
                server.snapshot_lock=threading.Lock()
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                servers.append(server); threads.append(thread)
                urls.append(f'http://127.0.0.1:{server.server_port}')
            config=GameConfig(population=3,shared_ancestry=True,innovation=.05,sound_change=.1,retention=.98)
            reference,remote=Game(config),Game(config)
            for graph in ([[0,1,2]]*3,[[0],[1],[2]],[[0,1],[0,1],[2]]):
                self.assertEqual(reference.step(topology=graph),remote.step(RegionTransport(urls),graph))
                for server in servers:
                    for staged in server.snapshots.values():
                        self.assertTrue(all(s['island']==server.region for s in staged['snapshot']['speakers']))
            self.assertEqual(reference.state,remote.state)
        finally:
            for server in servers:
                server.shutdown(); server.server_close()
            for thread in threads: thread.join()

    def test_read_only_comprehension_audit(self):
        game=Game(GameConfig(population=3,shared_ancestry=True))
        before=deepcopy(game.state)
        measurement=diagnostic(game,samples=5)
        self.assertEqual(before,game.state)
        self.assertEqual(measurement['source_by_listener'],[[1.0]*3]*3)

    def test_memory_and_novel_forms_remain_finite(self):
        game=Game(GameConfig(population=3,retention=.5,innovation=1,construction_innovation=1,sound_change=1,compact_events=True))
        for _ in range(15):
            events,_=game.step()
            for person in game.state['speakers']:
                for evidence in [*person['lexicon'].values(),person['constructions']]:
                    self.assertTrue(evidence)
                    self.assertTrue(all(v>0 for v in evidence.values()))
            for event in events:
                if event['kind']=='conversation':
                    self.assertNotIn('before',event)
                    self.assertIn('evidence',event)

    def test_topology_must_be_symmetric(self):
        with self.assertRaises(ValueError):
            validate_topology([[0,1],[1]],2)


if __name__=='__main__':
    unittest.main()
