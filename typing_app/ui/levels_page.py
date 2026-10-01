"""Levels page: details about the current level plus the full level map."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from .. import config
from . import theme
from .widgets import Badge, Card, LevelMapWidget, PrimaryButton, stat_row


class LevelsPage(QWidget):
    open_level_requested = pyqtSignal(int)

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 22, 26, 26)
        layout.setSpacing(16)
        scroll.setWidget(page)

        # -- current level detail -------------------------------------------
        detail = Card("Current level")
        detail_layout = QVBoxLayout()
        detail_layout.setSpacing(8)
        self.detail_title = QLabel("Level 1")
        self.detail_title.setObjectName("h2")
        self.detail_description = QLabel("")
        self.detail_description.setObjectName("dim")
        self.detail_description.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_description)

        badges = QHBoxLayout()
        badges.setSpacing(8)
        self.badge_state = Badge("READY", theme.palette("dark")["accent"])
        self.badge_requirement = Badge("80% accuracy", theme.palette("dark")["text_dim"])
        self.badge_best = Badge("no record yet", theme.palette("dark")["text_dim"])
        for badge in (self.badge_state, self.badge_requirement, self.badge_best):
            badges.addWidget(badge)
        badges.addStretch(1)
        detail_layout.addLayout(badges)

        rows = QVBoxLayout()
        rows.setSpacing(5)
        self.row_best_wpm = stat_row("Best speed", "-")
        self.row_best_acc = stat_row("Best accuracy", "-")
        self.row_stars = stat_row("Stars", "-")
        self.row_attempts = stat_row("Attempts", "-")
        for row in (self.row_best_wpm, self.row_best_acc, self.row_stars, self.row_attempts):
            rows.addWidget(row)
        rows.setContentsMargins(0, 4, 0, 0)
        detail_layout.addLayout(rows)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.play_button = PrimaryButton("Play level 1")
        self.play_button.setMinimumSize(180, 46)
        self.play_button.clicked.connect(self._play_current)
        buttons.addWidget(self.play_button)
        buttons.addStretch(1)
        detail_layout.addLayout(buttons)
        detail.add_layout(detail_layout)
        layout.addWidget(detail)

        # -- full level map ---------------------------------------------------
        map_card = Card("All 100 levels")
        legend = QLabel(
            "Green outline = completed  -  blue outline = unlocked  -  grey = locked.  "
            "Stars: 1 for passing, 2 for +5 WPM and 90% accuracy, 3 for +10 WPM and 96% accuracy.")
        legend.setObjectName("dim")
        legend.setWordWrap(True)
        map_card.add_widget(legend)
        self.level_map = LevelMapWidget()
        self.level_map.level_clicked.connect(self.open_level_requested)
        map_card.add_widget(self.level_map)
        layout.addWidget(map_card)

        layout.addStretch(1)

    # -- data ---------------------------------------------------------------------
    def refresh(self) -> None:
        profile = self.controller.profile
        engine = self.controller.engine
        pal = theme.palette(_theme())
        current = engine.next_level(profile)
        spec = engine.spec(current)
        record = engine.level_record(profile, current) or {}

        self.detail_title.setText(
            f"Level {current}: {spec['title']}" + ("  (final test)" if spec.get("is_test") else ""))
        self.detail_description.setText(spec["description"])

        status = engine.status(current, profile)
        if status == "completed":
            self.badge_state.setText("COMPLETED")
            self.badge_state.setStyleSheet(self._badge_style(pal["green"]))
        elif status == "unlocked":
            self.badge_state.setText("READY TO PLAY")
            self.badge_state.setStyleSheet(self._badge_style(pal["accent"]))
        else:
            self.badge_state.setText("LOCKED")
            self.badge_state.setStyleSheet(self._badge_style(pal["text_dim"]))
        self.badge_requirement.setText(f"{spec['min_wpm']:.0f} WPM & {config.PASS_ACCURACY:.0f}% accuracy")

        if record.get("completed"):
            self.badge_best.setText(f"best {record.get('best_wpm', 0):.0f} WPM")
            self.row_best_wpm.value_label.setText(f"{record.get('best_wpm', 0):.1f} WPM")
            self.row_best_acc.value_label.setText(f"{record.get('best_acc', 0):.1f}%")
            stars = int(record.get("stars", 0) or 0)
            self.row_stars.value_label.setText("★" * stars + "☆" * (3 - stars))
            self.row_attempts.value_label.setText(str(record.get("attempts", 0)))
        else:
            self.badge_best.setText("no record yet")
            for row in (self.row_best_wpm, self.row_best_acc, self.row_stars, self.row_attempts):
                row.value_label.setText("-")

        self.play_button.setText(f"Play level {current}")
        self.play_button.setEnabled(status != "locked")

        levels = []
        for level in range(1, config.TOTAL_LEVELS + 1):
            level_record = engine.level_record(profile, level) or {}
            levels.append({
                "level": level,
                "status": engine.status(level, profile),
                "stars": int(level_record.get("stars", 0) or 0),
                "current": level == current,
            })
        self.level_map.set_levels(levels)

    @staticmethod
    def _badge_style(color: str) -> str:
        return (f"color: {color}; border: 1px solid {color}; border-radius: 9px;"
                " padding: 2px 9px; font-weight: bold;")

    def _play_current(self) -> None:
        self.open_level_requested.emit(self.controller.engine.next_level(self.controller.profile))


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
