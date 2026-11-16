import tempfile
import unittest
from pathlib import Path
from galapagos.model import Config, Simulation


class ModelTests(unittest.TestCase):
    def test_reproducible_events(self):
        a, b = [], []
        first = Simulation(Config(population=8), a.append)
        second = Simulation(Config(population=8), b.append)
        for _ in range(5):
            first.step()
            second.step()
        self.assertEqual(a, b)

    def test_migration_conserves_population_and_probabilities(self):
        sim = Simulation(Config(population=8, migration=1, turnover=1, innovation=1))
        for _ in range(10):
            sim.step()
            self.assertEqual(len(sim.speakers), 24)
            self.assertEqual(len({s.id for s in sim.speakers}), 24)
            for s in sim.speakers:
                for row in s.repertoire:
                    self.assertAlmostEqual(sum(row), 1)
                    self.assertTrue(all(0 <= p <= 1 for p in row))

    def test_checkpoint_continues_identically(self):
        sim = Simulation(Config(population=8))
        sim.step()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            sim.checkpoint(path)
            resumed = Simulation.restore(path)
        for _ in range(5):
            self.assertEqual(sim.step(), resumed.step())
            self.assertEqual(sim.speakers, resumed.speakers)

    def test_isolation_prevents_cross_island_contact(self):
        events = []
        sim = Simulation(Config(population=8, contact=0, migration=0, turnover=0), events.append)
        for _ in range(3):
            sim.step()
        islands = {s.id: s.island for s in sim.speakers}
        for event in events:
            if event['kind'] == 'interaction':
                self.assertEqual(islands[event['speaker']], islands[event['listener']])

    def test_no_learning_no_change(self):
        sim = Simulation(Config(population=8, learning_rate=0, turnover=0, migration=0))
        before = sim.summary()['islands']
        for _ in range(4):
            sim.step()
        self.assertEqual(before, sim.summary()['islands'])

    def test_singleton(self):
        sim = Simulation(Config(islands=1, population=1, turnover=1))
        self.assertIsNone(sim.step()['expected_agreement'])

    def test_validation(self):
        for kwargs in ({'population': 0}, {'migration': -1}, {'learning_rate': float('nan')}):
            with self.assertRaises(ValueError):
                Config(**kwargs)


if __name__ == '__main__':
    unittest.main()
