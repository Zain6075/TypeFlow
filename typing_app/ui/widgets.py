"""Reusable UI building blocks: cards, stat tiles, buttons, the level map and
small confirmation dialogs.  Everything here is theme-aware through
``theme.palette()``.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from . import theme

# ---------------------------------------------------------------------------
# Cards & text
# ---------------------------------------------------------------------------
class Card(QFrame):
    """Rounded surface container with an optional title row."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("h3")
            self._layout.addWidget(label)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class StatCard(QFrame):
    """A single quick-stat: big value, caption and optional sub-line."""

    def __init__(self, caption: str, value: str = "-", sub: str = "", accent: str | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)

        self.caption = QLabel(caption.upper())
        self.caption.setObjectName("dim")
        self.caption.setWordWrap(True)
        caption_font = QFont(theme.FONT_STACK)
        caption_font.setPointSize(8)
        caption_font.setBold(True)
        self.caption.setFont(caption_font)

        self.value = QLabel(value)
        value_font = QFont(theme.FONT_STACK)
        value_font.setPointSize(19)
        value_font.setBold(True)
        self.value.setFont(value_font)
        if accent:
            self.value.setStyleSheet(f"color: {accent};")

        self.sub = QLabel(sub)
        self.sub.setObjectName("dim")

        layout.addWidget(self.caption)
        layout.addWidget(self.value)
        layout.addWidget(self.sub)

    def set_value(self, value: str, sub: str | None = None, accent: str | None = None) -> None:
        self.value.setText(value)
        if sub is not None:
            self.sub.setText(sub)
        if accent:
            self.value.setStyleSheet(f"color: {accent};")
        elif self.value.styleSheet():
            self.value.setStyleSheet("")


class Badge(QLabel):
    """Small coloured pill used for level states and requirements."""

    def __init__(self, text: str, color: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 9px;"
            " padding: 2px 9px; font-weight: bold;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)


class GhostButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)


class DangerButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("danger")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("h2")


# ---------------------------------------------------------------------------
# Level map
# ---------------------------------------------------------------------------
def _star_polygon(cx: float, cy: float, radius: float) -> QPolygonF:
    import math
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = radius if i % 2 == 0 else radius * 0.45
        points.append(QPointF_(cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return QPolygonF(points)


def QPointF_(x: float, y: float):
    from PyQt6.QtCore import QPointF
    return QPointF(x, y)


class LevelTile(QWidget):
    """One level on the map: number, state and earned stars."""

    clicked = pyqtSignal(int)

    def __init__(self, level: int, status: str, stars: int, is_current: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.level = level
        self.status = status          # "locked" | "unlocked" | "completed"
        self.stars = stars
        self.is_current = is_current
        self.setFixedSize(74, 74)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self._tooltip())

    def _tooltip(self) -> str:
        if self.status == "locked":
            return f"Level {self.level} - locked\nFinish level {self.level - 1} to unlock."
        if self.status == "completed":
            return f"Level {self.level} - completed with {self.stars} star(s).\nClick to retry."
        return f"Level {self.level} - ready to play!"

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.level)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        pal = theme.palette(_current_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        if self.status == "locked":
            fill, border, text_color = QColor(pal["surface_alt"]), QColor(pal["border"]), QColor(pal["text_dim"])
        elif self.status == "unlocked":
            fill, border, text_color = QColor(pal["surface"]), QColor(pal["accent"]), QColor(pal["text"])
        else:  # completed
            fill, border, text_color = QColor(pal["surface"]), QColor(pal["green"]), QColor(pal["text"])

        painter.setPen(QPen(border, 2.0 if self.status != "locked" else 1.2))
        painter.setBrush(fill)
        painter.drawPath(path)

        # "current level" halo
        if self.is_current:
            halo = QColor(pal["accent"])
            halo.setAlpha(70)
            painter.setPen(QPen(halo, 5))
            painter.drawPath(path)

        painter.setPen(text_color)
        number_font = QFont(theme.FONT_STACK)
        number_font.setPointSize(13)
        number_font.setBold(True)
        painter.setFont(number_font)
        painter.drawText(QRectF(0, 8, self.width(), 30), Qt.AlignmentFlag.AlignCenter, str(self.level))

        if self.status == "locked":
            self._draw_lock(painter, pal)
        elif self.status == "completed":
            self._draw_stars(painter, pal)

    def _draw_lock(self, painter: QPainter, pal: dict) -> None:
        color = QColor(pal["text_dim"])
        painter.setPen(QPen(color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2 + 8
        painter.drawRoundedRect(QRectF(cx - 8, cy, 16, 12), 2.5, 2.5)
        shackle = QPainterPath()
        shackle.moveTo(cx - 5, cy)
        shackle.lineTo(cx - 5, cy - 5)
        shackle.arcTo(QRectF(cx - 5, cy - 11, 10, 12), 0, 180)
        shackle.lineTo(cx + 5, cy)
        painter.drawPath(shackle)

    def _draw_stars(self, painter: QPainter, pal: dict) -> None:
        filled = QColor(pal["gold"])
        empty = QColor(pal["border"])
        spacing = 17.0
        start = self.width() / 2 - (spacing * 1.5)
        y = self.height() / 2 + 15
        for index in range(3):
            cx = start + index * spacing
            painter.setBrush(filled if index < self.stars else empty)
            painter.setPen(QPen(empty if index >= self.stars else filled, 1))
            painter.drawPolygon(_star_polygon(cx, y, 6.4))


def _current_theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"


class LevelMapWidget(QWidget):
    """Grid of 100 level tiles; emits the level that was clicked."""

    level_clicked = pyqtSignal(int)

    COLUMNS = 10

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setSpacing(8)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.tiles: dict[int, LevelTile] = {}

    def set_levels(self, levels: list[dict]) -> None:
        """``levels`` is a list of {level, status, stars, current} dicts."""
        # Remove old tiles.
        for tile in self.tiles.values():
            self.grid.removeWidget(tile)
            tile.deleteLater()
        self.tiles.clear()
        for index, info in enumerate(levels):
            tile = LevelTile(info["level"], info["status"], info.get("stars", 0),
                             info.get("current", False))
            tile.clicked.connect(self.level_clicked)
            self.grid.addWidget(tile, index // self.COLUMNS, index % self.COLUMNS)
            self.tiles[info["level"]] = tile


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
def confirm(parent, title: str, text: str, ok_text: str = "OK", cancel_text: str = "Cancel",
            danger: bool = False) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(text)
    box.setIcon(QMessageBox.Icon.Question if not danger else QMessageBox.Icon.Warning)
    yes = box.addButton(ok_text, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
    if danger:
        yes.setObjectName("danger")
    box.setDefaultButton(cancel_text)
    box.exec()
    return box.clickedButton() is yes


def message(parent, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(title)
    box.setInformativeText(text)
    box.exec()


def prompt_text(parent, title: str, label: str, text: str = "", ok_text: str = "Save") -> str | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(380)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(label))
    editor = QLineEdit(text)
    editor.setMaxLength(24)
    layout.addWidget(editor)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        value = editor.text().strip()
        return value or None
    return None


def stat_row(caption: str, value: str, value_color: str | None = None) -> QWidget:
    """Compact 'caption .... value' row used on the results screen."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    caption_label = QLabel(caption)
    caption_label.setObjectName("dim")
    value_label = QLabel(value)
    font = QFont(theme.FONT_STACK)
    font.setBold(True)
    value_label.setFont(font)
    if value_color:
        value_label.setStyleSheet(f"color: {value_color};")
    layout.addWidget(caption_label)
    layout.addStretch(1)
    layout.addWidget(value_label)
    row.value_label = value_label      # convenient handle for updates
    return row


class StarRow(QWidget):
    """Row of three stars, ``filled`` of them lit (used on the results screen)."""

    def __init__(self, size: int = 34, filled: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.size = size
        self.filled = filled
        self.setFixedSize(size * 3 + 18, size + 8)

    def set_filled(self, filled: int) -> None:
        self.filled = max(0, min(3, filled))
        self.update()

    def paintEvent(self, event) -> None:
        pal = theme.palette(_current_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        spacing = self.size + 9
        for index in range(3):
            cx = self.size / 2 + index * spacing
            cy = self.height() / 2
            painter.setBrush(QColor(pal["gold"]) if index < self.filled else QColor(pal["border"]))
            painter.setPen(QPen(QColor(pal["gold"]) if index < self.filled else QColor(pal["border"]), 1))
            painter.drawPolygon(_star_polygon(cx, cy, self.size * 0.42))
