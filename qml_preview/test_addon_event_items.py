"""Exhaustive killer addon-pool audit and survivor event-item restrictions."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dbd_randomizer as R
from rotation_engine import RotationState, make_rotated_build
from tools.addon_names_ru_en import ADDON_RU_EN

QML = Path(__file__).with_name("Main.qml").read_text(encoding="utf-8")


class AllKillerAddonPoolTests(unittest.TestCase):
    def test_every_killer_canonical_pool_has_usable_unique_mapped_icons(self):
        db = R.db_defaults()
        self.assertGreaterEqual(len(db["killers"]), 44)
        for killer, info in db["killers"].items():
            with self.subTest(killer=killer):
                pool = list(R._playable_addons(info["addons"]))
                self.assertGreaterEqual(len(pool), 2)
                self.assertEqual(len(pool), len(set(pool)), "duplicate addon name")
                known = ADDON_RU_EN[killer]
                self.assertTrue(set(pool).issubset(known), "RU→EN mapping missing")
                self.assertTrue(set(pool).issubset(R.ICONS.ADDON_ICONS),
                                "addon image missing")

                # Force every entry through the actual build constructor.
                # A random sampling test could miss a rare addon by chance.
                original_pick = R._pick
                for expected in pool:
                    def force_pick(candidates, count, expected=expected):
                        choices = list(dict.fromkeys(candidates))
                        if count == 2 and expected in choices:
                            other = next((a for a in choices if a != expected), None)
                            return [expected] + ([other] if other else [])
                        return original_pick(candidates, count)
                    with mock.patch.object(R, "_pick", side_effect=force_pick):
                        result = R.make_killer_build(
                            db, [killer], skin_enabled=False, respect_owned=False)
                    self.assertIn(expected, result["addons"])
                    self.assertEqual(len(result["addons"]), 2)
                    self.assertEqual(len(set(result["addons"])), 2)

    def test_diagnostic_explains_ownership_for_non_doctor(self):
        db = R.db_defaults()
        first = R._playable_addons(db["killers"]["Охотник"]["addons"])[0]
        db["owned"]["killer_addons"] = [first]
        self.assertIn("Только отмеченные",
                      R.killer_addon_diagnostic(db, "Охотник", True))
        self.assertEqual(R.killer_addon_diagnostic(db, "Охотник", False), "")

    def test_diagnostic_preserves_manually_shortened_catalog(self):
        db = R.db_defaults()
        canonical = list(db["killers"]["Охотник"]["addons"])
        db["killers"]["Охотник"]["addons"] = canonical[:2]
        warning = R.killer_addon_diagnostic(db, "Охотник", False)
        self.assertIn("Локальная база содержит 2 из", warning)
        self.assertEqual(db["killers"]["Охотник"]["addons"], canonical[:2])


class EventItemToggleTests(unittest.TestCase):
    def setUp(self):
        self.db = R.db_defaults()
        self.names = list(self.db["survivors"])[:3]
        self.events = set(R.DATA.EVENT_SURVIVOR_ITEMS)
        self.limited = set(R.DATA.LIMITED_SURVIVOR_ITEMS)

    def test_event_names_are_explicit_and_exist_in_catalog(self):
        present = {x for data in self.db["survivor_items"].values()
                   for x in data["items"]}
        self.assertEqual(len(self.events), 15)
        self.assertTrue(self.events.issubset(present))
        self.assertTrue(self.limited.issubset(present))
        self.assertFalse(self.events & self.limited)
        self.assertNotIn("Флакон Виго с туманом", self.events)

    def test_normal_generator_never_returns_event_when_disabled(self):
        seen = set()
        for _ in range(160):
            result = R.make_survivor_build(
                self.db, self.names, skin_enabled=False, event_items_enabled=False)
            item = result["power_or_item"]
            self.assertNotIn(item, self.events | self.limited)
            self.assertIn(item, self.db["survivor_items"][result["category"]]["items"])
            seen.add(result["category"])
        self.assertIn("Предметы с туманом", seen)
        self.assertNotIn("Хлопушки", seen)

    def test_balanced_rotation_obeys_the_same_exclusion(self):
        rotation = RotationState()
        for _ in range(125):
            result = make_rotated_build(
                R, self.db, "SURVIVOR", self.names, rotation,
                skin_enabled=False, addons_enabled=True,
                event_items_enabled=False)
            self.assertNotIn(result["power_or_item"], self.events | self.limited)
            self.assertNotEqual(result["category"], "Хлопушки")
            rotation.record_build(result, R.EMPTY, R.NO_ADDONS)

    def test_all_owned_items_filtered_produces_empty_slots_not_event(self):
        only_event = next(iter(sorted(self.events)))
        self.db["owned"]["survivor_items"] = [only_event]
        default = R.make_survivor_build(
            self.db, self.names, skin_enabled=False,
            respect_owned=True, event_items_enabled=False)
        self.assertEqual(default["power_or_item"], R.EMPTY)
        self.assertEqual(default["addons"], [R.EMPTY, R.EMPTY])
        balanced = make_rotated_build(
            R, self.db, "SURVIVOR", self.names, RotationState(),
            respect_owned=True, skin_enabled=False, event_items_enabled=False)
        self.assertEqual(balanced["power_or_item"], R.EMPTY)
        self.assertEqual(balanced["addons"], [R.EMPTY, R.EMPTY])

    def test_event_setting_keeps_regular_items_and_default_behavior(self):
        self.assertTrue(R.OPTION_DEFAULTS["event_items_enabled"])
        self.assertIn("Китайская хлопушка", self.events)
        for category, info in self.db["survivor_items"].items():
            enabled = R._survivor_item_pool(info, event_items_enabled=True)
            disabled = R._survivor_item_pool(info, event_items_enabled=False)
            self.assertTrue(set(disabled).issubset(enabled), category)
            self.assertTrue(set(disabled).isdisjoint(self.events | self.limited))
            self.assertTrue(set(enabled).isdisjoint(self.limited))

    def test_qml_toggle_is_survivor_only_in_both_places(self):
        self.assertIn('id: buildEventItemsOption', QML)
        self.assertGreaterEqual(QML.count('keyName: "event_items"'), 2)
        self.assertGreaterEqual(QML.count('visible: backend.role === "survivor"'), 2)
        self.assertIn('title: "Ивентовые предметы (выжившие)"', QML)


if __name__ == "__main__":
    unittest.main()
