from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path
import random
import tempfile
import unittest

from galapagos.game import Game, GameConfig, OBJECTS, digest, encounter, initialize, interpret, island_task, produce
from galapagos.play import commit, restore


class CommunicationTests(unittest.TestCase):
    def setUp(self):
        self.config = GameConfig(population=3, turnover=0, migration=0, innovation=0)
        state = initialize(self.config)
        self.source, self.listener = state['speakers'][0], state['speakers'][3]
        self.intention = dict(action='give', object='water')

    def test_unknown_language_does_not_leak_intention(self):
        utterance = produce(self.source, self.intention, random.Random(1))
        self.assertIsNone(interpret(self.listener, utterance['text'], OBJECTS, random.Random(1)))
        original = deepcopy(self.listener)
        event = encounter(self.source, self.listener, self.intention, replace(self.config, repair=0), random.Random(1))
        self.assertFalse(event['final_success'])
        self.assertEqual(original, self.listener)

    def test_grounding_learns_word_and_construction(self):
        event = encounter(self.source, self.listener, self.intention, replace(self.config, repair=1), random.Random(1))
        self.assertFalse(event['first_success'])
        self.assertTrue(event['repaired'])
        self.assertEqual(interpret(self.listener, event['utterance']['text'], OBJECTS, random.Random(2)), self.intention)
        self.assertEqual(self.listener['lexicon']['water']['nara'], 1)
        self.assertEqual(self.listener['constructions']['verb_object'], 1)
        # New knowledge affects production, not just displayed transcripts.
        productions = [produce(self.listener, self.intention, random.Random(seed))['word'] for seed in range(100)]
        self.assertIn('nara', productions)

    def test_no_learning_ablation(self):
        original = deepcopy(self.listener)
        event = encounter(self.source, self.listener, self.intention, replace(self.config, repair=1, learning=0), random.Random(1))
        self.assertTrue(event['final_success'])
        self.assertEqual(original, self.listener)
        self.assertIsNone(interpret(self.listener, 'give nara', OBJECTS, random.Random(2)))

    def test_homonym_interpretation_uses_listener_evidence(self):
        listener = deepcopy(self.source)
        listener['lexicon']['water'].clear()
        listener['lexicon']['stone']['nara'] = 10
        self.assertEqual(interpret(listener, 'give nara', OBJECTS, random.Random(1)), dict(action='give', object='stone'))
        event = encounter(self.source, listener, self.intention, replace(self.config, repair=1), random.Random(1))
        self.assertFalse(event['first_success'])
        self.assertTrue(event['repaired'])
        self.assertEqual(listener['lexicon']['water']['nara'], 1)

    def test_task_retry_and_result_order_invariance(self):
        a, b = Game(self.config), Game(self.config)
        tasks = a.tasks()
        results = [island_task(task) for task in tasks]
        self.assertEqual(results[0], island_task(tasks[0]))
        events_a, summary_a = a.apply(tasks, results)
        events_b, summary_b = b.apply(tasks, list(reversed(results)))
        self.assertEqual(a.state, b.state)
        self.assertEqual(events_a, events_b)
        self.assertEqual(summary_a, summary_b)
        with self.assertRaises(ValueError):
            a.apply(tasks, results)

    def test_invalid_results_cannot_partially_commit(self):
        game = Game(self.config)
        original = deepcopy(game.state)
        tasks = game.tasks()
        results = [island_task(task) for task in tasks]
        results[-1]['speakers'][0]['island'] = 999
        with self.assertRaises(ValueError):
            game.apply(tasks, results)
        self.assertEqual(original, game.state)
        with self.assertRaises(ValueError):
            game.apply(tasks, results[:-1])
        self.assertEqual(original, game.state)

    def test_process_count_does_not_change_results(self):
        serial, parallel = Game(self.config), Game(self.config)
        with ProcessPoolExecutor(max_workers=3, mp_context=multiprocessing.get_context('spawn')) as executor:
            for _ in range(3):
                self.assertEqual(serial.step(), parallel.step(executor))
        self.assertEqual(serial.state, parallel.state)

    def test_checkpoint_integrity_and_continuation(self):
        game = Game(self.config)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events, summary = game.step()
            folder = commit(root, game, events, summary)
            resumed = restore(root)
            for _ in range(3):
                self.assertEqual(game.step(), resumed.step())
            self.assertEqual(game.state, resumed.state)
            (folder / 'summary.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                restore(root)

    def test_conservation_with_migration_and_cohorts(self):
        game = Game(replace(self.config, migration=1, turnover=1))
        for _ in range(5):
            game.step()
            people = game.state['speakers']
            self.assertEqual(len(people), 9)
            self.assertEqual(len({s['id'] for s in people}), 9)
            for person in people:
                self.assertTrue(all(person['lexicon'][obj] for obj in OBJECTS))
                self.assertTrue(person['constructions'])

    def test_isolation_and_singleton(self):
        game = Game(replace(self.config, contact=0))
        events, _ = game.step()
        self.assertTrue(all(not e['cross_island'] for e in events if e['kind'] == 'conversation'))
        _, summary = Game(GameConfig(islands=1, population=1)).step()
        self.assertIsNone(summary['overall']['first_success'])

    def test_bad_configuration(self):
        for args in ({'learning': float('nan')}, {'population': 0}, {'repair': 2}, {'seed': True}):
            with self.assertRaises(ValueError):
                GameConfig(**args)


if __name__ == '__main__':
    unittest.main()
