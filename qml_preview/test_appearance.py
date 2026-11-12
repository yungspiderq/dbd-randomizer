"""Appearance engine regression tests, no Qt dependencies."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appearance


class AppearanceTests(unittest.TestCase):
    def test_old_config_defaults(self):
        state = appearance.normalize({})
        self.assertEqual(state, {"theme": "crimson", "scale": 1.0, "animations": True})
        self.assertEqual(appearance.normalize(None), state)
        self.assertEqual(appearance.normalize([]), state)

    def test_valid_themes_have_complete_palette(self):
        required = {
            "title", "description", "background", "sidebar", "surface",
            "panel", "button", "buttonHover", "stroke", "muted", "text",
            "accent", "accentHover", "accentSoft", "input", "inputStroke",
            "inputFocus", "navActive", "navHover", "chart", "chartAlt",
        }
        self.assertEqual(set(appearance.THEMES), {"crimson", "frost", "violet"})
        for theme in appearance.THEMES:
            with self.subTest(theme=theme):
                p = appearance.palette(theme)
                self.assertEqual(set(p), required)
                for key in required - {"title", "description"}:
                    self.assertRegex(p[key], r"^#[0-9a-fA-F]{6}$")
                self.assertNotEqual(p["background"], p["accent"])
                self.assertNotEqual(p["panel"], p["text"])

    def test_scale_and_animation_values_are_normalized(self):
        for scale in appearance.SCALES:
            with self.subTest(scale=scale):
                result = appearance.normalize({"qt_scale": scale, "qt_animations": False})
                self.assertEqual(result["scale"], scale)
                self.assertFalse(result["animations"])
        self.assertEqual(appearance.normalize({"qt_scale": 100})["scale"], 1.20)
        self.assertEqual(appearance.normalize({"qt_scale": -2})["scale"], 0.90)
        self.assertEqual(appearance.normalize({"qt_scale": True})["scale"], 1.00)
        self.assertEqual(appearance.normalize({"qt_scale": math.nan})["scale"], 1.00)
        self.assertEqual(appearance.normalize({"qt_scale": math.inf})["scale"], 1.00)
        self.assertTrue(appearance.normalize({"qt_animations": "false"})["animations"])
        self.assertEqual(appearance.normalize({"qt_theme": "not-a-theme"})["theme"], "crimson")

    def test_saving_does_not_override_other_config_entries(self):
        original = {"rotation_enabled": True, "qt_scale": 1.0, "favorite_builds_v1": [{"id":"test"}]}
        state = {"theme": "violet", "scale": 1.1, "animations": False}
        appearance.write_to_options(original, state)
        self.assertEqual(appearance.normalize(original), state)
        self.assertTrue(original["rotation_enabled"])
        self.assertEqual(original["favorite_builds_v1"], [{"id":"test"}])

    def test_palettes_are_copies(self):
        p = appearance.palette("crimson")
        p["accent"] = "#000000"
        self.assertNotEqual(p["accent"], appearance.palette("crimson")["accent"])
        self.assertEqual(appearance.palette("bogus"), appearance.palette("crimson"))


if __name__ == "__main__":
    unittest.main()
