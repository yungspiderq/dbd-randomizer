"""Fast headless regression tests for the native Qt backend."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
import dbd_randomizer as core
import native_backend
import qt_updater


class QtBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qtapp = QApplication.instance() or QApplication(["dbd-qt-test"])

    def setUp(self):
        self.cfg = core.default_config()
        self.cfg["options"]["skin_enabled"] = False
        self.cfg["timings"]["countdown"] = 0
        self.cfg["timings"]["search_settle"] = 0
        self.cfg["timings"]["after_slot_click"] = 0
        self.cfg["timings"]["between_steps"] = 0
        for val in self.cfg["coords"].values():
            val["x"] = "100"
            val["y"] = "100"
        self.patches = [
            patch.object(core, "load_config", return_value=(self.cfg, False)),
            patch.object(core, "load_db", side_effect=core.db_defaults),
            patch.object(core, "save_config"),
            patch.object(native_backend.QtBridge, "_hotkey"),
            patch.object(native_backend, "IconStore"),
            patch.object(core, "_load_tk", side_effect=AssertionError("Tk should not load")),
        ]
        for p in self.patches:
            p.start()
        self.bridge = native_backend.QtBridge()

    def tearDown(self):
        self.bridge.close()
        for p in reversed(self.patches):
            p.stop()

    def test_native_backend_no_tk_and_both_roles(self):
        self.assertEqual(self.bridge.role, "survivor")
        self.bridge.generate()
        self.assertEqual(len(self.bridge.build["perks"]), 4)
        self.assertEqual(len(self.bridge.perks), 4)
        self.bridge.setRole("killer")
        self.bridge.generate()
        self.assertEqual(self.bridge.build["side"], "KILLER")
        self.assertEqual(len(self.bridge.build["addons"]), 2)

    def test_settings_mode_and_character_filter(self):
        self.bridge.setMode("any")
        self.assertEqual(self.bridge.mode, "any")
        self.bridge.toggleOption("dry")
        self.assertTrue(self.bridge.options["dry"])
        s = next(x["name"] for x in self.bridge.characters if x["side"] == "S")
        self.bridge.setCharacter(s, "S")
        self.assertNotIn(s, self.bridge.available_characters("SURVIVOR"))

    def test_lock_and_reroll(self):
        self.bridge.generate()
        self.bridge.toggleLock(0)
        original = self.bridge.perks[0]["name"]
        self.bridge.rerollPerks()
        self.assertEqual(self.bridge.perks[0]["name"], original)

    def test_dry_run_never_changes_equipped_tracking(self):
        self.bridge.generate()
        self.bridge.toggleOption("dry")
        self.bridge.equip()
        self.bridge._worker.join(timeout=12)
        self.assertFalse(self.bridge._worker.is_alive())
        self.assertEqual(self.bridge.cfg.get("last_equipped", {}), {})

    def test_character_panels_and_filtered_bulk_actions(self):
        entries = self.bridge.characters
        self.assertTrue(any(c["side"] == "K" for c in entries))
        self.assertTrue(any(c["side"] == "S" for c in entries))
        self.bridge.setCharactersBulk("K", "none", "")
        self.assertFalse(self.bridge.available_characters("KILLER"))
        self.assertEqual(self.cfg["owned"]["killers"], ["__none__"])
        self.bridge.setCharactersBulk("K", "all", "")
        self.assertTrue(self.bridge.available_characters("KILLER"))
        target = next(c["name"] for c in self.bridge.characters if c["side"] == "S")
        self.bridge.setCharactersBulk("S", "none", target)
        match = next(c for c in self.bridge.characters if c["side"] == "S" and c["name"] == target)
        self.assertFalse(match["owned"])

    def test_skin_gallery_default_and_bulk_ownership(self):
        if not core.SKINS:
            self.skipTest("No skins database")
        names = self.bridge.skinCharacters
        self.assertTrue(names)
        first = next((x for x in names if x["side"] == "S" and x["count"] > 0), None)
        self.assertIsNotNone(first)
        self.bridge.setSkinCharacter(first["name"])
        stats = self.bridge.skinStats
        self.assertEqual(stats["owned"], stats["total"])
        first_skin = self.bridge.skins[0]
        self.assertIn("rarity", first_skin)
        self.assertIn("date", first_skin)
        self.assertIn("type", first_skin)
        self.bridge.toggleSkin(first_skin["id"])
        self.assertEqual(self.bridge.skinStats["owned"], stats["total"]-1)
        self.bridge.setSkinsOwned("none")
        self.assertEqual(self.bridge.skinStats["owned"], 0)
        self.assertEqual(self.bridge.randomSkinId(), -1)
        self.bridge.setSkinsOwned("all")
        self.assertEqual(self.bridge.skinStats["owned"], stats["total"])
        self.assertIn(self.bridge.randomSkinId(), [x["id"] for x in self.bridge.skins])

    def test_invalid_custom_build_rejected(self):
        self.bridge.buildCustom("SURVIVOR", "nonexistent", "", "", "", "x", "x", "x", "x")
        self.assertIsNone(self.bridge.build)

    def test_future_updates_use_explicit_semver(self):
        self.assertLess(qt_updater._key("v2.28.0-qt-beta.2"), qt_updater._key("v2.28.0-qt-beta.3"))
        self.assertIsNone(qt_updater._key("v2.28.0"))
        with self.assertRaises(ValueError):
            qt_updater._get("https://attacker.example/test")


if __name__ == "__main__":
    unittest.main()
