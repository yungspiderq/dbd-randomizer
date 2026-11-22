"""Verify Scourge Hook search text without changing saved perk titles."""
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

    def test_any_symbols_and_whitespace_are_removed_only_for_scourge_hooks(self):
        for name in (
            "Секущий крюк: пучина ярости",
            "СЕКУЩИЙ КРЮК — ПУЧИНА ЯРОСТИ!!!",
            'Секущий крюк «пучина ярости»',
            "  Секущий   крюк:: (пучина-ярости)  ",
        ):
            self.assertEqual(core.game_search_query(name),
                             "секущий крюк пучина ярости")
        for name in ("Порча: никому не скрыться от смерти", "Барбекю и чили",
                     "Радужный король", "Ключ от судна", "крюк: Пучина ярости"):
            self.assertEqual(core.game_search_query(name), name)

    def test_every_known_invocation_perk_searches_without_symbols(self):
        perks = list(core.DATA.SURV_COMMON_PERKS)
        for survivor in core.DATA.SURVIVORS.values():
            perks.extend(survivor if isinstance(survivor, list) else survivor["perks"])
        invocations = {p for p in perks if p.casefold().startswith("чары")}
        self.assertGreaterEqual(len(invocations), 2)
        for name in invocations:
            with self.subTest(name=name):
                query = core.game_search_query(name)
                self.assertTrue(query.startswith("чары "))
                self.assertEqual(query, query.lower())
                self.assertTrue(all(ch.isalnum() or ch == " " for ch in query))
                self.assertEqual(query, " ".join(query.split()))

    def test_invocation_search_strips_colon_dash_quotes_and_whitespace(self):
        for name in (
            "Чары: пауки-прядильщики",
            "ЧАРЫ — ПАУКИ-ПРЯДИЛЬЩИКИ!!!",
            'Чары «пауки-прядильщики»',
            "  Чары:: (пауки-прядильщики)  ",
        ):
            self.assertEqual(core.game_search_query(name),
                             "чары пауки прядильщики")
        self.assertEqual(core.game_search_query("Чары: предательские вороны"),
                         "чары предательские вороны")
        self.assertEqual(core.game_search_query("Порча: погибель"),
                         "Порча: погибель")

    def test_invocation_ocr_match_handles_game_punctuation(self):
        original = "Чары: пауки-прядильщики"
        for result in (original, "Чары пауки прядильщики",
                       "ЧАРЫ — ПАУКИ-ПРЯДИЛЬЩИКИ",
                       "Поиск: Чары: пауки-прядильщики"):
            with self.subTest(result=result):
                self.assertTrue(core.game_search_result_matches(original, result))
        self.assertFalse(core.game_search_result_matches(
            original, "Чары: предательские вороны"))

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
