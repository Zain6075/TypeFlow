"""Lightweight charts drawn with QPainter (no extra dependencies).

``LineChart`` plots one or two series over time (WPM / accuracy history) and
``BarList`` renders horizontal bars (weakest keys, practice minutes).
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from . import theme


class LineChart(QWidget):
    """Simple line chart with grid, axis labels and per-series colours."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.title = title
        self.series: list[dict] = []   # [{"name": str, "color": str, "points": [(x, y)]}]
        self.y_min = 0.0
        self.y_max = 100.0
        self.y_suffix = ""
        self.setMinimumSize(320, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, series: list[dict], y_min: float = 0.0, y_max: float = 100.0,
                 y_suffix: str = "") -> None:
        self.series = series
        self.y_min, self.y_max, self.y_suffix = y_min, y_max, y_suffix
        self.update()

    def paintEvent(self, event) -> None:
        pal = theme.palette(_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, top, bottom = 46, 14, (26 if self.title else 8), 30
        plot = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        if plot.width() <= 10 or plot.height() <= 10:
            return

        if self.title:
            painter.setPen(QColor(pal["text"]))
            font = QFont(theme.FONT_STACK)
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(0, 4, self.width(), 20), Qt.AlignmentFlag.AlignLeft, self.title)

        # Horizontal grid lines + Y labels.
        painter.setFont(QFont(theme.FONT_STACK, 8))
        grid = QColor(pal["chart_grid"])
        steps = 4
        for index in range(steps + 1):
            ratio = index / steps
            y = plot.bottom() - ratio * plot.height()
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            value = self.y_min + ratio * (self.y_max - self.y_min)
            painter.setPen(QColor(pal["text_dim"]))
            painter.drawText(QRectF(0, y - 8, left - 8, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:.0f}{self.y_suffix}")

        if not any(s["points"] for s in self.series):
            painter.setPen(QColor(pal["text_dim"]))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No data yet - play a level!")
            return

        # X range shared by all series.
        all_x = [point[0] for s in self.series for point in s["points"]]
        x_min, x_max = min(all_x), max(all_x)
        if x_max == x_min:
            x_max = x_min + 1

        for s in self.series:
            if not s["points"]:
                continue
            color = QColor(s.get("color") or pal["chart_line"])
            path = QPainterPath()
            for index, (x, y, *_label) in enumerate(s["points"]):
                px = plot.left() + (x - x_min) / (x_max - x_min) * plot.width()
                py = plot.bottom() - (max(self.y_min, min(self.y_max, y)) - self.y_min) / \
                     (self.y_max - self.y_min) * plot.height()
                point = QPointF(px, py)
                path.moveTo(point) if index == 0 else path.lineTo(point)
            painter.setPen(QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            # Dots.
            for point in s["points"]:
                x, y = point[0], point[1]
                px = plot.left() + (x - x_min) / (x_max - x_min) * plot.width()
                py = plot.bottom() - (max(self.y_min, min(self.y_max, y)) - self.y_min) / \
                     (self.y_max - self.y_min) * plot.height()
                painter.setBrush(color)
                painter.setPen(QPen(color, 1))
                painter.drawEllipse(QRectF(px - 2.6, py - 2.6, 5.2, 5.2))

        # X labels: first / last entry.
        painter.setPen(QColor(pal["text_dim"]))
        painter.setFont(QFont(theme.FONT_STACK, 8))
        first_label = self.series[0]["points"][0][2] if len(self.series[0]["points"][0]) > 2 else ""
        last_label = self.series[0]["points"][-1][2] if len(self.series[0]["points"][-1]) > 2 else ""
        if first_label:
            painter.drawText(QRectF(plot.left(), plot.bottom() + 6, plot.width() / 2, 18),
                             Qt.AlignmentFlag.AlignLeft, str(first_label))
        if last_label:
            painter.drawText(QRectF(plot.left() + plot.width() / 2, plot.bottom() + 6,
                                    plot.width() / 2, 18),
                             Qt.AlignmentFlag.AlignRight, str(last_label))

        # Legend.
        legend_x = left + 6
        for s in self.series:
            if not s["points"]:
                continue
            color = QColor(s.get("color") or pal["chart_line"])
            painter.setBrush(color)
            painter.setPen(QPen(color, 1))
            painter.drawRoundedRect(QRectF(legend_x, top + 4, 9, 9), 2, 2)
            painter.setPen(QColor(pal["text_dim"]))
            painter.drawText(QRectF(legend_x + 13, top, 140, 18), Qt.AlignmentFlag.AlignVCenter, s["name"])
            legend_x += 13 + 8 * len(s["name"]) + 22


class BarList(QWidget):
    """Horizontal bars with a label on the left and a value on the right."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.rows: list[tuple[str, float, str]] = []   # (label, 0..1 ratio, value text)
        self.color = "#f87171"
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows: list[tuple[str, float, str]], color: str = "#f87171") -> None:
        self.rows = rows
        self.color = color
        self.update()

    def paintEvent(self, event) -> None:
        pal = theme.palette(_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.rows:
            painter.setPen(QColor(pal["text_dim"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No mistakes recorded yet - nice work!")
            return
        row_height = min(26.0, (self.height() - 8) / max(1, len(self.rows)))
        label_width = 54
        value_width = 74
        bar_max = self.width() - label_width - value_width - 24
        y = 4.0
        for label, ratio, value in self.rows:
            painter.setPen(QColor(pal["text"]))
            font = QFont(theme.MONO_STACK)
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(0, y, label_width - 8, row_height),
                             Qt.AlignmentFlag.AlignVCenter, label.upper())
            track = QRectF(label_width, y + row_height * 0.28, bar_max, row_height * 0.44)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(pal["surface_alt"]))
            painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
            if ratio > 0:
                filled = QRectF(track.left(), track.top(), max(6.0, track.width() * min(1.0, ratio)),
                                track.height())
                painter.setBrush(QColor(self.color))
                painter.drawRoundedRect(filled, filled.height() / 2, filled.height() / 2)
            painter.setPen(QColor(pal["text_dim"]))
            painter.setFont(QFont(theme.FONT_STACK, 9))
            painter.drawText(QRectF(track.right() + 10, y, value_width, row_height),
                             Qt.AlignmentFlag.AlignVCenter, value)
            y += row_height


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
