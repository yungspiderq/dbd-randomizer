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


if __name__ == "__main__":
    unittest.main()
