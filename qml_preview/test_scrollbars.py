"""Offline coverage checks for draggable Qt scrollbars.

A real Qt engine smoke test exercises the QML bar objects in Windows CI.
"""
import re
import unittest
from pathlib import Path

QML = Path(__file__).with_name("Main.qml")


class ScrollbarTests(unittest.TestCase):
    def test_every_scrollable_section_has_an_interactive_scrollbar(self):
        source = QML.read_text(encoding="utf-8")
        views = re.findall(r"\b(?:Flickable|ListView)\s*\{", source)
        bars = re.findall(r"ScrollBar\.vertical:\s*QuickScrollBar\s*\{", source)
        self.assertEqual(len(views), 15, "View count changed; audit the scrollbar coverage")
        self.assertEqual(len(bars), len(views),
                         "A Flickable or ListView lacks a scrollbar")
        self.assertIn("component QuickScrollBar: ScrollBar", source)
        self.assertIn("interactive: true", source)
        self.assertIn("active: true", source)
        self.assertIn("policy: ScrollBar.AsNeeded", source)
        self.assertIn("minimumSize: 0.07", source)

    def test_page_builder_outfits_and_favorites_are_covered(self):
        source = QML.read_text(encoding="utf-8")
        for name in ("mainPageScrollBar", "builderPerkScrollBar",
                     "outfitScrollBar", "workScroll", "outfitsCatalog",
                     "favoritesCatalog", "charactersCatalog"):
            with self.subTest(control=name):
                self.assertIn(name, source)
        self.assertIn("function verifyFastScroll()", source)
        self.assertIn("QT QUICK • STABLE 3.1.0", source)


if __name__ == "__main__":
    unittest.main()
