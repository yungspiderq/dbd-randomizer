"""v3.1.0 design regressions: restrained chrome, accessible type, real product hero."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import appearance

QML = Path(__file__).with_name("Main.qml").read_text(encoding="utf-8")


def luminance(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
              for v in rgb]
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(left, right):
    hi, lo = sorted((luminance(left), luminance(right)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class UnslopDesignTests(unittest.TestCase):
    def test_all_old_theme_keys_remain_and_ink_is_readable(self):
        for theme in ("crimson", "frost", "violet"):
            with self.subTest(theme=theme):
                palette = appearance.palette(theme)
                self.assertGreaterEqual(contrast(palette["text"], palette["background"]), 7.0)
                self.assertGreaterEqual(contrast(palette["muted"], palette["background"]), 4.5)
                self.assertGreaterEqual(contrast(palette["text"], palette["panel"]), 7.0)
                self.assertNotEqual(palette["accent"], palette["panel"])
                self.assertNotEqual(palette["button"], palette["background"])

    def test_artwork_is_the_visual_focal_point(self):
        for marker in (
            'id: generatedHero',
            'objectName: "generatedHero"',
            'id: heroBody',
            'height: Math.max(170, heroBody.implicitHeight + 36)',
            'iconKey: backend.detail.char',
            'text: backend.detail.power || "Не выбрано"',
            'text: "Результат генерации"',
            'function verifyDesignLayout()',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, QML)
        self.assertIn('text: "Выбранная внешность"', QML)
        self.assertIn('text: "Испытание матча"', QML)

    def test_quiet_chrome_and_single_prominent_generator_action(self):
        for marker in (
            "property bool prominent: false",
            'color: prominent ? (over.containsMouse ? "#ffffff" : "#e8eef2")',
            'border.color: primary ? win.colors.accent : win.colors.stroke',
            'prominent: true',
            'text: "Генератор билдов"',
            'QT QUICK • STABLE 3.1.1',
        ):
            with self.subTest(marker=marker):
                # Main title uses an expression, so check that on its own.
                if marker == 'text: "Генератор билдов"':
                    self.assertIn('? "Генератор билдов" : win.page', QML)
                else:
                    self.assertIn(marker, QML)
        self.assertEqual(QML.count("prominent: true"), 1)
        self.assertNotIn("QT ИНТЕРФЕЙС", QML)
        self.assertNotIn('text: "ВАШ БИЛД"', QML)
        self.assertEqual(len(re.findall(r'NavItem \{ ordinal: \d+;', QML)), 10)


if __name__ == "__main__":
    unittest.main()
