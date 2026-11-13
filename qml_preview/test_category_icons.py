"""Qt category icon regression tests. Icons are vector-drawn, not emoji files."""
import re
import unittest
from pathlib import Path

QML = Path(__file__).with_name("Main.qml")


class CategoryIconsTests(unittest.TestCase):
    def test_all_navigation_categories_show_unique_vector_icons(self):
        source = QML.read_text(encoding="utf-8")
        nav = re.findall(
            r'NavItem \{ ordinal: (\d+); label: "([^"]+)"; iconName: "([^"]+)"',
            source,
        )
        self.assertEqual(len(nav), 10)
        self.assertEqual(len({label for _, label, _ in nav}), 10)
        self.assertEqual(len({icon for _, _, icon in nav}), 10)
        self.assertIn("component MiniGlyph: Canvas", source)
        self.assertIn("onKindChanged: requestPaint()", source)
        self.assertIn('property string iconName: ""', source)

    def test_perk_and_challenge_types_have_real_icons(self):
        source = QML.read_text(encoding="utf-8")
        for marker in (
            '{key:"all", label:"ВСЕ", icon:"all"}',
            '{key:"common", label:"ОБЩИЕ", icon:"common"}',
            '{key:"unique", label:"УНИКАЛЬНЫЕ", icon:"unique"}',
            '{key:"character", label:"ПЕРСОНАЖА", icon:"character"}',
            '{ key: "mixed", text: "Смешанные", icon: "mixed" }',
            '{ key: "general", text: "Обычные", icon: "general" }',
            '{ key: "power", text: "Способности", icon: "power" }',
            'iconName: modelData.icon',
            'backend.detail.challengeTheme',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertIn("QT QUICK • STABLE 3.0.3", source)


if __name__ == "__main__":
    unittest.main()
