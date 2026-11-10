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

    def test_balanced_mode_is_opt_in_and_persists(self):
        self.assertFalse(self.bridge.rotationEnabled)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.setRotationEnabled(True)
        self.assertTrue(self.bridge.rotationEnabled)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.assertTrue(self.cfg["options"]["rotation_enabled"])
        self.assertIn("rotation_state", self.cfg["options"])
        self.assertGreater(self.cfg["options"]["rotation_state"]["SURVIVOR"]["characters"]["counts"][self.bridge.build["char"]], 0)
        self.bridge.setRotationEnabled(False)
        self.assertFalse(self.bridge.rotationEnabled)
        self.assertEqual(self.bridge.rotationStats["seen"], 1)

    def test_rotation_side_isolation_and_confirmation_reset_backend(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.bridge.setRole("killer")
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.generate()
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.bridge.resetRotation()
        self.assertEqual(self.bridge.rotationStats["seen"], 0)
        self.bridge.setRole("survivor")
        self.assertEqual(self.bridge.rotationStats["seen"], 1)

    def test_balanced_mode_reroll_uses_weighted_perk_history(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        before = list(self.bridge.build["perks"])
        self.bridge.reroll(0)
        after = self.bridge.build["perks"]
        self.assertEqual(len(after), 4)
        self.assertNotEqual(after[0], before[0])
        self.assertEqual(len(set(after)), 4)

    def test_perk_details_owner_common_and_safe_reference(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        info = self.bridge.perkInfo(0)
        self.assertTrue(info["filled"])
        self.assertEqual(info["name"], self.bridge.perks[0]["name"])
        self.assertIn(info["kind"], ("Уникальный навык", "Общий навык"))
        self.assertTrue(info["found"])
        self.assertEqual(info["slot"], 1)

    def test_pinned_perks_survive_full_generate_and_have_no_duplicates(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        selected = self.bridge.perks[0]["name"]
        revision = self.bridge.buildRevision
        self.bridge.toggleLock(0)
        self.assertEqual(revision, self.bridge.buildRevision)
        self.bridge.generate()
        self.assertGreater(self.bridge.buildRevision, revision)
        self.assertEqual(self.bridge.perks[0]["name"], selected)
        self.assertTrue(self.bridge.perks[0]["locked"])
        names = [p["name"] for p in self.bridge.perks if p["filled"]]
        self.assertEqual(len(names), len(set(names)))

    def test_bulk_lock_and_unlock_affects_only_filled_slots(self):
        self.bridge.generate()
        self.bridge.setAllPerkLocks(True)
        self.assertEqual(self.bridge.lockedCount, 4)
        original = [p["name"] for p in self.bridge.perks]
        self.bridge.rerollPerks()
        self.assertEqual(original, [p["name"] for p in self.bridge.perks])
        self.bridge.setAllPerkLocks(False)
        self.assertEqual(self.bridge.lockedCount, 0)

    def test_new_challenge_can_release_incompatible_pinned_perks(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        self.bridge.setAllPerkLocks(True)
        dropping = {"side": "KILLER", "diff": 1, "ru": "Тестовое ограничение",
                    "text": "Без перков", "fx": {"drop": ["perks"]}}
        self.bridge._generate(preset_challenge=dropping)
        self.assertEqual(self.bridge.lockedCount, 0)
        self.assertTrue(self.bridge.build["forbidden"]["perks"])

    def test_statistics_tracks_both_modes_and_perk_rerolls(self):
        self.bridge.generate()
        overview = self.bridge.statistics["overview"]
        self.assertEqual(overview["generated"], 1)
        self.assertEqual(overview["classic"], 1)
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        overview = self.bridge.statistics["overview"]
        self.assertEqual(overview["generated"], 2)
        self.assertEqual(overview["balanced"], 1)
        self.assertEqual(len(self.bridge.statistics["recent"]), 2)
        self.bridge.reroll(0)
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 2)
        self.assertEqual(self.bridge.statistics["overview"]["rerolls"], 1)
        self.assertIn("statistics_v1", self.cfg["options"])

    def test_statistics_side_and_category_independent_from_build(self):
        self.bridge.generate()
        self.bridge.setStatisticsSide("KILLER")
        self.assertEqual(self.bridge.statisticsSide, "KILLER")
        self.assertEqual(self.bridge.role, "survivor")
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 0)
        self.bridge.setStatisticsGroup("perks")
        self.assertEqual(self.bridge.statisticsGroup, "perks")
        self.bridge.setStatisticsGroup("items")
        self.assertEqual(self.bridge.statisticsGroup, "perks")
        self.bridge.setStatisticsSide("SURVIVOR")
        self.bridge.setStatisticsGroup("items")
        self.assertEqual(self.bridge.statisticsGroup, "items")
        self.assertTrue(self.bridge.statistics["top"])

    def test_reset_statistics_does_not_reset_rotation(self):
        self.bridge.setRotationEnabled(True)
        self.bridge.generate()
        assert self.bridge.rotationStats["seen"] == 1
        self.bridge.resetStatistics()
        self.assertEqual(self.bridge.statistics["overview"]["generated"], 0)
        self.assertEqual(self.bridge.rotationStats["seen"], 1)
        self.assertTrue(self.bridge.rotationEnabled)

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

    def test_addons_have_real_names_and_two_labeled_slots(self):
        self.bridge.setRole("killer")
        self.bridge.generate()
        meta = self.bridge.detail
        self.assertEqual(len(meta["addonDetails"]), 2)
        for pos, addon in enumerate(meta["addonDetails"], 1):
            self.assertEqual(addon["slot"], pos)
            self.assertEqual(addon["raw"], self.bridge.build["addons"][pos - 1])
            self.assertEqual(addon["name"], self.bridge.build["addons"][pos - 1].strip())
            self.assertIsInstance(addon["filled"], bool)

    def test_full_challenge_rule_difficulty_and_equipment_restrictions(self):
        challenge = next(ch for ch in core.DATA.CHALLENGES
                         if ch.get("side") == "SURVIVOR"
                         and "item" in ch.get("fx", {}).get("drop", ()))
        self.bridge._generate(preset_challenge=challenge)
        metadata = self.bridge.detail
        self.assertEqual(metadata["challenge"], challenge["ru"])
        self.assertEqual(metadata["challengeText"], challenge["text"])
        self.assertEqual(metadata["challengeWhy"], challenge["why"])
        self.assertEqual(metadata["challengeDifficulty"], core.DATA.CHALLENGE_DIFFS[challenge["diff"]])
        self.assertTrue(any("Предмет" in part for part in metadata["challengeRestrictions"]))

    def test_visual_catalogs_match_generator_pools(self):
        chars = self.bridge.searchCharacters("KILLER", "")
        self.assertGreater(len(chars), 0)
        self.assertIn(chars[0]["name"], self.bridge.db["killers"])
        self.assertTrue(self.bridge.searchPerks("SURVIVOR", ""))
        killer = chars[0]["name"]
        result = self.bridge.searchAddons("KILLER", killer, "", "")
        playable = set(core._playable_addons(self.bridge.db["killers"][killer]["addons"]))
        self.assertTrue(all(x["name"] in playable for x in result))
        self.assertFalse(self.bridge.searchPerks("UNKNOWN", ""))

    def test_item_picker_and_addon_compatibility(self):
        items = self.bridge.searchItems("")
        self.assertTrue(items)
        item = items[0]
        category = self.bridge.db["survivor_items"][item["category"]]
        self.assertIn(item["name"], category["items"])
        suggestions = self.bridge.searchAddons("SURVIVOR", "", item["name"], "")
        expected = set(core._playable_addons(category.get("addons", [])))
        self.assertTrue(all(row["name"] in expected for row in suggestions))
        self.assertEqual(self.bridge.searchAddons("SURVIVOR", "", "", ""), [])
        self.bridge.buildCustom("SURVIVOR",
                                next(iter(self.bridge.db["survivors"])),
                                "", "Несуществующий аддон", "",
                                *[x["name"] for x in self.bridge.searchPerks("SURVIVOR", "")[:4]])
        self.assertIsNone(self.bridge.build)

    def test_invalid_custom_build_rejected(self):
        self.bridge.buildCustom("SURVIVOR", "nonexistent", "", "", "", "x", "x", "x", "x")
        self.assertIsNone(self.bridge.build)

    def test_selected_addon_effect_shows_real_summary_and_source(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async") as refresh:
            self.bridge.selectAddonEffect("KILLER", "Охотник", "", "Радужный камень")
            refresh.assert_called_once()
        data = self.bridge.addonEffect
        self.assertEqual(data["name"], "Радужный камень")
        self.assertTrue(data["verified"])
        self.assertIn("30", data["effect"])
        self.assertEqual(data["english"], "Iridescent Stone")
        self.assertTrue(data["source"].startswith("https://deadbydaylight.wiki.gg/"))
        self.bridge._addon_catalog.categories["Iridescent Stone"] = ["EffectDuration"]
        self.assertIn("длительность эффекта", self.bridge.addonEffect["categories"])

    def test_addon_without_checked_description_never_has_invented_claim(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async"):
            self.bridge.selectAddonEffect("KILLER", "Охотник", "", "Несуществующая запись")
        data = self.bridge.addonEffect
        self.assertFalse(data["verified"])
        self.assertFalse(data["effect"])

    def test_addon_notes_cover_other_killers_and_survivors(self):
        examples = [
            ("KILLER", "Свинья", "", "Видеокассета"),
            ("KILLER", "Кошмар", "", "Садовые грабли"),
            ("KILLER", "Хороший парень", "", "Жесткая шляпа"),
            ("SURVIVOR", "", "Фонарики", "Батарейка"),
            ("SURVIVOR", "", "Аптечки", "Медицинские ножницы"),
            ("SURVIVOR", "", "Ящики с инструментами", "Катушка проволоки"),
            ("SURVIVOR", "", "Ключи", "Уникальное обручальное кольцо"),
        ]
        for side, char, category, name in examples:
            with self.subTest(name=name):
                with patch.object(self.bridge._addon_catalog, "refresh_async"):
                    self.bridge.selectAddonEffect(side, char, category, name)
                effect = self.bridge.addonEffect
                self.assertTrue(effect["verified"])
                self.assertTrue(effect["effect"])
                self.assertTrue(effect["english"])
                self.assertIn("wiki.gg", effect["source"])

    def test_wiki_effect_tags_render_as_broad_mechanic_not_false_specific_claim(self):
        with patch.object(self.bridge._addon_catalog, "refresh_async"):
            self.bridge.selectAddonEffect("SURVIVOR", "", "Фонарики", "Сверхмощная батарейка")
        english = self.bridge.addonEffect["english"]
        self.bridge._addon_catalog.categories[english] = ["Charges", "ActionTime"]
        entry = self.bridge.addonEffect
        self.assertIn("заряды", entry["summary"])
        self.assertIn("время действия", entry["summary"])
        self.assertFalse(entry["verified"])
        self.assertEqual(entry["effect"], "")

    def test_all_survivor_addon_groups_have_english_lookup(self):
        from tools.addon_names_ru_en import ITEM_ADDON_RU_EN
        self.assertGreaterEqual(len(ITEM_ADDON_RU_EN), 6)
        for category, names in ITEM_ADDON_RU_EN.items():
            with self.subTest(category=category):
                self.assertTrue(names)
                ru, english = next(iter(names.items()))
                entry = self.bridge._addon_catalog.get("SURVIVOR", "", category, ru)
                self.assertEqual(entry["english"], english)
                self.assertTrue(entry["source"].startswith("https://"))

    def test_custom_build_validation_reports_success_to_ui(self):
        survivor = next(iter(self.bridge.db["survivors"]))
        perks = [row["name"] for row in self.bridge.searchPerks("SURVIVOR", "")[:4]]
        self.assertEqual(len(perks), 4)
        self.assertTrue(self.bridge.buildCustom("SURVIVOR", survivor, "", "", "", *perks))
        self.assertEqual(self.bridge.build["char"], survivor)
        self.assertFalse(self.bridge.buildCustom("SURVIVOR", "invalid survivor", "", "", "", *perks))

    def test_future_updates_use_explicit_semver(self):
        self.assertLess(qt_updater._key("v2.28.0-qt-beta.9"), qt_updater._key("v2.28.0-qt-beta.10"))
        self.assertIsNone(qt_updater._key("v2.28.0"))
        with self.assertRaises(ValueError):
            qt_updater._get("https://attacker.example/test")


if __name__ == "__main__":
    unittest.main()
