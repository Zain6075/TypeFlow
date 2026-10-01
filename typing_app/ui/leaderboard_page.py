"""Local leaderboard: ranks every profile on this PC.

Four ranking tabs (level, best WPM, best accuracy, stars), gold/silver/bronze
highlighting for the top three, a per-level personal-best history, export and
import of progress, and resets with confirmation.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .. import leaderboard, stats as stats_mod
from . import theme
from .widgets import Card, DangerButton, GhostButton, SectionTitle, confirm, message


class LeaderboardPage(QWidget):
    data_changed = pyqtSignal()      # after import / reset

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.metric = "level"
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = SectionTitle("Leaderboard")
        subtitle = QLabel("All profiles on this computer - no internet, no accounts.")
        subtitle.setObjectName("dim")
        header_column = QVBoxLayout()
        header_column.addWidget(title)
        header_column.addWidget(subtitle)
        header.addLayout(header_column)
        header.addStretch(1)
        export_button = GhostButton("Export JSON")
        export_button.clicked.connect(self._export)
        import_button = GhostButton("Import JSON")
        import_button.clicked.connect(self._import)
        reset_profile_button = DangerButton("Reset my profile")
        reset_profile_button.clicked.connect(self._reset_profile)
        reset_all_button = DangerButton("Reset everything")
        reset_all_button.clicked.connect(self._reset_all)
        for button in (export_button, import_button, reset_profile_button, reset_all_button):
            header.addWidget(button)
        layout.addLayout(header)

        # -- ranking tabs (one table per tab) ---------------------------------
        self.tabs = QTabWidget()
        self.tables: dict[str, QTableWidget] = {}
        for key, label, _entry_key in leaderboard.METRICS:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(8, 8, 8, 8)
            table = QTableWidget(0, 7)
            table.setHorizontalHeaderLabels(
                ["Rank", "Name", "Level", "Best WPM", "Best accuracy", "Stars", "Last played"])
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(1, 170)
            tab_layout.addWidget(table)
            self.tabs.addTab(tab, label)
            self.tables[key] = table
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs)

        # -- personal bests ---------------------------------------------------
        self.bests_card = Card("Personal bests - per level")
        self.bests_table = QTableWidget(0, 5)
        self.bests_table.setHorizontalHeaderLabels(
            ["Level", "Best WPM", "Accuracy", "Stars", "Completed"])
        self.bests_table.verticalHeader().setVisible(False)
        self.bests_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bests_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bests_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bests_table.setMaximumHeight(240)
        self.bests_card.add_widget(self.bests_table)
        layout.addWidget(self.bests_card)
        layout.addStretch(1)

    # -- data -----------------------------------------------------------------------
    def refresh(self) -> None:
        pal = theme.palette(_theme())
        profiles = self.controller.storage.all_profile_records()
        entries = leaderboard.build(profiles)
        current_id = self.controller.profile.get("id")

        # Fill every tab's table so switching tabs is instant.
        for metric, _label, _key in leaderboard.METRICS:
            self._fill_table(self.tables[metric], leaderboard.rank(entries, metric),
                             current_id, pal)


        # Personal best history for the current profile.
        bests = leaderboard.personal_bests(self.controller.profile)
        self.bests_table.setRowCount(len(bests))
        for row, best in enumerate(bests):
            cells = [
                str(best["level"]),
                f"{best['wpm']:.1f}",
                f"{best['accuracy']:.1f}%",
                "★" * best["stars"] + "☆" * (3 - best["stars"]),
                str(best["completed_at"])[:10],
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.bests_table.setItem(row, column, item)

    def _fill_table(self, table: QTableWidget, entries: list[dict], current_id: str,
                    pal: dict) -> None:
        """Render one ranked list into one of the tab tables."""
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            is_current = entry["id"] == current_id
            medal = leaderboard.medal(entry["rank"])
            rank_color = {"gold": pal["gold"], "silver": pal["silver"],
                          "bronze": pal["bronze"]}.get(medal, pal["text_dim"])
            rank_text = {1: "1st", 2: "2nd", 3: "3rd"}.get(entry["rank"], f"{entry['rank']}th")
            values = [
                (rank_text, rank_color, True),
                (entry["name"] + ("  (you)" if is_current else ""),
                 pal["accent"] if is_current else pal["text"], is_current),
                (str(entry["level"]), pal["text"], False),
                (f"{entry['best_wpm']:.0f}", pal["text"], False),
                (f"{entry['best_accuracy']:.1f}%", pal["text"], False),
                (f"{entry['stars']} / 300", pal["gold"], False),
                (stats_mod.relative_day(entry["last_played"]), pal["text_dim"], False),
            ]
            for column, (text, color, bold) in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter if column != 1
                    else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                item.setForeground(QColor(color))
                if bold:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if is_current:
                    item.setBackground(QColor(pal["surface_alt"]))
                table.setItem(row, column, item)

    # -- slots ----------------------------------------------------------------------
    def _tab_changed(self, index: int) -> None:
        self.metric = leaderboard.METRICS[index][0]
        self.refresh()

    # -- export / import -------------------------------------------------------------
    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export progress", str(Path.home() / "typeflow-progress.json"),
            "JSON files (*.json)")
        if not path:
            return
        try:
            self.controller.storage.export_all(Path(path))
            message(self, "Export complete",
                    f"All profiles and settings were saved to:\n{path}")
        except OSError as error:
            message(self, "Export failed", str(error))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import progress", str(Path.home()), "JSON files (*.json)")
        if not path:
            return
        try:
            imported = self.controller.storage.import_all(Path(path))
        except (OSError, ValueError) as error:
            message(self, "Import failed", str(error))
            return
        self.data_changed.emit()
        self.controller.reload_profiles()
        message(self, "Import complete",
                f"Imported {len(imported)} profile(s). Switch to them from the home page.")

    # -- resets -----------------------------------------------------------------------
    def _reset_profile(self) -> None:
        profile = self.controller.profile
        if not confirm(self, "Reset profile?",
                       f"This erases all progress and statistics for '{profile.get('name')}'.\n"
                       "The profile itself stays. This cannot be undone.",
                       ok_text="Reset profile", danger=True):
            return
        self.controller.storage.reset_profile(profile["id"], profile.get("name"))
        self.controller.reload_profiles()
        self.data_changed.emit()
        message(self, "Profile reset", "Your progress has been cleared. Good luck!")

    def _reset_all(self) -> None:
        if not confirm(self, "Reset everything?",
                       "This erases the progress and statistics of EVERY profile on this "
                       "computer, including the leaderboard. Profiles themselves stay.\n"
                       "This cannot be undone.",
                       ok_text="Reset everything", danger=True):
            return
        for header in self.controller.storage.load_profiles():
            self.controller.storage.reset_profile(header["id"], header.get("name"))
        self.controller.reload_profiles()
        self.data_changed.emit()
        message(self, "Leaderboard reset", "All profiles start from level 1 again.")


def _theme() -> str:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return getattr(app, "typeflow_theme", "dark") if app else "dark"
