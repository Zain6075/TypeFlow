"""Results screen shown after every lesson attempt.

Displays the earned stars, the detailed numbers, whether the level was passed
(and the next level unlocked) and the buttons to retry, continue or go home.
Retries are always allowed and never penalised.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import config, stats as stats_mod
from ..typing_engine import TypingResult
from . import theme
from .widgets import Badge, Card, GhostButton, PrimaryButton, StarRow, stat_row


class ResultsPage(QWidget):
    retry_requested = pyqtSignal()
    next_requested = pyqtSignal()
    home_requested = pyqtSignal()
    levels_requested = pyqtSignal()

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.level = 1
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        card = Card()
        card.setMaximumWidth(560)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.stars = StarRow(size=40)
        layout.addWidget(self.stars, 0, Qt.AlignmentFlag.AlignCenter)

        self.headline = QLabel("Level complete!")
        self.headline.setObjectName("h1")
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.headline)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("dim")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.badge_row = QHBoxLayout()
        self.badge_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(self.badge_row)

        rows = QVBoxLayout()
        rows.setSpacing(6)
        self.wpm_row = stat_row("Speed", "-")
        self.accuracy_row = stat_row("Accuracy", "-")
        self.errors_row = stat_row("Mistakes", "-")
        self.time_row = stat_row("Time", "-")
        self.chars_row = stat_row("Characters", "-")
        for row in (self.wpm_row, self.accuracy_row, self.errors_row, self.time_row, self.chars_row):
            rows.addWidget(row)
        rows.setContentsMargins(40, 14, 40, 4)
        layout.addLayout(rows)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.retry_button = GhostButton("Retry level")
        self.retry_button.clicked.connect(self.retry_requested)
        self.levels_button = GhostButton("Level map")
        self.levels_button.clicked.connect(self.levels_requested)
        self.next_button = PrimaryButton("Next level")
        self.next_button.clicked.connect(self.next_requested)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.levels_button)
        buttons.addWidget(self.next_button)
        layout.addLayout(buttons)

        self.home_button = GhostButton("Back to home")
        self.home_button.clicked.connect(self.home_requested)
        layout.addWidget(self.home_button, 0, Qt.AlignmentFlag.AlignCenter)

        card.add_layout(layout)
        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(card)
        center.addStretch(1)
        root.addLayout(center)
        root.addStretch(1)

    # -- data ---------------------------------------------------------------------
    def show_result(self, level: int, result: TypingResult, passed: bool, stars: int,
                    unlocked_next: int | None, is_new_best: bool, valid: bool) -> None:
        self.level = level
        pal = theme.palette(_theme())
        self.stars.set_filled(stars)

        if not valid:
            self.headline.setText("Result not recorded")
            self.subtitle.setText(
                f"That result ({result.wpm:.0f} WPM) is not physically possible, so it was "
                "ignored. Your practice time was still counted - please try again.")
        elif passed:
            self.headline.setText("Level complete!")
            self.subtitle.setText(
                f"You passed level {level} with {result.wpm:.0f} WPM and "
                f"{result.accuracy:.1f}% accuracy.")
        else:
            self.headline.setText("Not quite yet")
            need_wpm = self.controller.engine.min_wpm(level)
            self.subtitle.setText(
                f"Level {level} needs at least {config.PASS_ACCURACY:.0f}% accuracy and "
                f"{need_wpm:.0f} WPM. Slow down a little and try again - retries are free!")

        # Badges: pass state, new personal best, next unlock.
        for i in reversed(range(self.badge_row.count())):
            widget = self.badge_row.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        if valid and passed:
            self.badge_row.addWidget(Badge("PASSED", pal["green"]))
        elif valid:
            self.badge_row.addWidget(Badge("KEEP TRYING", pal["red"]))
        if is_new_best:
            self.badge_row.addWidget(Badge("NEW PERSONAL BEST", pal["gold"]))
        if unlocked_next is not None:
            self.badge_row.addWidget(Badge(f"LEVEL {unlocked_next} UNLOCKED", pal["accent"]))

        self.wpm_row.value_label.setText(f"{result.wpm:.1f} WPM")
        self.accuracy_row.value_label.setText(f"{result.accuracy:.1f}%")
        self.accuracy_row.value_label.setStyleSheet(
            "" if result.accuracy >= config.PASS_ACCURACY
            else f"color: {pal['red']}; font-weight: bold;")
        self.errors_row.value_label.setText(str(result.errors))
        self.time_row.value_label.setText(stats_mod.format_duration(result.duration))
        self.chars_row.value_label.setText(str(result.chars))

        has_next = unlocked_next is not None and unlocked_next <= config.TOTAL_LEVELS
        is_final = level >= config.TOTAL_LEVELS
        self.next_button.setEnabled(passed and (has_next or is_final))
        self.next_button.setText("Finish campaign" if is_final else "Next level")


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
