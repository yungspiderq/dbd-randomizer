"""Stable Qt appearance settings and palettes, independent of PySide6.

Appearance is stored inside the existing config's options map. Old installs
get the default Crimson theme at 100% scale without migration or loss of data.
"""
from __future__ import annotations

import math

SCALES = (0.90, 1.00, 1.10, 1.20)
DEFAULT_THEME = "crimson"
THEMES = {
    "crimson": {
        "title": "CRIMSON", "description": "Классический красно-чёрный",
        "background": "#0c0f14", "sidebar": "#11151c", "surface": "#171d26",
        "panel": "#1b2430", "button": "#242b36", "buttonHover": "#2d3645",
        "stroke": "#2f3947", "muted": "#8995a5", "text": "#f3f5f8",
        "accent": "#ea5753", "accentHover": "#fa6d66", "accentSoft": "#f2b2a7",
        "input": "#1e2631", "inputStroke": "#374251", "inputFocus": "#dd5956",
        "navActive": "#262e3a", "navHover": "#1c222c",
        "chart": "#e56c69", "chartAlt": "#7b9fde",
    },
    "frost": {
        "title": "FROST", "description": "Холодный синий и графит",
        "background": "#0b1018", "sidebar": "#101823", "surface": "#172231",
        "panel": "#1b2939", "button": "#233449", "buttonHover": "#314962",
        "stroke": "#35485c", "muted": "#a1b1c4", "text": "#eef6ff",
        "accent": "#4298e5", "accentHover": "#67b8ff", "accentSoft": "#a8d7ff",
        "input": "#1a2939", "inputStroke": "#40546b", "inputFocus": "#52a4ed",
        "navActive": "#263c55", "navHover": "#1b2c40",
        "chart": "#5ea9ee", "chartAlt": "#79d3e8",
    },
    "violet": {
        "title": "VIOLET", "description": "Глубокий фиолетовый и неон",
        "background": "#100f18", "sidebar": "#181521", "surface": "#221d30",
        "panel": "#28233a", "button": "#302840", "buttonHover": "#473652",
        "stroke": "#483b59", "muted": "#b1a5c0", "text": "#f7f0ff",
        "accent": "#ad73dc", "accentHover": "#ca95f2", "accentSoft": "#dfb9ff",
        "input": "#2c2641", "inputStroke": "#594866", "inputFocus": "#bd83e9",
        "navActive": "#403052", "navHover": "#2c223a",
        "chart": "#ba7fe8", "chartAlt": "#e396ca",
    },
}


def normalize(options=None):
    options = options if isinstance(options, dict) else {}
    theme = options.get("qt_theme", DEFAULT_THEME)
    if theme not in THEMES:
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
