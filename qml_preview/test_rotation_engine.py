"""Regression checks for the optional frequency/recency-aware RNG."""
import random
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dbd_randomizer as core
from rotation_engine import RotationState, make_rotated_build


class RotationEngineTests(unittest.TestCase):
    def test_recent_killer_weight_shrinks_but_never_becomes_zero(self):
        state = RotationState(rng=random.Random(1))
        before = state.weights("KILLER", "characters", ["A", "B"])
        self.assertEqual(before["A"], before["B"])
        state.record("KILLER", "characters", ["A"])
        after = state.weights("KILLER", "characters", ["A", "B"])
        self.assertGreater(after["B"], after["A"])
        self.assertGreater(after["A"], 0)

    def test_broad_character_coverage_and_no_fixed_sequence(self):
        state = RotationState(rng=random.Random(9))
        candidates = [str(x) for x in range(20)]
        seq = []
        for _ in range(100):
            x = state.select("KILLER", "characters", candidates)[0]
            seq.append(x)
            state.record("KILLER", "characters", [x])
        info = state.info("KILLER", candidates)
        self.assertEqual(info["seen"], len(candidates))
        self.assertEqual(info["total"], 20)
        self.assertLessEqual(max(seq.count(x) for x in candidates) -
                             min(seq.count(x) for x in candidates), 5)
        self.assertTrue(any(seq[i] != seq[i+1] for i in range(99)))

    def test_serialization_reset_and_separate_roles(self):
        state = RotationState(rng=random.Random(1))
        state.record("KILLER", "characters", ["X"])
        state.record("SURVIVOR", "characters", ["Y"])
        restored = RotationState(state.serialize())
        self.assertEqual(restored.info("KILLER", ["X"])["seen"], 1)
        self.assertEqual(restored.info("SURVIVOR", ["Y"])["seen"], 1)
        restored.reset("KILLER")
        self.assertEqual(restored.info("KILLER", ["X"])["seen"], 0)
        self.assertEqual(restored.info("SURVIVOR", ["Y"])["seen"], 1)
        self.assertEqual(state.info("KILLER", ["X"])["seen"], 1)

    def test_select_without_replacement_and_scoped_addons(self):
        state = RotationState(rng=random.Random(3))
        choice = state.select("KILLER", "addons", ["a", "a", "b", "c"], count=3, scope="Охотник")
        self.assertEqual(set(choice), {"a", "b", "c"})
        state.record("KILLER", "addons", ["a"], scope="Охотник")
        own = state.weights("KILLER", "addons", ["a", "b"], scope="Охотник")
        other = state.weights("KILLER", "addons", ["a", "b"], scope="Другой")
        self.assertLess(own["a"], own["b"])
        self.assertEqual(other["a"], other["b"])

    def test_rotated_killer_build_uses_real_db_and_excludes_challenge_bans(self):
        db = core.db_defaults()
        killer_names = list(db["killers"])[:8]
        blocked = killer_names[0]
        rotation = RotationState(rng=random.Random(17))
        chars = []
        for _ in range(70):
            build = make_rotated_build(
                core, db, "KILLER", killer_names, rotation, perk_mode="any",
                addons_enabled=True, skin_enabled=False, respect_owned=False,
                fx={"ban_chars": [blocked]})
            self.assertIn(build["char"], killer_names[1:])
            self.assertNotEqual(build["char"], blocked)
            self.assertEqual(len(build["perks"]), 4)
            self.assertEqual(len(build["addons"]), 2)
            self.assertEqual(len(set(p for p in build["perks"] if p != core.EMPTY)),
                             len([p for p in build["perks"] if p != core.EMPTY]))
            addons = set(core._playable_addons(db["killers"][build["char"]]["addons"]))
            self.assertTrue(all(x in addons or x in (core.EMPTY, core.NO_ADDONS)
                                for x in build["addons"]))
            chars.append(build["char"])
            rotation.record_build(build, core.EMPTY, core.NO_ADDONS)
        self.assertEqual(set(chars), set(killer_names[1:]))

    def test_rotated_survivor_build_keeps_item_category_and_compatible_addons(self):
        db = core.db_defaults()
        rotation = RotationState(rng=random.Random(4))
        available = list(db["survivors"])[:4]
        for _ in range(24):
            build = make_rotated_build(
                core, db, "SURVIVOR", available, rotation, perk_mode="mixed",
                addons_enabled=True, skin_enabled=False, respect_owned=False, fx={})
            category = db["survivor_items"][build["category"]]
            self.assertIn(build["power_or_item"], category["items"])
            addon_set = set(core._playable_addons(category["addons"]))
            self.assertTrue(all(x in addon_set or x in (core.EMPTY, core.NO_ADDONS)
                                for x in build["addons"]))
            self.assertEqual(len(build["perks"]), 4)
            rotation.record_build(build, core.EMPTY, core.NO_ADDONS)

    def test_challenge_perk_constraints_and_no_accounting_disabled_slots(self):
        db = core.db_defaults()
        state = RotationState(rng=random.Random(33))
        all_killers = list(db["killers"])
        fx = {"perk_pool": "common", "drop": ["addons"]}
        b = make_rotated_build(core, db, "KILLER", all_killers[:6], state,
                               perk_mode="mixed", respect_owned=False,
                               addons_enabled=True, skin_enabled=False, fx=fx)
        self.assertTrue(all(x in db["killer_common_perks"] or x == core.EMPTY
                            for x in b["perks"]))
        state.record_build(b, core.EMPTY, core.NO_ADDONS)
        self.assertFalse(state._section("KILLER", "addons", scope=b["char"])["counts"])

    def test_invalid_rotation_payload_is_ignored_safely(self):
        state = RotationState({"KILLER": {"characters": {"counts": {"A": -100, "B": 3},
                                                          "recent": ["B", 4]}}},
                               rng=random.Random(1))
        self.assertEqual(state.info("KILLER", ["A", "B"])["seen"], 1)
        self.assertEqual(state.weights("KILLER", "characters", ["A", "B"])["A"], 1.0)


if __name__ == "__main__":
    unittest.main()
