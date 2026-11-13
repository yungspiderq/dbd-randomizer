"""Stable Qt appearance settings and palettes, independent of PySide6.

Appearance is stored inside the existing config's options map. Old installs
get the default Crimson theme at 100% scale without migration or loss of data.
"""
from __future__ import annotations

import math

SCALES = (0.90, 1.00, 1.10, 1.20)
DEFAULT_THEME = "crimson"
THEMES = {
    # Quiet, accessible neutral ramp: color belongs to selection and DBD artwork.
    "crimson": {
        "title": "CRIMSON", "description": "Графит и приглушённый красный",
        "background": "#0d1116", "sidebar": "#12171d", "surface": "#171d24",
        "panel": "#1b232c", "button": "#242d37", "buttonHover": "#303b47",
        "stroke": "#343e4a", "muted": "#a5b0bc", "text": "#f2f4f5",
        "accent": "#d5726b", "accentHover": "#e18a82", "accentSoft": "#e5ada7",
        "input": "#1b222b", "inputStroke": "#3b4652", "inputFocus": "#d5726b",
        "navActive": "#252d37", "navHover": "#1c242d",
        "chart": "#cc7e75", "chartAlt": "#9bb0c6",
    },
    "frost": {
        "title": "FROST", "description": "Графит и холодная сталь",
        "background": "#0e1217", "sidebar": "#131820", "surface": "#192028",
        "panel": "#1d252e", "button": "#27313b", "buttonHover": "#313d49",
        "stroke": "#394550", "muted": "#aab6c2", "text": "#f1f4f5",
        "accent": "#8fb3cd", "accentHover": "#adcbdd", "accentSoft": "#bbd4e2",
        "input": "#1d2630", "inputStroke": "#41515e", "inputFocus": "#8fb3cd",
        "navActive": "#283440", "navHover": "#1d2933",
        "chart": "#8fb3cd", "chartAlt": "#a3b8b5",
    },
    "violet": {
        "title": "VIOLET", "description": "Графит и дымчатая сирень",
        "background": "#111116", "sidebar": "#17171d", "surface": "#1e1e26",
        "panel": "#23232d", "button": "#2d2d38", "buttonHover": "#383845",
        "stroke": "#45434f", "muted": "#b5b1c1", "text": "#f4f2f5",
        "accent": "#b4a0ca", "accentHover": "#c6b4d8", "accentSoft": "#d1c2df",
        "input": "#23232e", "inputStroke": "#514f60", "inputFocus": "#b4a0ca",
        "navActive": "#35313e", "navHover": "#282630",
        "chart": "#b4a0ca", "chartAlt": "#a7b6be",
    },
}


def normalize(options=None):
    options = options if isinstance(options, dict) else {}
    theme = options.get("qt_theme", DEFAULT_THEME)
    if not isinstance(theme, str) or theme not in THEMES:
        theme = DEFAULT_THEME
    raw_scale = options.get("qt_scale", 1.0)
    if type(raw_scale) not in (float, int) or not math.isfinite(raw_scale):
        scale = 1.0
    else:
        scale = min(SCALES, key=lambda value: abs(raw_scale - value))
    animations = options.get("qt_animations", True)
    if type(animations) is not bool:
        animations = True
    return {"theme": theme, "scale": scale, "animations": animations}


def palette(theme):
    return dict(THEMES.get(theme, THEMES[DEFAULT_THEME]))


def write_to_options(options, state):
    options["qt_theme"] = state["theme"]
    options["qt_scale"] = state["scale"]
    options["qt_animations"] = state["animations"]
