"""Verify all game search text without changing saved catalog titles."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dbd_randomizer as core


class ScourgeHookSearchTests(unittest.TestCase):
    def test_every_known_scourge_hook_perk_searches_without_symbols(self):
        perks = list(core.DATA.KILLER_COMMON_PERKS)
        for killer in core.DATA.KILLERS.values():
            perks.extend(killer["perks"])
        scourge = {p for p in perks if p.casefold().startswith("секущий крюк")}
        self.assertGreaterEqual(len(scourge), 5)
        for name in scourge:
            with self.subTest(name=name):
                query = core.game_search_query(name)
                self.assertTrue(query.startswith("секущий крюк "))
                self.assertEqual(query, query.lower())
                self.assertTrue(all(ch.isalnum() or ch == " " for ch in query))
                self.assertNotIn(":", query)
                self.assertEqual(query, " ".join(query.split()))

    def test_requested_exact_search_phrase(self):
        self.assertEqual(
            core.game_search_query("Секущий крюк: пучина ярости"),
            "секущий крюк пучина ярости"
        )

    def test_any_symbols_and_whitespace_are_removed_for_all_names(self):
        for name in (
            "Секущий крюк: пучина ярости",
            "СЕКУЩИЙ КРЮК — ПУЧИНА ЯРОСТИ!!!",
            'Секущий крюк «пучина ярости»',
            "  Секущий   крюк:: (пучина-ярости)  ",
        ):
            self.assertEqual(core.game_search_query(name),
                             "секущий крюк пучина ярости")
        for original, expected in (
            ("Порча: никому не скрыться от смерти", "порча никому не скрыться от смерти"),
            ('"Дисциплина" - заметки Картера', "дисциплина заметки картера"),
            ("Раз, два, три, четыре!", "раз два три четыре"),
            ("крюк: Пучина ярости", "крюк пучина ярости"),
            ("  А+Б/В_Г №5… ", "а б в г 5"),
            ("Радужный король", "Радужный король"),
            ("Барбекю и чили", "Барбекю и чили"),
        ):
            self.assertEqual(core.game_search_query(original), expected)

    def test_every_catalog_perk_and_addon_is_punctuation_free(self):
        db = core.db_defaults()
        names = set(db["killer_common_perks"]) | set(db["surv_common_perks"])
        for profile in db["killers"].values():
            names.update(profile["perks"])
            names.update(profile["addons"])
        for perks in db["survivors"].values():
            names.update(perks)
        for entry in db["survivor_items"].values():
            names.update(entry["addons"])
        self.assertGreater(len(names), 1000)
        for name in names:
            with self.subTest(name=name):
                query = core.game_search_query(name)
                self.assertTrue(query)
                self.assertTrue(all(ch.isalnum() or ch == " " for ch in query))
                self.assertTrue(core.game_search_result_matches(name, query))
                self.assertTrue(core.game_search_result_matches(name, name))
        self.assertFalse(core.game_search_result_matches("!!!", "anything"))
        self.assertFalse(core.game_search_result_matches("Дар", "Подарок"))

    def test_all_boon_and_invocation_perks(self):
        perks = set(core.DATA.SURV_COMMON_PERKS)
        for names in core.DATA.SURVIVORS.values():
            perks.update(names)
        families = {p for p in perks if p.casefold().startswith(("дар:", "чары:"))}
        self.assertGreaterEqual(len(families), 7)
        for name in families:
            with self.subTest(name=name):
                query = core.game_search_query(name)
                self.assertNotEqual(query, name)
                self.assertTrue(all(ch.isalnum() or ch == " " for ch in query))
                self.assertTrue(core.game_search_result_matches(name, query))
                self.assertTrue(core.game_search_result_matches(name, name))

    def test_boon_and_invocation_variants(self):
        for name in ("Дар: круг исцеления", "ДАР — КРУГ ИСЦЕЛЕНИЯ!!!",
                     'Дар «круг исцеления»', "  дар:: круг   исцеления "):
            self.assertEqual(core.game_search_query(name), "дар круг исцеления")
        self.assertEqual(core.game_search_query("Чары: пауки-прядильщики"),
                         "чары пауки прядильщики")
        self.assertFalse(core.game_search_result_matches(
            "Дар: круг исцеления", "Дар: уход в тень"))
        self.assertEqual(core.game_search_query("Подарок"), "Подарок")

    def test_ocr_match_handles_colon_and_plain_search_result(self):
        original = "Секущий крюк: пучина ярости"
        for result in (
            original,
            "Секущий крюк пучина ярости",
            "СЕКУЩИЙ КРЮК — ПУЧИНА ЯРОСТИ",
            "Поиск: Секущий крюк: пучина ярости",
        ):
            with self.subTest(ocr=result):
                self.assertTrue(core.game_search_result_matches(original, result))
        self.assertFalse(core.game_search_result_matches(
            original, "Секущий крюк: резонанс боли"))
        self.assertTrue(core.game_search_result_matches("Барбекю и чили",
                                                        "Барбекю и чили"))
        self.assertFalse(core.game_search_result_matches("Барбекю и чили",
                                                         "Выбор за тобой"))


if __name__ == "__main__":
    unittest.main()
