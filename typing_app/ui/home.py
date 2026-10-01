"""Home page: welcome, profile switcher, the big Continue button, quick stats,
the level map and shortcuts to every other screen.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from .. import config, stats as stats_mod
from . import theme
from .widgets import Card, GhostButton, LevelMapWidget, PrimaryButton, StatCard


class HomePage(QWidget):
    open_level_requested = pyqtSignal(int)
    navigate_requested = pyqtSignal(str)      # "levels" | "leaderboard" | "stats" | "settings"
    switch_profile_requested = pyqtSignal(str)
    manage_profiles_requested = pyqtSignal()

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

        # -- welcome + profile switcher -------------------------------------
        welcome_row = QHBoxLayout()
        welcome_column = QVBoxLayout()
        welcome_column.setSpacing(2)
        self.welcome_label = QLabel("Welcome back!")
        self.welcome_label.setObjectName("h1")
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("dim")
        welcome_column.addWidget(self.welcome_label)
        welcome_column.addWidget(self.progress_label)
        welcome_row.addLayout(welcome_column)
        welcome_row.addStretch(1)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(190)
        self.profile_combo.currentIndexChanged.connect(self._combo_changed)
        welcome_row.addWidget(self.profile_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        manage_button = GhostButton("Manage profiles")
        manage_button.clicked.connect(self.manage_profiles_requested)
        welcome_row.addWidget(manage_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(welcome_row)

        # -- continue hero ---------------------------------------------------
        hero = Card()
        hero_layout = QHBoxLayout()
        hero_layout.setSpacing(18)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        self.continue_title = QLabel("Continue where you left off")
        self.continue_title.setObjectName("h2")
        self.continue_subtitle = QLabel("")
        self.continue_subtitle.setObjectName("dim")
        self.continue_subtitle.setWordWrap(True)
        hero_text.addWidget(self.continue_title)
        hero_text.addWidget(self.continue_subtitle)
        hero_layout.addLayout(hero_text, 1)
        self.continue_button = PrimaryButton("Continue")
        self.continue_button.setMinimumSize(190, 56)
        self.continue_button.clicked.connect(self._continue)
        hero_layout.addWidget(self.continue_button, 0, Qt.AlignmentFlag.AlignVCenter)
        hero.add_layout(hero_layout)
        layout.addWidget(hero)

        # -- quick stats ------------------------------------------------------
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.streak_card = StatCard("Day streak", "0")
        self.avg_card = StatCard("Average WPM", "-")
        self.best_card = StatCard("Best WPM", "-")
        self.accuracy_card = StatCard("Accuracy", "-")
        for card in (self.streak_card, self.avg_card, self.best_card, self.accuracy_card):
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # -- shortcuts ----------------------------------------------------------
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(12)
        for label, target in (("Levels", "levels"), ("Leaderboard", "leaderboard"),
                              ("Stats", "stats"), ("Settings", "settings")):
            button = GhostButton(label)
            button.setMinimumHeight(44)
            button.clicked.connect(lambda _checked, name=target: self.navigate_requested.emit(name))
            shortcuts.addWidget(button)
        layout.addLayout(shortcuts)

        # -- level map ----------------------------------------------------------
        map_card = Card("Level map - 100 levels")
        map_note = QLabel("Finish a level with 80% accuracy and the required speed to unlock the next one.")
        map_note.setObjectName("dim")
        map_card.add_widget(map_note)
        self.level_map = LevelMapWidget()
        self.level_map.level_clicked.connect(self.open_level_requested)
        map_card.add_widget(self.level_map)
        layout.addWidget(map_card)

        layout.addStretch(1)

    # -- data -----------------------------------------------------------------------
    def refresh(self) -> None:
        profile = self.controller.profile
        engine = self.controller.engine
        pal = theme.palette(_theme())

        # Profile switcher (avoid re-populating while the user is browsing it).
        profiles = self.controller.profiles
        if self.profile_combo.count() != len(profiles):
            self.profile_combo.blockSignals(True)
            self.profile_combo.clear()
            for header in profiles:
                self.profile_combo.addItem(header.get("name", "Player"), header.get("id"))
            self.profile_combo.blockSignals(False)
        index = self.profile_combo.findData(profile.get("id"))
        if index >= 0:
            self.profile_combo.blockSignals(True)
            self.profile_combo.setCurrentIndex(index)
            self.profile_combo.blockSignals(False)

        self.welcome_label.setText(f"Welcome back, {profile.get('name', 'Player')}!")
        highest = engine.highest_completed(profile)
        stars = engine.total_stars(profile)
        self.progress_label.setText(
            f"{highest} of {config.TOTAL_LEVELS} levels completed  -  {stars} / 300 stars  -  "
            f"last played {stats_mod.last_played_display(profile)}")

        next_level = engine.next_level(profile)
        spec = engine.spec(next_level)
        if next_level > config.TOTAL_LEVELS:
            self.continue_title.setText("Campaign complete!")
            self.continue_subtitle.setText("You have finished all 100 levels. Replay any level for more stars.")
        elif spec.get("is_test"):
            self.continue_title.setText(f"Final test {next_level}")
            self.continue_subtitle.setText(f"{spec['title']} - everything you have learned, mixed together.")
        else:
            self.continue_title.setText(f"Level {next_level}: {spec['title']}")
            self.continue_subtitle.setText(
                f"{spec['description']}  -  pass with {config.PASS_ACCURACY:.0f}% accuracy "
                f"and {spec['min_wpm']:.0f} WPM.")
        self.continue_button.setText("Continue" if highest else "Start typing")

        streak = stats_mod.current_streak(profile)
        self.streak_card.set_value(f"{streak} day{'s' if streak != 1 else ''}",
                                   f"best: {stats_mod.longest_streak(profile)} days")
        self.avg_card.set_value(f"{stats_mod.average_wpm(profile):.0f}",
                                f"avg accuracy {stats_mod.average_accuracy(profile):.0f}%")
        self.best_card.set_value(f"{stats_mod.best_wpm(profile):.0f}",
                                 f"across {stats_mod.session_count(profile)} sessions",
                                 accent=pal["accent"])
        self.accuracy_card.set_value(f"{stats_mod.overall_accuracy(profile):.1f}%",
                                     f"{stats_mod.format_duration(stats_mod.total_practice_seconds(profile))} practised")

        # Level map.
        levels = []
        for level in range(1, config.TOTAL_LEVELS + 1):
            record = engine.level_record(profile, level) or {}
            levels.append({
                "level": level,
                "status": engine.status(level, profile),
                "stars": int(record.get("stars", 0) or 0),
                "current": level == next_level and next_level <= config.TOTAL_LEVELS,
            })
        self.level_map.set_levels(levels)

    # -- slots -------------------------------------------------------------------------
    def _combo_changed(self, index: int) -> None:
        profile_id = self.profile_combo.itemData(index)
        if profile_id and profile_id != self.controller.profile.get("id"):
            self.switch_profile_requested.emit(profile_id)

    def _continue(self) -> None:
        next_level = self.controller.engine.next_level(self.controller.profile)
        self.open_level_requested.emit(min(next_level, config.TOTAL_LEVELS))


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
