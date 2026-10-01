"""The big text display of the typing screen.

Characters are painted individually so correct letters can be green, mistakes
red, and the next expected character can carry a blinking caret.  Long lessons
wrap onto multiple lines and the view auto-scrolls to keep the current line
visible.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from . import theme
from ..typing_engine import UNTYPED, CORRECT, WRONG


class TypingTextWidget(QWidget):
    """Renders ``text`` coloured by per-character ``states``."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.text = ""
        self.states: list[int] = []
        self.pos = 0
        self.font_size = 16
        self.scroll_line = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)

    # -- data ------------------------------------------------------------------
    def set_text(self, text: str, states: list[int], font_size: int | None = None) -> None:
        self.text = text
        self.states = states
        self.pos = 0
        self.scroll_line = 0
        if font_size:
            self.font_size = font_size
        self.update()

    def set_progress(self, pos: int, states: list[int]) -> None:
        self.pos = pos
        self.states = states
        self._auto_scroll()
        self.update()

    # -- layout ------------------------------------------------------------------
    def _metrics(self) -> tuple[QFont, QFontMetrics, float, float]:
        font = QFont(theme.MONO_STACK)
        font.setPointSize(self.font_size)
        metrics = QFontMetrics(font)
        char_width = max(6.0, metrics.horizontalAdvance("M"))
        line_height = metrics.height() * 1.42
        return font, metrics, char_width, line_height

    def _lines(self, char_width: float) -> list[tuple[int, int]]:
        """Greedy word wrap -> list of (start, end) character ranges."""
        padding = 16.0
        usable = max(40.0, self.width() - padding * 2)
        per_line = max(10, int(usable // char_width))
        lines: list[tuple[int, int]] = []
        start = 0
        index = 0
        length = len(self.text)
        while index < length:
            limit = min(length, start + per_line)
            if limit < length:
                # Back up to the last space so words are not split.
                space = self.text.rfind(" ", start, limit)
                if space > start:
                    limit = space + 1
            lines.append((start, limit))
            start = limit
            index = limit
        return lines or [(0, 0)]

    def _auto_scroll(self) -> None:
        _font, _metrics, char_width, line_height = self._metrics()
        lines = self._lines(char_width)
        visible = max(1, int((self.height() - 24) // line_height))
        current_line = 0
        for index, (start, end) in enumerate(lines):
            if start <= self.pos < end or (self.pos >= end and index == len(lines) - 1):
                current_line = index
                break
        if current_line < self.scroll_line:
            self.scroll_line = max(0, current_line - 1)
        elif current_line >= self.scroll_line + visible - 1:
            self.scroll_line = max(0, current_line - visible + 2)

    # -- painting ------------------------------------------------------------------
    def paintEvent(self, event) -> None:
        pal = theme.palette(_theme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(pal["surface"]))

        font, _metrics, char_width, line_height = self._metrics()
        painter.setFont(font)
        padding = 16.0
        lines = self._lines(char_width)
        visible = max(1, int((self.height() - 16) // line_height))
        start_line = min(self.scroll_line, max(0, len(lines) - visible))
        y = 10.0

        colors = {
            UNTYPED: QColor(pal["text_dim"]),
            CORRECT: QColor(pal["green"]),
            WRONG: QColor(pal["red"]),
        }
        caret = QColor(pal["accent"])
        wrong_bg = QColor(pal["red_soft"])
        caret_bg = QColor(pal["accent"])
        caret_bg.setAlpha(38)

        for line_index in range(start_line, min(len(lines), start_line + visible + 1)):
            start, end = lines[line_index]
            x = padding
            for index in range(start, end):
                char = self.text[index]
                state = self.states[index] if index < len(self.states) else UNTYPED
                rect = QRectF(x, y, char_width, line_height)
                if state == WRONG:
                    painter.fillRect(QRectF(x, y + line_height * 0.12, char_width,
                                            line_height * 0.76), wrong_bg)
                if index == self.pos:
                    painter.fillRect(QRectF(x, y + line_height * 0.12, char_width,
                                            line_height * 0.76), caret_bg)
                painter.setPen(colors.get(state, colors[UNTYPED]))
                if char == " ":
                    if state == WRONG:
                        painter.fillRect(QRectF(x + char_width * 0.2, y + line_height * 0.45,
                                                char_width * 0.6, 2.0), colors[WRONG])
                    elif index == self.pos:
                        painter.fillRect(QRectF(x + char_width * 0.15, y + line_height * 0.48,
                                                char_width * 0.7, 2.0), caret)
                else:
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, char)
                x += char_width
            y += line_height

        # Progress hint at the bottom of the widget.
        if self.text:
            done = self.pos / max(1, len(self.text))
            painter.setPen(QColor(pal["text_dim"]))
            hint_font = QFont(theme.FONT_STACK)
            hint_font.setPointSize(8)
            painter.setFont(hint_font)
            painter.drawText(QRectF(padding, self.height() - 18, self.width() - padding * 2, 14),
                             Qt.AlignmentFlag.AlignRight, f"{done * 100:.0f}%")


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
