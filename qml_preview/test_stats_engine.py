"""Regression tests for persistent statistics across both randomizer modes."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stats_engine import BuildStatistics


def mock_build(side="KILLER", char="Охотник", perks=None, addons=None, **extra):
    out = {"side": side, "char": char,
           "perks": perks or ["Адреналин", "Переработка"],
           "addons": addons or ["Батарейка", "Лента"],
           "power_or_item": "Аптечка", "category": "Аптечки",
           "forbidden": {}}
    out.update(extra)
    return out


class StatisticsTests(unittest.TestCase):
    def test_empty_has_no_fake_history(self):
        t = BuildStatistics()
        o = t.overview("KILLER", ["Охотник", "Призрак"])
        self.assertEqual(o["generated"], 0)
        self.assertEqual(o["seen"], 0)
        self.assertEqual(t.recent("KILLER"), [])
        self.assertEqual(t.summary("KILLER", "characters", ["Охотник"])[0]["count"], 0)

    def test_classic_and_balanced_are_both_counted(self):
        t = BuildStatistics()
        for i in range(4):
            t.record_build(mock_build(char="Охотник" if i < 3 else "Призрак"),
                           balanced=i % 2 == 0)
        o = t.overview("KILLER", ["Охотник", "Призрак", "Дух"])
        self.assertEqual(o["generated"], 4)
        self.assertEqual(o["classic"], 2)
        self.assertEqual(o["balanced"], 2)
        self.assertEqual(o["seen"], 2)
        self.assertEqual(t.summary("KILLER", "characters", [], order="top")[0]["count"], 3)
        self.assertEqual(t.summary("KILLER", "characters", ["Дух", "Охотник"],
                                   order="least")[0]["name"], "Дух")

    def test_groups_and_survivor_items_are_counted(self):
        t = BuildStatistics()
        t.record_build(mock_build(side="SURVIVOR", char="Мег", perks=["Навык A", "Навык B"],
                                  addons=["Бинты", "Ножницы"]))
        o = t.overview("SURVIVOR", ["Мег"])
        self.assertEqual(o["uniquePerks"], 2)
        self.assertEqual(o["uniqueAddons"], 2)
        self.assertEqual(t.summary("SURVIVOR", "items")[0]["name"], "Аптечка")
        self.assertEqual(t.overview("KILLER")["generated"], 0)

    def test_rerolls_count_as_perk_draw_not_full_generation(self):
        t = BuildStatistics()
        t.record_build(mock_build())
        t.record_perk_reroll("KILLER", "Охотник", "Другой навык", balanced=True)
        o = t.overview("KILLER", ["Охотник"])
        self.assertEqual(o["generated"], 1)
        self.assertEqual(o["rerolls"], 1)
        self.assertEqual(o["balanced"], 0)
        self.assertEqual(t.recent("KILLER")[0]["kind"], "reroll")
        self.assertEqual(t.summary("KILLER", "perks", ["Другой навык"])[0]["count"], 1)

    def test_dropped_equipment_not_counted(self):
        t = BuildStatistics()
        t.record_build(mock_build(side="SURVIVOR",
                                  forbidden={"item": True, "perks": True, "addons": True}))
        self.assertEqual(t.overview("SURVIVOR")["generated"], 1)
        for group in ("perks", "addons", "items"):
            self.assertEqual(t.summary("SURVIVOR", group), [])
        self.assertEqual(t.recent("SURVIVOR")[0]["perks"], [])

    def test_save_reload_recent_and_reset_are_independent(self):
        t = BuildStatistics()
        t.record_build(mock_build())
        t.record_build(mock_build(side="SURVIVOR", char="Мег"))
        saved = t.serialize()
        new = BuildStatistics(saved)
        self.assertEqual(new.overview("KILLER")["generated"], 1)
        self.assertEqual(new.overview("SURVIVOR")["generated"], 1)
        new.reset("KILLER")
        self.assertEqual(new.overview("KILLER")["generated"], 0)
        self.assertEqual(new.overview("SURVIVOR")["generated"], 1)
        self.assertEqual(t.overview("KILLER")["generated"], 1)

    def test_freshness_tracks_last_seen_order(self):
        t = BuildStatistics()
        for char in ["A", "B", "C", "A"]:
            t.record_build(mock_build(char=char))
        stale = t.summary("KILLER", "characters", ["A", "B", "C", "D"], order="stale")
        self.assertEqual([row["name"] for row in stale], ["B", "C", "A"])
        self.assertTrue(stale[0]["since"] > stale[1]["since"])
        self.assertFalse(any(row["name"] == "D" for row in stale))

    def test_recent_history_capped_and_untrusted_save_filtered(self):
        t = BuildStatistics()
        for _ in range(115):
            t.record_build(mock_build())
        self.assertEqual(len(t.recent("KILLER", 200)), 100)
        t2 = BuildStatistics({"KILLER":{"generated":-2, "groups":{"characters":
                             {"Valid": 5, "Invalid": -10, "Bogus": "bad"}},
                             "recent":[{"character":"A", "perks":["B",42], "kind":"build"}]}})
        self.assertEqual(t2.overview("KILLER")["generated"], 0)
        self.assertEqual(t2.summary("KILLER","characters")[0]["name"], "Valid")
        self.assertEqual(t2.recent("KILLER")[0]["perks"], ["B"])


if __name__ == "__main__":
    unittest.main()
