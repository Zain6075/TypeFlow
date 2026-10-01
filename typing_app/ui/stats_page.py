"""Stats dashboard: charts, streaks, practice time and the weakest keys."""
from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import config, stats as stats_mod
from . import theme
from .charts import BarList, LineChart
from .widgets import Card, StatCard


class StatsPage(QWidget):
    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        # -- headline numbers -------------------------------------------------
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.time_card = StatCard("Practice", "0m")
        self.sessions_card = StatCard("Sessions", "0")
        self.streak_card = StatCard("Streak", "0 days")
        self.longest_card = StatCard("Best streak", "0 days")
        self.avg_card = StatCard("Avg WPM", "-")
        self.best_card = StatCard("Best WPM", "-")
        self.accuracy_card = StatCard("Avg accuracy", "-")
        for card in (self.time_card, self.sessions_card, self.streak_card, self.longest_card,
                     self.avg_card, self.best_card, self.accuracy_card):
            cards.addWidget(card)
        layout.addLayout(cards)

        # -- charts -------------------------------------------------------------
        charts = QHBoxLayout()
        charts.setSpacing(12)
        self.wpm_chart = LineChart("Speed over time (WPM)")
        self.accuracy_chart = LineChart("Accuracy over time (%)")
        charts.addWidget(self.wpm_chart)
        charts.addWidget(self.accuracy_chart)
        layout.addLayout(charts, 1)

        # -- weak keys & practice days -------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        weak_card = Card("Weakest keys")
        weak_note = QLabel("Error rate per key - these keys are folded back into your lessons "
                           "automatically.")
        weak_note.setObjectName("dim")
        weak_note.setWordWrap(True)
        weak_card.add_widget(weak_note)
        self.weak_chart = BarList()
        weak_card.add_widget(self.weak_chart)
        bottom.addWidget(weak_card, 2)

        days_card = Card("Practice minutes - last 14 days")
        self.days_chart = BarList()
        days_card.add_widget(self.days_chart)
        bottom.addWidget(days_card, 3)
        layout.addLayout(bottom, 1)

        self.summary = QLabel("")
        self.summary.setObjectName("dim")
        layout.addWidget(self.summary)

    # -- data ------------------------------------------------------------------------
    def refresh(self) -> None:
        profile = self.controller.profile
        engine = self.controller.engine
        pal = theme.palette(_theme())

        seconds = stats_mod.total_practice_seconds(profile)
        self.time_card.set_value(stats_mod.format_duration(seconds),
                                 f"{seconds / 3600:.1f} hours total")
        self.sessions_card.set_value(str(stats_mod.session_count(profile)),
                                     "lessons finished")
        streak = stats_mod.current_streak(profile)
        self.streak_card.set_value(f"{streak} day{'s' if streak != 1 else ''}", "keep it going!")
        self.longest_card.set_value(f"{stats_mod.longest_streak(profile)} days", "personal record")
        self.avg_card.set_value(f"{stats_mod.average_wpm(profile):.0f}", "mean of valid runs")
        self.best_card.set_value(f"{stats_mod.best_wpm(profile):.0f}", "fastest level",
                                 accent=pal["accent"])
        self.accuracy_card.set_value(f"{stats_mod.average_accuracy(profile):.1f}%",
                                     f"overall {stats_mod.overall_accuracy(profile):.1f}%")

        # Charts: one point per recorded session.
        history = stats_mod.wpm_accuracy_series(profile)
        wpm_points = [(index, entry["wpm"], str(entry.get("date", ""))[:10])
                      for index, entry in enumerate(history)]
        accuracy_points = [(index, entry["acc"], str(entry.get("date", ""))[:10])
                           for index, entry in enumerate(history)]
        self.wpm_chart.set_data(
            [{"name": "WPM", "color": pal["chart_line"], "points": wpm_points}],
            y_min=0, y_max=max(40.0, max((p[1] for p in wpm_points), default=40.0) * 1.15))
        self.accuracy_chart.set_data(
            [{"name": "Accuracy", "color": pal["chart_line2"], "points": accuracy_points}],
            y_min=60, y_max=100, y_suffix="%")

        # Weakest keys.
        weak = stats_mod.weakest_keys(profile, limit=8)
        worst = weak[0]["rate"] if weak else 1.0
        self.weak_chart.set_rows(
            [(row["key"], row["rate"] / max(worst, 1.0),
              f"{row['rate']:.1f}% ({row['errors']}/{row['typed']})") for row in weak],
            color=pal["red"])

        # Practice minutes for the last 14 days.
        per_day = stats_mod.practice_by_day(profile)
        days = sorted(per_day.keys())[-14:]
        peak = max((per_day[d] for d in days), default=1.0)
        self.days_chart.set_rows(
            [(d[5:], per_day[d] / max(peak, 0.1), f"{per_day[d]:.0f} min") for d in days],
            color=pal["accent"])

        highest = engine.highest_completed(profile)
        stars = engine.total_stars(profile)
        self.summary.setText(
            f"{highest} of {config.TOTAL_LEVELS} levels completed  -  {stars} / 300 stars  -  "
            f"{stats_mod.format_duration(seconds)} of practice across "
            f"{stats_mod.session_count(profile)} sessions.")


def _theme() -> str:
    """Current theme name (stored on the QApplication by the main window)."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
