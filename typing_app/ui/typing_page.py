"""The typing screen: live statistics, coloured text, on-screen keyboard.

The page owns a :class:`~typing_app.typing_engine.TypingEngine` instance for
the current lesson and feeds it keystrokes.  When the lesson is finished it
hands the result to the main window (``controller.on_level_finished``), which
saves progress and shows the results screen.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import config
from ..typing_engine import TypingEngine
from . import theme
from .keyboard_view import KeyboardView
from .typing_text import TypingTextWidget
from .widgets import Badge, Card, GhostButton


class TypingPage(QWidget):
    """Practice one level."""

    # Emitted when the player leaves the screen without finishing.
    abandon_requested = pyqtSignal()

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.level = 1
        self.spec: dict = {}
        self.engine: TypingEngine | None = None
        self.show_keyboard = True
        self._build()

        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._refresh_live_stats)

    # -- UI -------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 20)
        root.setSpacing(14)

        # Header row: level identity + requirement + quick toggles.
        header = QHBoxLayout()
        header.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.level_label = QLabel("Level 1")
        self.level_label.setObjectName("h1")
        self.title_label = QLabel("")
        self.title_label.setObjectName("dim")
        titles.addWidget(self.level_label)
        titles.addWidget(self.title_label)
        header.addLayout(titles)
        header.addStretch(1)

        self.requirement_badge = Badge("Needs 80% accuracy", theme.palette("dark")["accent"])
        header.addWidget(self.requirement_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.keyboard_button = GhostButton("Keyboard: on")
        self.keyboard_button.setCheckable(True)
        self.keyboard_button.setChecked(True)
        self.keyboard_button.clicked.connect(self._toggle_keyboard)
        header.addWidget(self.keyboard_button)

        self.sound_button = GhostButton("Sound: on")
        self.sound_button.setCheckable(True)
        self.sound_button.setChecked(True)
        self.sound_button.clicked.connect(self._toggle_sound)
        header.addWidget(self.sound_button)

        quit_button = GhostButton("Quit")
        quit_button.clicked.connect(self.abandon_requested.emit)
        header.addWidget(quit_button)
        root.addLayout(header)

        # Live statistics.
        stats_card = Card()
        stats_row = QHBoxLayout()
        stats_row.setSpacing(26)
        self.wpm_label = self._live_stat(stats_row, "WPM", "0")
        self.accuracy_label = self._live_stat(stats_row, "Accuracy", "100%")
        self.errors_label = self._live_stat(stats_row, "Errors", "0")
        self.time_label = self._live_stat(stats_row, "Time", "0:00")
        stats_row.addStretch(1)
        stats_card.add_layout(stats_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMaximum(1000)
        stats_card.add_widget(self.progress)
        root.addWidget(stats_card)

        # The lesson text.
        self.text_widget = TypingTextWidget()
        root.addWidget(self.text_widget, 1)

        # On-screen keyboard.
        self.keyboard = KeyboardView()
        self.keyboard.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.keyboard)

    def _live_stat(self, layout, caption: str, value: str) -> QLabel:
        column = QVBoxLayout()
        column.setSpacing(0)
        caption_label = QLabel(caption.upper())
        caption_label.setObjectName("dim")
        caption_font = theme.app_font(8)
        caption_font.setBold(True)
        caption_label.setFont(caption_font)
        value_label = QLabel(value)
        value_font = theme.app_font(20)
        value_font.setBold(True)
        value_label.setFont(value_font)
        column.addWidget(caption_label)
        column.addWidget(value_label)
        layout.addLayout(column)
        return value_label

    # -- lifecycle --------------------------------------------------------------
    def start_level(self, level: int) -> None:
        """Prepare the lesson for ``level`` using the current profile."""
        self.level = level
        self.spec = self.controller.engine.spec(level)
        profile = self.controller.profile
        text = self.controller.engine.build_text(level, profile)

        self.engine = TypingEngine(text)
        self.level_label.setText(f"Level {level}" + ("  -  final test" if self.spec.get("is_test") else ""))
        self.title_label.setText(f"{self.spec['title']}  |  {self.spec['description']}")
        need_wpm = self.spec["min_wpm"]
        self.requirement_badge.setText(f"Pass: {need_wpm:.0f} WPM & {config.PASS_ACCURACY:.0f}% accuracy")
        self.text_widget.set_text(text, self.engine.states,
                                  font_size=self.controller.settings.get("font_size", 16) + 1)

        # Keyboard guide: on by default (settings), toggled off per-lesson.
        settings = self.controller.settings
        self.show_keyboard = bool(settings.get("keyboard_guide", True))
        self.keyboard.setVisible(self.show_keyboard)
        self.keyboard_button.setChecked(self.show_keyboard)
        self.keyboard_button.setText(f"Keyboard: {'on' if self.show_keyboard else 'off'}")
        self.keyboard.set_scale(self.controller.settings.get("font_size", 16) / 16.0)
        self.keyboard.set_next_key(self.engine.next_char)

        sound_on = bool(settings.get("sound", True))
        self.sound_button.setChecked(sound_on)
        self.sound_button.setText(f"Sound: {'on' if sound_on else 'off'}")
        self.controller.sound.set_enabled(sound_on)

        self._refresh_live_stats()
        self.setFocus()

    # -- input -------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.engine is None or self.engine.finished:
            return
        key = event.key()
        if key == Qt.Key.Key_Backspace:
            self.engine.backspace()
            self.keyboard.set_next_key(self.engine.next_char)
            self._sync_text()
            event.accept()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up,
                   Qt.Key.Key_Down, Qt.Key.Key_Escape, Qt.Key.Key_Return):
            event.ignore()
            return
        text = event.text()
        if not text:
            event.ignore()
            return
        char = text[0]
        if char.isprintable() or char == " ":
            self._press(char)
            event.accept()
        else:
            event.ignore()

    def _press(self, char: str) -> None:
        """Feed one character into the engine (also used by tests)."""
        engine = self.engine
        if engine is None or engine.finished:
            return
        expected = engine.next_char
        engine.press(char)
        if char != expected:
            self.controller.sound.play("error")
            self._flash_errors()
        else:
            self.controller.sound.play("click")
        self.keyboard.set_next_key(engine.next_char)
        self._sync_text()
        self._refresh_live_stats()
        if engine.finished:
            self._finish()

    def _sync_text(self) -> None:
        self.text_widget.set_progress(self.engine.pos, self.engine.states)

    def _flash_errors(self) -> None:
        self.errors_label.setStyleSheet(f"color: {theme.palette(_theme())['red']};")
        QTimer.singleShot(220, self._reset_error_color)

    def _reset_error_color(self) -> None:
        self.errors_label.setStyleSheet("")

    def _refresh_live_stats(self) -> None:
        if self.engine is None:
            return
        engine = self.engine
        self.wpm_label.setText(f"{engine.live_wpm():.0f}")
        accuracy = engine.live_accuracy()
        pal = theme.palette(_theme())
        self.accuracy_label.setText(f"{accuracy:.1f}%")
        self.accuracy_label.setStyleSheet(
            "" if accuracy >= config.PASS_ACCURACY else f"color: {pal['red']};")
        self.errors_label.setText(str(engine.errors))
        minutes, seconds = divmod(int(engine.elapsed), 60)
        self.time_label.setText(f"{minutes}:{seconds:02d}")
        self.progress.setValue(int(engine.progress() * 1000))

    # -- toggles ------------------------------------------------------------------
    def _toggle_keyboard(self) -> None:
        self.show_keyboard = self.keyboard_button.isChecked()
        self.keyboard.setVisible(self.show_keyboard)
        self.keyboard_button.setText(f"Keyboard: {'on' if self.show_keyboard else 'off'}")

    def _toggle_sound(self) -> None:
        enabled = self.sound_button.isChecked()
        self.controller.settings["sound"] = enabled
        self.controller.sound.set_enabled(enabled)
        self.sound_button.setText(f"Sound: {'on' if enabled else 'off'}")
        self.controller.save_settings()

    # -- finish ----------------------------------------------------------------------
    def _finish(self) -> None:
        self.timer.stop()
        self.controller.sound.play("complete")
        result = self.engine.result()
        QTimer.singleShot(320, lambda: self.controller.on_level_finished(self.level, result))


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
