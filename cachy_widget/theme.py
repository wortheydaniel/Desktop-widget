"""Palette. Dark navy base from the CachyOS Plasma colour scheme, teal-green brand accent."""

from PyQt6.QtGui import QColor


def rgba(hex_: str, a: float = 1.0) -> QColor:
    c = QColor(hex_)
    c.setAlphaF(a)
    return c


BG_TOP = "#1d2133"       # window bg (#181B28) lifted slightly for the gradient
BG_BOTTOM = "#10131d"
PANEL = "#ffffff"        # used at ~5% alpha for inner cards
ACCENT = "#08c9a0"       # CachyOS green-teal
ACCENT_2 = "#66c2f2"     # Plasma-scheme cyan, for cool data (rain, tomorrow)
TEXT = "#eef2f7"
TEXT_MUTED = "#9aa3b8"
TEXT_FAINT = "#5f6882"
WARM = "#ffc857"

# Soft glow colour behind the hero icon, by condition kind
GLOW = {
    "clear": "#ffb347",
    "partly": "#ffd27a",
    "cloudy": "#8aa4c8",
    "fog": "#9fb0c4",
    "drizzle": "#5aa9e6",
    "rain": "#4a90e2",
    "snow": "#bfe3ff",
    "storm": "#9b7bff",
    "night": "#6c7bff",
}
