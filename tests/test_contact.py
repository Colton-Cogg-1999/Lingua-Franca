import unittest

try:
    import numpy as np
except ImportError:
    np = None

if np is not None:
    from lingua_franca import contact


@unittest.skipIf(np is None, "contact pilot requires the analysis extra")
class ContactTests(unittest.TestCase):
    def test_schedules_diverge_only_during_treatment(self):
        world = contact.initial_world(1)
        for gen in (10, 51):
            base, count = contact.transmit(world, 19, gen, "sustained")
            for branch in ("isolated", "fragmented"):
                other, remote = contact.transmit(world, 19, gen, branch)
                self.assertEqual(remote, count)
                np.testing.assert_array_equal(base.sounds, other.sounds)
                np.testing.assert_array_equal(base.roots, other.roots)

    def test_treatment_routes_and_copy_budget(self):
        shape = (contact.REGIONS, contact.MEANINGS)
        # Negative root labels identify the tutor's region. Replacements have positive IDs.
        world = contact.Lexicon(
            np.broadcast_to(-contact.REGION - 1, shape), contact.initial_world(2).sounds
        )
        for branch in contact.BRANCHES:
            next_world, remote = contact.transmit(world, 19, 11, branch)
            self.assertEqual(next_world.roots.shape, shape)
            inherited = next_world.roots < 0
            displacement = abs(next_world.roots + 1 + contact.REGION)[inherited]
            if branch == "isolated":
                self.assertTrue((displacement == 0).all())
                self.assertEqual(remote, 0)
            if branch == "fragmented":
                self.assertTrue((displacement <= 1).all())
                self.assertGreater(remote, 0)

    def test_probes_split_ties_and_ignore_genealogy(self):
        shape = (contact.REGIONS, contact.MEANINGS)
        sounds = np.zeros((*shape, 4), dtype=int)
        roots = contact.REGION * contact.MEANINGS + contact.MEANING
        rows = contact.measure(contact.Lexicon(roots, sounds))
        self.assertEqual(len(rows), contact.REGIONS * (contact.REGIONS - 1))
        for _, _, credit, shared, errors in rows:
            self.assertAlmostEqual(credit, 1 / contact.MEANINGS)
            self.assertEqual((shared, errors), (0, 0))
