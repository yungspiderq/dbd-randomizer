"""Layout guards for wrapped DBD class descriptions and variable-length labels."""
import re
import unittest
from pathlib import Path

QML = Path(__file__).with_name("Main.qml").read_text(encoding="utf-8")


class ResponsiveLayoutTests(unittest.TestCase):
    def test_2v8_cards_use_implicit_content_height(self):
        self.assertIn('id: classCardsRepeater', QML)
        self.assertIn('height: Math.max(126, requiredHeight)', QML)
        self.assertIn('property real requiredHeight: classBody.implicitHeight + 28', QML)
        self.assertIn('id: classesCopyButton', QML)
        self.assertIn('function verifyClassLayout()', QML)
        self.assertNotRegex(
            QML,
            r'Text\s*\{\s*text:\s*modelData\.skills;[^\}]*height:\s*57'
        )
        self.assertIn('textFormat: Text.PlainText', QML)

    def test_other_long_text_sections_reflow_or_reveal_full_text(self):
        for text in (
            'height: Math.max(144, addonsBody.implicitHeight + 26)',
            'height: Math.max(91, addonTextColumn.implicitHeight + 18)',
            'height: Math.max(168, rotationBody.implicitHeight + 24)',
            'height: Math.max(83, settingsWarningText.implicitHeight + 26)',
            'height: Math.max(172, favoriteActions.y + favoriteActions.height + 14)',
            'height: Math.max(576, rankingBody.implicitHeight + 22)',
            'y: Math.max(100, favoriteTextBlock.y + favoriteTextBlock.implicitHeight + 7)',
            'ToolTip.text: catalogRow.title',
            'ToolTip.text: button.label',
            'clip: true',
        ):
            with self.subTest(text=text):
                self.assertIn(text, QML)

    def test_buttons_do_not_overlay_neighboring_controls(self):
        self.assertIn('width: Math.max(0, button.width - 16)', QML)
        self.assertIn('width: Math.max(0, parent.width - (button.iconName ? 21 : 0))',
                      QML)
        self.assertIn('id: buttonText', QML)
        self.assertIn('elide: Text.ElideRight', QML)
        self.assertIn('buttonText.truncated', QML)
        self.assertIn('QT QUICK • STABLE 3.0.4', QML)


if __name__ == "__main__":
    unittest.main()
