"""Offline regression tests for catalog localization and wiki-cache refresh."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import catalog_audit
from tools import fetch_ru_skins


class CatalogAuditTests(unittest.TestCase):
    def test_all_catalogs_are_counted_without_guessing_unverified_translations(self):
        report = catalog_audit.audit()
        self.assertGreater(report["skins"]["total"], 2000)
        self.assertGreater(report["skins"]["with_russian"], 1000)
        self.assertEqual(
            report["skins"]["total"],
            report["skins"]["with_russian"] + report["skins"]["without_russian"],
        )
        self.assertGreater(report["perks"]["distinct_by_side"]["KILLER"], 70)
        self.assertGreater(report["perks"]["distinct_by_side"]["SURVIVOR"], 70)
        self.assertIn("reference_note", report["source"])
        self.assertIn("does not prove", report["perks"]["reference_note"])
        self.assertIn("## Аддоны", catalog_audit.markdown(report))

    def test_baseline_detects_removed_russian_name_without_replacing_it(self):
        baseline = catalog_audit.baseline_snapshot()
        ident = next(key for key, value in baseline["skins"].items()
                     if value["name_ru"])
        fake = dict(catalog_audit.SKINS.SKINS_BY_ID)
        fake[int(ident)] = {**fake[int(ident)]}
        fake[int(ident)].pop("name_ru", None)
        with patch.object(catalog_audit.SKINS, "SKINS_BY_ID", fake):
            report = catalog_audit.audit(baseline)
        self.assertTrue(any("verified RU name lost" in item for item in report["errors"]))

    def test_baseline_detects_same_character_skin_swap(self):
        baseline = catalog_audit.baseline_snapshot()
        ident = next(k for k, row in baseline["skins"].items()
                     if row.get("name") and row.get("file"))
        fake = dict(catalog_audit.SKINS.SKINS_BY_ID)
        fake[int(ident)] = {**fake[int(ident)],
                            "name": "Unrelated cosmetic",
                            "file": "Unrelated_Outfit_999.png"}
        with patch.object(catalog_audit.SKINS, "SKINS_BY_ID", fake):
            report = catalog_audit.audit(baseline)
        self.assertTrue(any("may have changed identity" in error
                            for error in report["errors"]))

    def test_baseline_allows_translation_update_without_identity_change(self):
        baseline = catalog_audit.baseline_snapshot()
        ident = next(k for k, row in baseline["skins"].items()
                     if row.get("name") and row.get("file"))
        fake = dict(catalog_audit.SKINS.SKINS_BY_ID)
        fake[int(ident)] = {**fake[int(ident)]}
        fake[int(ident)]["name_ru"] = "Новое проверенное имя"
        with patch.object(catalog_audit.SKINS, "SKINS_BY_ID", fake):
            report = catalog_audit.audit(baseline)
        self.assertFalse(any(str(ident) in error for error in report["errors"]))

    def test_baseline_detects_character_id_reassignment(self):
        baseline = catalog_audit.baseline_snapshot()
        ident = next(iter(baseline["skins"]))
        bad_baseline = {"skins": {ident: {
            "char": "Вымышленный персонаж", "side": "KILLER",
            "name_ru": "",
        }}}
        report = catalog_audit.audit(bad_baseline)
        self.assertTrue(any("reassigned" in error for error in report["errors"]))


class CacheRefreshTests(unittest.TestCase):
    def test_refresh_fetches_new_text_and_replaces_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_ru_skins, "CACHE", tmp), \
                 patch.object(fetch_ru_skins, "api",
                              return_value={"parse": {"wikitext": "|+ Актуальное название"}}), \
                 patch.object(fetch_ru_skins.time, "sleep", return_value=None):
                path = Path(fetch_ru_skins.cache_path("Персонаж (наборы одежды)"))
                path.write_text("|+ Старое название", encoding="utf-8")
                result = fetch_ru_skins.fetch_wikitext(
                    "Персонаж (наборы одежды)", 42, refresh=True)
                self.assertEqual(result, "|+ Актуальное название")
                self.assertEqual(path.read_text(encoding="utf-8"), result)
                self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

    def test_refresh_preserves_cache_when_wiki_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_ru_skins, "CACHE", tmp), \
                 patch.object(fetch_ru_skins, "api", side_effect=OSError("403")):
                title = "Персонаж (наборы одежды)"
                path = Path(fetch_ru_skins.cache_path(title))
                path.write_text("|+ Подтверждено ранее", encoding="utf-8")
                self.assertEqual(
                    fetch_ru_skins.fetch_wikitext(title, 42, refresh=True),
                    "|+ Подтверждено ранее")
                self.assertEqual(path.read_text(encoding="utf-8"), "|+ Подтверждено ранее")

    def test_unavailable_source_does_not_invent_missing_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_ru_skins, "CACHE", tmp), \
                 patch.object(fetch_ru_skins, "api", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    fetch_ru_skins.fetch_wikitext("Missing article", 123, refresh=True)


    def test_live_catalog_excludes_unknown_ptb_characters(self):
        from tools import resolve_skins
        from tools.char_map_ru import KILLER_EN_RU, SURVIVOR_EN_RU
        from tools import catalog_audit as audit
        known_k = next((en, ru) for en, ru in KILLER_EN_RU.items()
                       if ru in audit.DATA.KILLERS)
        known_s = next((en, ru) for en, ru in SURVIVOR_EN_RU.items()
                       if ru in audit.DATA.SURVIVORS)
        entries = {
            "killers": (
                '{id = 1, name = "' + known_k[0] + '"}, '
                '{id = 45, name = "Unreleased PTB Killer"},'
            ),
            "survivors": (
                '{id = 1, name = "' + known_s[0] + '"}, '
                '{id = 55, name = "Unreleased PTB Survivor"},'
            ),
        }
        with patch.object(resolve_skins, "lua_block",
                          side_effect=lambda _src, table: entries[table]), \
             patch("builtins.print"):
            killer_ids, survivor_ids = resolve_skins.character_names("")
        self.assertEqual(killer_ids, {1: known_k[1]})
        self.assertEqual(survivor_ids, {1: known_s[1]})


    def test_wiki_renumbering_never_reassigns_old_skin_ids(self):
        from tools import resolve_skins
        previous = {
            200: {"kind": "outfit", "side": "KILLER",
                  "char": "A", "file": "a_outfit.png", "name": "A set", "date": "01.01.2025"},
            201: {"kind": "outfit", "side": "SURVIVOR",
                  "char": "B", "file": "b_outfit.png", "name": "B set", "date": "01.01.2025"},
        }
        rows = [
            {"id": 200, "kind": "outfit", "side": "SURVIVOR",
             "char": "B", "file": "b_outfit.png", "name": "B set", "date": "01.01.2025"},
            {"id": 201, "kind": "outfit", "side": "KILLER",
             "char": "A", "file": "a_outfit.png", "name": "A set", "date": "01.01.2025"},
            {"id": 201, "kind": "outfit", "side": "KILLER",
             "char": "C", "file": "c_outfit.png", "name": "C set", "date": "01.10.2026"},
        ]
        with patch("builtins.print"):
            resolve_skins.preserve_catalog_ids(rows, previous)
        self.assertEqual([row["id"] for row in rows[:2]], [201, 200])
        self.assertGreater(rows[2]["id"], 201)
        self.assertEqual(len({row["id"] for row in rows}), 3)


if __name__ == "__main__":
    unittest.main()
