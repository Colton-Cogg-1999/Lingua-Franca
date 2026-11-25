import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from lingua_franca import contact as pilot
    from lingua_franca import receptive


@unittest.skipIf(np is None, "receptive study requires the analysis extra")
class ReceptiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = receptive.distance_table()

    def test_full_adoption_replays_pilot_after_reconnection(self):
        world = pilot.initial_world(4)
        memory = receptive.Memory()
        for gen in range(51, 59):
            expected, remote = pilot.transmit(world, 4, gen, "fragmented")
            world, exposures, copies = receptive.advance(
                world, memory, 4, gen, "restored", 1
            )
            self.assertEqual((exposures, copies), (remote, remote))
            np.testing.assert_array_equal(expected.roots, world.roots)
            np.testing.assert_array_equal(expected.sounds, world.sounds)

    def test_unadopted_forms_are_learned_from_previous_tutor(self):
        world = pilot.initial_world(2)
        shape = receptive.VOCAB_SHAPE
        # Every starting root is negative and identifies its source region.
        roots = np.broadcast_to(-pilot.REGION - 1, shape)
        memory = receptive.Memory()
        child, heard, copied = receptive.advance(
            pilot.Lexicon(roots, world.sounds), memory, 2, 51, "restored", 0
        )
        self.assertGreater(heard, 0)
        self.assertEqual(copied, 0)
        self.assertEqual((memory.heard == 51).sum(), heard)
        retained = child.roots < 0
        np.testing.assert_array_equal(child.roots[retained], roots[retained])
        self.assertEqual(
            (memory.heard != 51).sum(), np.prod(memory.heard.shape) - heard
        )

    def test_meaning_level_ties_memory_expiration_and_no_probe_feedback(self):
        world = pilot.initial_world(8)
        # All meanings use the same form everywhere except in region 0.
        sounds = np.broadcast_to(world.sounds[1, 0], world.sounds.shape).copy()
        sounds[0] = world.sounds[0]
        world = pilot.Lexicon(world.roots, sounds)
        mask = np.zeros(receptive.VOCAB_SHAPE, dtype=bool)
        mask[1] = True
        memory = receptive.Memory()
        forms = np.broadcast_to(sounds[0], sounds.shape)
        for gen in range(51, 55):
            memory.learn(forms, mask, gen)
        self.assertEqual(set(memory.heard[1].ravel()), {52, 53, 54})
        before = memory.forms.copy()
        local, recognized, *_ = receptive.probe(world, memory, 55, self.table)
        self.assertGreater(recognized, local)
        np.testing.assert_array_equal(before, memory.forms)
        expired = receptive.probe(world, memory, 62, self.table)
        self.assertEqual(expired[0], expired[1])
        self.assertAlmostEqual(
            expired[0], np.mean([r[2] for r in pilot.measure(world)])
        )
        ties = receptive.recognition(np.zeros((2, 40, 40)))
        np.testing.assert_allclose(ties, 1 / 40)
