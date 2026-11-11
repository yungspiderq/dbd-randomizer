"""Offline unit tests for local DBD favorites collections and safe restoration."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dbd_randomizer as core
from favorites import FavoriteBuilds, MAX_FAVORITES


class FavoriteTests(unittest.TestCase):
    def setUp(self):
        self.db = core.db_defaults()
        self.killers = list(self.db["killers"])
        self.survivors = list(self.db["survivors"])
        self.lib = FavoriteBuilds(empty=core.EMPTY, no_addons=core.NO_ADDONS)

    def killer(self):
        return core.make_killer_build(
            self.db, self.killers, perk_mode="mixed",
            addons_enabled=True, skin_enabled=False)

    def survivor(self):
        return core.make_survivor_build(
            self.db, self.survivors, perk_mode="mixed",
            addons_enabled=True, skin_enabled=False)

    def test_add_save_restore_roundtrip_killer(self):
        build = self.killer()
        ident = self.lib.add(build, "Любимый охотник", "Маньяки", "Сильный билд")
        self.assertEqual(self.lib.count, 1)
        row = self.lib.get(ident)
        self.assertEqual(row["title"], "Любимый охотник")
        self.assertEqual(row["collection"], "Маньяки")
        self.assertEqual(row["note"], "Сильный билд")
        restored = self.lib.restore(ident, self.db, core)
        self.assertEqual(restored["side"], build["side"])
        self.assertEqual(restored["char"], build["char"])
        self.assertEqual(restored["perks"], build["perks"])
        self.assertEqual(restored["addons"], build["addons"])
        self.assertEqual(restored["power_or_item"], build["power_or_item"])
        self.assertFalse(restored["forbidden"])
        self.assertEqual(restored["fx"], {})

    def test_roundtrip_survivor_preserves_item_and_valid_addons(self):
        build = self.survivor()
        ident = self.lib.add(build, "", "", "Хорошо подходит для ремонта")
        result = self.lib.restore(ident, self.db, core)
        self.assertEqual(result["side"], "SURVIVOR")
        self.assertEqual(result["category"], build["category"])
        self.assertEqual(result["power_or_item"], build["power_or_item"])
        self.assertEqual(result["addons"], build["addons"])
        self.assertTrue(result["power_is_item"])

    def test_search_side_filters_and_collections(self):
        killer = self.killer()
        survivor = self.survivor()
        self.lib.add(killer, "Шутка", "Коллекция 1", "На маньяка")
        self.lib.add(survivor, "Помощь", "Коллекция 2", "Для выживания")
        self.assertEqual(len(self.lib.list(side="KILLER")), 1)
        self.assertEqual(len(self.lib.list(side="SURVIVOR")), 1)
        self.assertEqual(self.lib.list(query="ПОМОЩЬ")[0]["title"], "Помощь")
        self.assertEqual(self.lib.list(query="КОЛЛЕКЦИЯ 1")[0]["title"], "Шутка")
        self.assertEqual(self.lib.list(query="ВыжиВанИя")[0]["side"], "SURVIVOR")
        self.assertEqual(self.lib.list(collection="Коллекция 2")[0]["side"], "SURVIVOR")
        self.assertEqual(len(self.lib.collections()), 3)

    def test_update_delete_no_change_to_saved_equipment(self):
        build = self.killer()
        ident = self.lib.add(build, "Старое имя")
        original = self.lib.get(ident)["build"]
        self.assertTrue(self.lib.update(ident, "Новое имя", "2v8", "Заметка"))
        self.assertEqual(self.lib.get(ident)["title"], "Новое имя")
        self.assertEqual(self.lib.get(ident)["build"], original)
        self.assertFalse(self.lib.delete("nonexistent"))
        self.assertTrue(self.lib.delete(ident))
        self.assertEqual(self.lib.count, 0)
        self.assertFalse(self.lib.update(ident, "X"))
        with self.assertRaisesRegex(ValueError, "не найден"):
            self.lib.restore(ident, self.db, core)

    def test_config_is_immutable_from_outside_and_survives_restart(self):
        build = self.killer()
        original_build = copy.deepcopy(build)
        ident = self.lib.add(build, "Тест")
        build["perks"][0] = "Чужое значение"
        self.assertEqual(self.lib.get(ident)["build"]["perks"], original_build["perks"])
        saved = self.lib.serialize()
        saved[0]["title"] = "Изменено извне"
        self.assertEqual(self.lib.get(ident)["title"], "Тест")
        restarted = FavoriteBuilds(self.lib.serialize(), empty=core.EMPTY,
                                   no_addons=core.NO_ADDONS)
        self.assertEqual(restarted.restore(ident, self.db, core)["perks"], original_build["perks"])

    def test_deleted_game_perk_or_character_is_rejected_without_crash(self):
        ident = self.lib.add(self.killer(), "Проверка обновления")
        corrupt_db = copy.deepcopy(self.db)
        char = self.lib.get(ident)["build"]["char"]
        del corrupt_db["killers"][char]
        with self.assertRaisesRegex(ValueError, "Персонаж"):
            self.lib.restore(ident, corrupt_db, core)
        corrupt_db = copy.deepcopy(self.db)
        value = self.lib.get(ident)["build"]["perks"][0]
        for info in corrupt_db["killers"].values():
            info["perks"] = [name for name in info["perks"] if name != value]
        corrupt_db["killer_common_perks"] = [name for name in corrupt_db["killer_common_perks"] if name != value]
        with self.assertRaisesRegex(ValueError, "устаревший навык"):
            self.lib.restore(ident, corrupt_db, core)

    def test_corrupted_entries_are_ignored_and_input_is_bounded(self):
        b = self.killer()
        ident = self.lib.add(b, "Длинный заголовок" * 15, "Коллекция" * 20, "Заметка" * 200)
        e = self.lib.get(ident)
        self.assertLessEqual(len(e["title"]), 72)
        self.assertLessEqual(len(e["collection"]), 48)
        self.assertLessEqual(len(e["note"]), 240)
        forged = self.lib.serialize()
        forged += [
            {"id": "broken", "build": b},
            {"id": ident, "build": b},
            {"id": "1234567890abcdef", "build": {"side": "X", "char": "Unknown"}},
        ]
        loaded = FavoriteBuilds(forged, empty=core.EMPTY, no_addons=core.NO_ADDONS)
        self.assertEqual(loaded.count, 1)
        self.assertEqual(loaded.get(ident)["title"], e["title"])

    def test_capacity_limit(self):
        build = self.killer()
        for i in range(MAX_FAVORITES):
            self.lib.add(build, "Saved " + str(i))
        with self.assertRaisesRegex(ValueError, "лимит"):
            self.lib.add(build, "one more")

    def test_missing_slots_or_duplicate_real_perks_are_refused(self):
        build = self.killer()
        build["perks"] = build["perks"][:3]
        with self.assertRaisesRegex(ValueError, "слотов"):
            self.lib.add(build)
        build = self.killer()
        build["perks"][1] = build["perks"][0]
        with self.assertRaisesRegex(ValueError, "повторяющиеся"):
            self.lib.add(build)


if __name__ == "__main__":
    unittest.main()
