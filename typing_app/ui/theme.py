"""Theme system: colour palettes, fonts and a generated Qt stylesheet.

Two themes ship with the app ("dark" default and "light").  Colours are kept in
one dictionary per theme so every widget can pick exact colours when it needs
to paint something custom (charts, keyboard, level tiles).
"""
from __future__ import annotations

from string import Template

from PyQt6.QtGui import QFont

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
DARK = {
    "bg": "#0e1014",
    "surface": "#151922",
    "surface_alt": "#1b202b",
    "surface_hover": "#222836",
    "border": "#272e3d",
    "text": "#e8ecf3",
    "text_dim": "#98a2b3",
    "accent": "#5b8cff",
    "accent_hover": "#7ba3ff",
    "accent_text": "#0b1020",
    "on_accent": "#ffffff",
    "green": "#34d399",
    "green_soft": "#123324",
    "red": "#f87171",
    "red_soft": "#3a1d22",
    "gold": "#fbbf24",
    "silver": "#cbd5e1",
    "bronze": "#e08a4a",
    "chart_grid": "#242b39",
    "chart_line": "#5b8cff",
    "chart_line2": "#34d399",
    "shadow": "#000000",
}

LIGHT = {
    "bg": "#eef1f6",
    "surface": "#ffffff",
    "surface_alt": "#f5f7fb",
    "surface_hover": "#e9eef7",
    "border": "#d7dde8",
    "text": "#161b26",
    "text_dim": "#5a6577",
    "accent": "#2f6bed",
    "accent_hover": "#1f5bd6",
    "accent_text": "#ffffff",
    "on_accent": "#ffffff",
    "green": "#0e9f6e",
    "green_soft": "#d9f5ea",
    "red": "#dc2626",
    "red_soft": "#fde3e3",
    "gold": "#d97706",
    "silver": "#64748b",
    "bronze": "#b45309",
    "chart_grid": "#dde3ec",
    "chart_line": "#2f6bed",
    "chart_line2": "#0e9f6e",
    "shadow": "#9aa5b5",
}

PALETTES = {"dark": DARK, "light": LIGHT}
THEME_NAMES = {"dark": "Dark", "light": "Light"}

# Finger colours for the on-screen keyboard (identical in both themes).
FINGER_COLORS = {
    "left-pinky": "#f2789f",
    "left-ring": "#f2a05c",
    "left-middle": "#e8d15c",
    "left-index": "#5cd1a4",
    "thumb": "#8f9bb0",
    "right-index": "#5cd1a4",
    "right-middle": "#e8d15c",
    "right-ring": "#f2a05c",
    "right-pinky": "#f2789f",
}
FINGER_NAMES = {
    "left-pinky": "Left pinky",
    "left-ring": "Left ring",
    "left-middle": "Left middle",
    "left-index": "Left index",
    "thumb": "Thumb",
    "right-index": "Right index",
    "right-middle": "Right middle",
    "right-ring": "Right ring",
    "right-pinky": "Right pinky",
}

FONT_STACK = ["Segoe UI", "Inter", "Roboto", "Noto Sans", "Ubuntu", "DejaVu Sans"]
MONO_STACK = ["Cascadia Mono", "Consolas", "SF Mono", "DejaVu Sans Mono", "Monospace"]


def palette(name: str) -> dict:
    return PALETTES.get(name, DARK)


def app_font(size: int = 10) -> QFont:
    font = QFont()
    font.setFamilies(FONT_STACK)
    font.setPointSize(size)
    return font


def mono_font(size: int = 16) -> QFont:
    font = QFont()
    font.setFamilies(MONO_STACK)
    font.setPointSize(size)
    return font


# ---------------------------------------------------------------------------
# Stylesheet (built with string.Template so QSS braces need no escaping)
# ---------------------------------------------------------------------------
QSS_TEMPLATE = Template("""
* { font-family: "$font_stack"; }

QWidget { color: $text; background: $bg; font-size: $base_font; }
QToolTip { color: $text; background: $surface; border: 1px solid $border; padding: 5px; border-radius: 6px; }

QLabel { background: transparent; }
QLabel#h1 { font-size: 22pt; font-weight: bold; color: $text; }
QLabel#h2 { font-size: 14pt; font-weight: bold; color: $text; }
QLabel#h3 { font-size: 11pt; font-weight: bold; color: $text; }
QLabel#dim { color: $text_dim; }
QLabel#accent { color: $accent; font-weight: bold; }

QFrame#card { background: $surface; border: 1px solid $border; border-radius: 14px; }
QFrame#cardAlt { background: $surface_alt; border: 1px solid $border; border-radius: 14px; }
QFrame#separator { background: $border; max-height: 1px; border: none; }

QPushButton {
    background: $surface_alt; color: $text; border: 1px solid $border;
    border-radius: 10px; padding: 8px 16px; font-weight: bold;
}
QPushButton:hover { background: $surface_hover; border-color: $accent; }
QPushButton:pressed { background: $surface; }
QPushButton:disabled { color: $text_dim; background: $surface_alt; border-color: $border; }

QPushButton#primary {
    background: $accent; color: $on_accent; border: none; padding: 10px 22px;
}
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#primary:disabled { background: $surface_alt; color: $text_dim; border: 1px solid $border; }

QPushButton#danger { background: transparent; color: $red; border: 1px solid $red; }
QPushButton#danger:hover { background: $red_soft; }

QPushButton#nav {
    text-align: left; padding: 11px 14px; border: none; border-radius: 10px;
    background: transparent; color: $text_dim; font-weight: bold; font-size: $nav_font;
}
QPushButton#nav:hover { background: $surface_alt; color: $text; }
QPushButton#nav:checked { background: $accent; color: $on_accent; }

QPushButton#tileLocked { background: $surface_alt; color: $text_dim; border: 1px solid $border; border-radius: 12px; }

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: $surface_alt; color: $text; border: 1px solid $border;
    border-radius: 9px; padding: 7px 10px; selection-background-color: $accent;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $accent; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $surface; color: $text; border: 1px solid $border;
    selection-background-color: $accent; selection-color: $on_accent;
}

QCheckBox { background: transparent; spacing: 9px; }
QCheckBox::indicator {
    width: 19px; height: 19px; border-radius: 5px; border: 1px solid $border; background: $surface_alt;
}
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
QRadioButton { background: transparent; spacing: 8px; }

QSlider::groove:horizontal { height: 5px; background: $border; border-radius: 3px; }
QSlider::handle:horizontal {
    background: $accent; width: 17px; height: 17px; margin: -7px 0; border-radius: 9px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }

QTabWidget::pane { border: 1px solid $border; border-radius: 12px; background: $surface; top: -1px; }
QTabBar::tab {
    background: transparent; color: $text_dim; padding: 9px 18px; margin-right: 4px;
    border-top-left-radius: 9px; border-top-right-radius: 9px; font-weight: bold;
}
QTabBar::tab:selected { background: $surface; color: $accent; border: 1px solid $border; border-bottom: none; }
QTabBar::tab:hover:!selected { color: $text; }

QTableWidget, QListView {
    background: $surface; border: 1px solid $border; border-radius: 12px;
    gridline-color: $border; selection-background-color: $surface_hover;
}
QHeaderView::section {
    background: $surface_alt; color: $text_dim; padding: 8px; border: none;
    border-bottom: 1px solid $border; font-weight: bold;
}
QTableWidget::item { padding: 6px; border: none; }

QScrollBar:vertical { background: transparent; width: 11px; margin: 4px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 34px; }
QScrollBar::handle:vertical:hover { background: $text_dim; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 4px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 34px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QScrollArea { border: none; background: transparent; }
QProgressBar {
    background: $surface_alt; border: 1px solid $border; border-radius: 7px;
    text-align: center; color: $text_dim; max-height: 12px;
}
QProgressBar::chunk { background: $accent; border-radius: 6px; }
QMessageBox { background: $bg; }
""")


def build_stylesheet(theme: str, base_font_size: int = 10) -> str:
    colors = palette(theme)
    values = dict(colors)
    values.update({
        "font_stack": ", ".join(f'"{name}"' for name in FONT_STACK),
        "base_font": f"{base_font_size}pt",
        "nav_font": f"{base_font_size + 1}pt",
    })
    return QSS_TEMPLATE.substitute(values)


def apply_theme(app, theme: str, base_font_size: int = 10) -> None:
    """Apply palette + stylesheet + default fonts to the whole application."""
    app.setStyleSheet(build_stylesheet(theme, base_font_size))
    app.setFont(app_font(base_font_size))
