"""Regression tests for detailed perks and pins across full build regeneration."""
import random
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dbd_randomizer as core
from perk_cards import perk_info, reconcile_pins


class PerkCardTests(unittest.TestCase):
    def setUp(self):
        self.db = core.db_defaults()
        self.killer_names = list(self.db["killers"])

    def _killer(self, name=None, fx=None):
        return core.make_killer_build(
            self.db, [name or self.killer_names[0]], perk_mode="any",
            skin_enabled=False, addons_enabled=False, fx=fx or {})

    def test_perk_details_are_grounded_in_original_character_database(self):
        char = self.killer_names[0]
        skill = self.db["killers"][char]["perks"][0]
        data = perk_info(self.db, "KILLER", skill, empty=core.EMPTY)
        self.assertTrue(data["found"])
        self.assertIn(char, data["owner"])
        self.assertEqual(data["kind"], "Уникальный навык")
        common = self.db["killer_common_perks"][0]
        meta = perk_info(self.db, "KILLER", common, empty=core.EMPTY)
        self.assertTrue(meta["common"])
        self.assertEqual(meta["kind"], "Общий навык")
        self.assertFalse(perk_info(self.db, "KILLER", core.EMPTY, empty=core.EMPTY)["found"])

    def test_all_built_in_perks_have_nonempty_russian_summaries(self):
        from perk_descriptions import description_for, PERK_DESCRIPTIONS
        for side, characters, common in (
            ("KILLER", self.db["killers"], self.db["killer_common_perks"]),
            ("SURVIVOR", self.db["survivors"], self.db["surv_common_perks"]),
        ):
            all_perks = set(common)
            for profile in characters.values():
                all_perks.update(profile.get("perks", []) if isinstance(profile, dict)
                                 else profile)
            self.assertEqual(all_perks, set(PERK_DESCRIPTIONS[side]),
                             "Descriptions drifted from the actual generator catalog")
            for name in all_perks:
                summary = description_for(side, name)
                self.assertTrue(summary and len(summary) >= 30, name)
                meta = perk_info(self.db, side, name, empty=core.EMPTY)
                self.assertEqual(meta["description"], summary)
        self.assertEqual(sum(len(d) for d in PERK_DESCRIPTIONS.values()), 320)
        self.assertEqual(description_for("KILLER", "Навык, которого нет"), "")
        self.assertEqual(description_for("SURVIVOR", ""), "")

    def test_pin_survives_full_generation_without_duplicate_skills(self):
        old = self._killer()
        nxt = self._killer(self.killer_names[1])
        keep = old["perks"][0]
        pins, dropped = reconcile_pins(self.db, old, [True, False, False, False],
                                       nxt, empty=core.EMPTY, rng=random.Random(3))
        self.assertTrue(pins[0])
        self.assertEqual(dropped, 0)
        self.assertEqual(nxt["perks"][0], keep)
        present = [x for x in nxt["perks"] if x != core.EMPTY]
        self.assertEqual(len(present), len(set(present)))

    def test_lock_all_persists_and_order_is_unchanged(self):
        old = self._killer()
        nxt = self._killer(self.killer_names[2])
        locks, n = reconcile_pins(self.db, old, [True]*4, nxt,
                                 empty=core.EMPTY, rng=random.Random(2))
        self.assertEqual(locks, [True]*4)
        self.assertEqual(n, 0)
        self.assertEqual(nxt["perks"], old["perks"])

    def test_challenge_specific_restriction_removes_invalid_pin(self):
        old = self._killer()
        blocked = old["perks"][0]
        nxt = self._killer(self.killer_names[1], {"ban_perks": [blocked]})
        pins, dropped = reconcile_pins(self.db, old, [True, False, False, False],
                                       nxt, empty=core.EMPTY)
        self.assertFalse(pins[0])
        self.assertEqual(dropped, 1)
        self.assertNotIn(blocked, nxt["perks"])

    def test_drop_all_perks_removes_all_locks(self):
        old = self._killer()
        nxt = self._killer(self.killer_names[1], {"drop": ["perks"]})
        pins, dropped = reconcile_pins(self.db, old, [True]*4, nxt, empty=core.EMPTY)
        self.assertEqual(pins, [False]*4)
        self.assertEqual(dropped, 4)

    def test_role_switch_unpins_all(self):
        old = self._killer()
        next_survivor = core.make_survivor_build(self.db,
                                                [next(iter(self.db["survivors"]))],
                                                skin_enabled=False)
        pins, dropped = reconcile_pins(self.db, old, [True, True, False, False],
                                       next_survivor, empty=core.EMPTY)
        self.assertEqual(pins, [False]*4)
        self.assertEqual(dropped, 2)

    def test_respect_owned_releases_unowned_pin(self):
        old = self._killer()
        name = old["perks"][0]
        new = self._killer(self.killer_names[1])
        self.db.setdefault("owned", {})["killer_perks"] = [
            p for p in (core.all_unique_perks(self.db, "KILLER") +
                        list(self.db["killer_common_perks"])) if p != name
        ]
        pins, dropped = reconcile_pins(self.db, old, [True, False, False, False],
                                       new, respect_owned=True, empty=core.EMPTY)
        self.assertFalse(pins[0])
        self.assertEqual(dropped, 1)

    def test_no_pins_keeps_generated_build_unchanged(self):
        old = self._killer()
        nxt = self._killer(self.killer_names[1])
        original = list(nxt["perks"])
        pins, dropped = reconcile_pins(self.db, old, [False]*4, nxt,
                                       empty=core.EMPTY)
        self.assertEqual(nxt["perks"], original)
        self.assertEqual(pins, [False]*4)
        self.assertEqual(dropped, 0)


if __name__ == "__main__":
    unittest.main()
