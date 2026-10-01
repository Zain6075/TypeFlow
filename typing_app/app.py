"""Application shell: the main window, navigation and the "controller" object
that every page talks to.

The window owns the storage, the settings, the current profile and the level
engine.  Pages receive this window as their ``controller`` and call its public
methods (``open_level``, ``switch_profile``, ...) instead of reaching into each
other, which keeps the UI modules independent.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import config, stats as stats_mod
from .audio import SoundManager
from .level_engine import LevelEngine, load_lessons
from .storage import Storage
from .typing_engine import TypingResult
from .ui import theme
from .ui.home import HomePage
from .ui.leaderboard_page import LeaderboardPage
from .ui.levels_page import LevelsPage
from .ui.profiles_page import ProfilesPage
from .ui.results_page import ResultsPage
from .ui.settings_page import SettingsPage
from .ui.stats_page import StatsPage
from .ui.typing_page import TypingPage

NAV_ITEMS = [
    ("home", "Home"),
    ("levels", "Levels"),
    ("leaderboard", "Leaderboard"),
    ("stats", "Statistics"),
    ("settings", "Settings"),
    ("profiles", "Profiles"),
]


class MainWindow(QMainWindow):
    """Main application window and shared controller."""

    def __init__(self, storage: Storage | None = None):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} - offline typing trainer")
        self.resize(1180, 820)
        self.setMinimumSize(940, 660)

        # -- model -----------------------------------------------------------
        self.storage = storage or Storage()
        self.settings = self.storage.load_settings()
        self.profile_headers = self.storage.load_profiles()
        if not self.profile_headers:
            self.storage.create_profile("Player")
            self.profile_headers = self.storage.load_profiles()
        self._profile: dict = self._load_current_profile()
        self.engine = LevelEngine(load_lessons())
        self.sound = SoundManager(config.sounds_dir(),
                                  enabled=bool(self.settings.get("sound", True)),
                                  volume=int(self.settings.get("volume", 60)))

        # -- view ------------------------------------------------------------
        self._build_ui()
        self.apply_settings()
        self.navigate("home")
        self.refresh_all()

    # ------------------------------------------------------------------ setup
    def _load_current_profile(self) -> dict:
        """Load the profile remembered in settings (falling back to the first)."""
        wanted = self.settings.get("current_profile")
        for header in self.profile_headers:
            if header.get("id") == wanted:
                profile = self.storage.load_profile(header["id"])
                if profile:
                    return profile
        profile = self.storage.load_profile(self.profile_headers[0]["id"])
        return profile or self.storage.create_profile("Player")

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- sidebar ---------------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(214)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 20, 14, 16)
        sidebar_layout.setSpacing(6)

        logo = QLabel(config.APP_NAME)
        logo.setObjectName("h1")
        logo.setStyleSheet("font-size: 19pt;")
        tagline = QLabel("offline typing trainer")
        tagline.setObjectName("dim")
        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(tagline)
        sidebar_layout.addSpacing(16)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, object] = {}
        for key, label in NAV_ITEMS:
            button = theme_nav_button(label)
            button.setCheckable(True)
            button.setObjectName("nav")
            button.clicked.connect(lambda _checked, name=key: self.navigate(name))
            self.nav_group.addButton(button)
            sidebar_layout.addWidget(button)
            self.nav_buttons[key] = button
        sidebar_layout.addStretch(1)

        # Profile summary at the bottom of the sidebar.
        self.sidebar_profile_name = QLabel("Player")
        self.sidebar_profile_name.setStyleSheet("font-weight: bold;")
        self.sidebar_profile_detail = QLabel("level 1  -  0 stars")
        self.sidebar_profile_detail.setObjectName("dim")
        sidebar_layout.addWidget(self.sidebar_profile_name)
        sidebar_layout.addWidget(self.sidebar_profile_detail)
        root.addWidget(sidebar)

        # -- stacked pages -----------------------------------------------------
        self.stack = QStackedWidget()
        self.home_page = HomePage(self)
        self.levels_page = LevelsPage(self)
        self.typing_page = TypingPage(self)
        self.results_page = ResultsPage(self)
        self.leaderboard_page = LeaderboardPage(self)
        self.stats_page = StatsPage(self)
        self.settings_page = SettingsPage(self)
        self.profiles_page = ProfilesPage(self)

        for page in (self.home_page, self.levels_page, self.typing_page, self.results_page,
                     self.leaderboard_page, self.stats_page, self.settings_page,
                     self.profiles_page):
            self.stack.addWidget(page)

        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # -- status bar ----------------------------------------------------------
        self.statusBar().showMessage("Ready")

        # -- wiring ---------------------------------------------------------------
        self.home_page.open_level_requested.connect(self.open_level)
        self.home_page.navigate_requested.connect(self.navigate)
        self.home_page.switch_profile_requested.connect(self.switch_profile)
        self.home_page.manage_profiles_requested.connect(lambda: self.navigate("profiles"))
        self.levels_page.open_level_requested.connect(self.open_level)
        self.typing_page.abandon_requested.connect(self._abandon_level)
        self.results_page.retry_requested.connect(lambda: self.open_level(self._last_level))
        self.results_page.next_requested.connect(self._open_next_level)
        self.results_page.home_requested.connect(lambda: self.navigate("home"))
        self.results_page.levels_requested.connect(lambda: self.navigate("levels"))
        self.leaderboard_page.data_changed.connect(self.refresh_all)
        self.settings_page.settings_changed.connect(self.apply_settings)
        self.profiles_page.profiles_changed.connect(self.refresh_all)

    # ------------------------------------------------------------- navigation
    def navigate(self, name: str) -> None:
        pages = {
            "home": self.home_page, "levels": self.levels_page, "leaderboard": self.leaderboard_page,
            "stats": self.stats_page, "settings": self.settings_page, "profiles": self.profiles_page,
        }
        page = pages.get(name)
        if page is None:
            return
        if name in ("levels", "stats", "leaderboard", "profiles"):
            page.refresh()
        self.stack.setCurrentWidget(page)
        button = self.nav_buttons.get(name)
        if button:
            button.setChecked(True)
        self.statusBar().showMessage(f"{config.APP_NAME}  -  {name.title()}")

    def refresh_all(self) -> None:
        """Re-read profile data and refresh every visible page."""
        self.profile_headers = self.storage.load_profiles()
        if not self.profile_headers:                      # last profile deleted
            self.storage.create_profile("Player")
            self.profile_headers = self.storage.load_profiles()
        if self._profile.get("id") not in {h.get("id") for h in self.profile_headers}:
            self._profile = self._load_current_profile()
        self.home_page.refresh()
        self.levels_page.refresh()
        self.stats_page.refresh()
        self.leaderboard_page.refresh()
        self.profiles_page.refresh()
        self._refresh_sidebar()

    def _refresh_sidebar(self) -> None:
        profile = self.profile
        self.sidebar_profile_name.setText(profile.get("name", "Player"))
        self.sidebar_profile_detail.setText(
            f"level {self.engine.highest_completed(profile)}  -  "
            f"{self.engine.total_stars(profile)} stars")

    # ---------------------------------------------------------------- profiles
    @property
    def profile(self) -> dict:
        return self._profile

    @property
    def profiles(self) -> list[dict]:
        return self.profile_headers

    def switch_profile(self, profile_id: str) -> None:
        profile = self.storage.load_profile(profile_id)
        if not profile:
            return
        self._profile = profile
        self.settings["current_profile"] = profile_id
        self.save_settings()
        self.refresh_all()
        self.statusBar().showMessage(f"Switched to {profile.get('name', 'Player')}")

    def create_profile(self, name: str) -> None:
        profile = self.storage.create_profile(name)
        self._profile = profile
        self.settings["current_profile"] = profile["id"]
        self.save_settings()
        self.refresh_all()

    def delete_profile(self, profile_id: str) -> None:
        self.storage.delete_profile(profile_id)
        self.reload_profiles()
        self.refresh_all()

    def reload_profiles(self) -> None:
        """Re-read profiles from disk (after import/reset/delete)."""
        self.profile_headers = self.storage.load_profiles()
        if not self.profile_headers:
            self.storage.create_profile("Player")
            self.profile_headers = self.storage.load_profiles()
        current_id = self._profile.get("id")
        if current_id not in {h.get("id") for h in self.profile_headers}:
            self._profile = self._load_current_profile()
        else:
            self._profile = self.storage.load_profile(current_id) or self._load_current_profile()
        self.settings["current_profile"] = self._profile.get("id")
        self.save_settings()

    # ---------------------------------------------------------------- settings
    def save_settings(self) -> None:
        self.storage.save_settings(self.settings)

    def apply_settings(self) -> None:
        """Apply theme, fonts and sound to the whole app."""
        theme_name = self.settings.get("theme", "dark")
        size = int(self.settings.get("font_size", 16))
        app = QApplication.instance()
        app.typeflow_theme = theme_name            # read by custom painters
        theme.apply_theme(app, theme_name, max(9, size - 4))
        self.sound.set_enabled(bool(self.settings.get("sound", True)))
        self.sound.set_volume(int(self.settings.get("volume", 60)))
        self.refresh_all()

    # ------------------------------------------------------------------ levels
    def open_level(self, level: int) -> None:
        """Open a level for practice (locked levels are refused)."""
        level = int(level)
        if not self.engine.is_unlocked(level, self.profile):
            from .ui.widgets import message
            message(self, "Level locked",
                    f"Level {level} is still locked.\nFinish level {level - 1} to unlock it.")
            return
        self._last_level = level
        self.typing_page.start_level(level)
        self.stack.setCurrentWidget(self.typing_page)
        self.statusBar().showMessage(f"Level {level}  -  {self.engine.spec(level)['title']}")
        self.typing_page.setFocus()

    def _abandon_level(self) -> None:
        """Leave a lesson without saving it."""
        self.typing_page.stop()
        self.navigate("levels")

    def _open_next_level(self) -> None:
        """Continue with the level after the one that was just finished."""
        finished = self.results_page.level
        if finished >= config.TOTAL_LEVELS:
            self.navigate("home")            # campaign complete
            return
        following = finished + 1
        if self.engine.is_unlocked(following, self.profile):
            self.open_level(following)
        else:
            self.open_level(self.engine.next_level(self.profile))

    def on_level_finished(self, level: int, result: TypingResult) -> None:
        """Save the result of a finished lesson and show the results screen."""
        profile = self.profile
        passed = self.engine.passed(level, result.wpm, result.accuracy)
        valid = stats_mod.is_valid_result(result.wpm, result.accuracy)
        stars = self.engine.stars(level, result.wpm, result.accuracy) if valid else 0

        record = profile["levels"].setdefault(str(level), {
            "best_wpm": 0.0, "best_acc": 0.0, "stars": 0, "attempts": 0,
            "completed": False, "completed_at": "", "history": [],
        })
        previous_best = float(record.get("best_wpm", 0.0) or 0.0)
        is_new_best = valid and result.wpm > previous_best
        record["attempts"] = int(record.get("attempts", 0)) + 1

        stats = profile["stats"]
        stats["sessions"] = int(stats.get("sessions", 0)) + 1
        stats["total_time_sec"] = float(stats.get("total_time_sec", 0.0)) + result.duration
        stats["total_correct"] = int(stats.get("total_correct", 0)) + result.correct
        stats["total_typed"] = int(stats.get("total_typed", 0)) + result.typed
        today = _today()
        if today not in stats.setdefault("practice_dates", []):
            stats["practice_dates"].append(today)

        # Weak keys / words are real observations, so they are always kept.
        for key, key_stats in result.weak_keys.items():
            entry = stats["weak_keys"].setdefault(key, {"errors": 0, "typed": 0})
            entry["errors"] += int(key_stats.get("errors", 0))
            entry["typed"] += int(key_stats.get("typed", 0))
        for word, count in result.weak_words.items():
            stats["weak_words"][word] = int(stats["weak_words"].get(word, 0)) + int(count)

        unlocked_next = None
        if valid:
            record["best_wpm"] = max(previous_best, result.wpm)
            record["best_acc"] = max(float(record.get("best_acc", 0.0) or 0.0), result.accuracy)
            if passed and not record.get("completed"):
                record["completed"] = True
                record["completed_at"] = _now()
                unlocked_next = level + 1 if level < config.TOTAL_LEVELS else None
            if record.get("completed"):
                unlocked_next = unlocked_next or (level + 1 if level < config.TOTAL_LEVELS else None)
            record["stars"] = max(int(record.get("stars", 0) or 0), stars)
            record.setdefault("history", []).append({
                "date": _now(), "wpm": round(result.wpm, 1), "acc": round(result.accuracy, 1),
                "stars": stars,
            })
            stats["history"].append({
                "date": _now(), "level": level, "wpm": round(result.wpm, 1),
                "acc": round(result.accuracy, 1), "stars": stars,
                "duration": round(result.duration, 1),
            })
            # Keep the saved history a sane size.
            stats["history"] = stats["history"][-500:]
            record["history"] = record["history"][-50:]

        profile["last_played"] = _now()
        self.storage.save_profile(profile)
        self.refresh_all()

        self.results_page.show_result(level, result, passed, stars, unlocked_next,
                                      is_new_best, valid)
        self.stack.setCurrentWidget(self.results_page)

    # ------------------------------------------------------------------ events
    def closeEvent(self, event) -> None:
        """Remember window geometry and the current profile."""
        self.settings["window_geometry"] = {
            "width": self.width(), "height": self.height(),
            "maximized": self.isMaximized(),
        }
        self.settings["current_profile"] = self._profile.get("id")
        self.save_settings()
        super().closeEvent(event)


def theme_nav_button(text: str):
    """QPushButton styled as a sidebar entry."""
    from PyQt6.QtWidgets import QPushButton
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    return button


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.APP_NAME)
    app.typeflow_theme = "dark"

    settings = Storage().load_settings()
    theme.apply_theme(app, settings.get("theme", "dark"),
                      max(9, int(settings.get("font_size", 16)) - 4))
    app.typeflow_theme = settings.get("theme", "dark")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
