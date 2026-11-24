import sys
import json
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dbd_randomizer as core
from companion import analyze, catalog


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.db = core.db_defaults()

    def test_survivor_synergy_and_exhaustion(self):
        b = {"side": "SURVIVOR", "char": "Мэг Томас", "perks": [
            "Спринтер", "Гибкость", "Сам себе доктор", "Познания в ботанике"]}
        result = analyze(self.db, b)
        self.assertEqual(result["filled"], 4)
        self.assertTrue(result["synergies"])
        self.assertTrue(any("истощения" in w for w in result["warnings"]))

    def test_empty_and_wrong_side(self):
        self.assertFalse(analyze(self.db, None)["hasBuild"])
        result = analyze(self.db, {"side":"KILLER", "perks":["Спринтер"]})
        self.assertTrue(any("отсутствует" in w for w in result["warnings"]))

    def test_catalog_complete_and_paginated(self):
        rows = catalog(self.db, "KILLER", "characters", size=10)
        self.assertEqual(rows["total"], len(self.db["killers"]))
        last = catalog(self.db, "KILLER", "characters", page=999, size=10)
        self.assertEqual(last["page"], last["pages"] - 1)
        self.assertTrue(last["rows"])
        found = catalog(self.db, "SURVIVOR", "perks", "дар круг исцеления")
        self.assertEqual([x["name"] for x in found["rows"]], ["Дар: круг исцеления"])
        self.assertTrue(found["rows"][0]["detail"])

    def test_terrifier_catalog_and_randomization(self):
        art = self.db["killers"]["Ужасающий"]
        self.assertEqual(len(set(art["addons"])), 20)
        self.assertEqual(len(art["perks"]), 3)
        self.assertEqual(len(self.db["survivors"]["Сиенна Шоу"]), 3)
        for name in art["addons"]:
            self.assertIn(name, core.ICONS.ADDON_ICONS)
        b = core.make_killer_build(self.db, ["Ужасающий"], skin_enabled=False)
        self.assertEqual(b["char"], "Ужасающий")
        self.assertEqual(len(set(b["addons"])), 2)
        self.assertTrue(set(b["addons"]) <= set(art["addons"]))
        result = catalog(self.db, "KILLER", "addons", "Ужасающий")
        self.assertEqual(result["total"], 20)
        for side, names in (("KILLER", art["perks"]), ("SURVIVOR", self.db["survivors"]["Сиенна Шоу"])):
            for name in names:
                row = catalog(self.db, side, "perks", name)["rows"][0]
                self.assertTrue(row["detail"])
                self.assertIn(name, core.ICONS.PERK_ICONS)

    def test_terrifier_exact_russian_names_and_migration(self):
        from tools.addon_names_ru_en import ADDON_RU_EN
        expected = [
            "Девятый круг", "Клейкая лента", "Взрывоопасный подарок",
            "Дурик Джекс", "Хрустяшки Арта", "Череп Джонатана",
            "Глаз Виктории", "Голова с конфетами", "Дохлый опоссум",
            "Торнтонская соль", "Эмили", "Волдырь Брук",
            "Новенький трехколесник", "Окровавленная пуля", "Опаленные крылья",
            "Плоть Сиенны", "Отбеливатель", "Почерневшее сердце",
            "Скальп Элли", "Телефон Майка",
        ]
        self.assertEqual(self.db["killers"]["Ужасающий"]["addons"], expected)
        mapping = ADDON_RU_EN["Ужасающий"]
        self.assertEqual(set(mapping), set(expected))
        for name in expected:
            self.assertEqual(core.DATA.ADDON_RENAMES[mapping[name]], name)
            self.assertEqual(core.game_search_query(name), name)
            self.assertIn(name, core.ICONS.ADDON_ICONS)
        self.db["killers"]["Ужасающий"]["addons"] = [mapping[name] for name in expected]
        self.db["owned"]["killer_addons"] = [mapping[expected[0]]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dbd_database.json"
            path.write_text(json.dumps(self.db, ensure_ascii=False), encoding="utf-8")
            with patch.object(core, "DB_FILE", str(path)):
                restored = core.load_db()
        self.assertEqual(restored["killers"]["Ужасающий"]["addons"], expected)
        self.assertEqual(restored["owned"]["killer_addons"], [expected[0]])

    def test_addons_respect_real_pool(self):
        result = catalog(self.db, "KILLER", "addons", "Доктор", playable=core._playable_addons)
        self.assertEqual(result["total"], len(set(core._playable_addons(self.db["killers"]["Доктор"]["addons"]))))
        self.assertEqual(catalog(self.db, "KILLER", "items")["total"], 0)


if __name__ == "__main__":
    unittest.main()
