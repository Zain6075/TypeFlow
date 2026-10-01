"""Profiles page: create, switch, export, import and delete local profiles."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import stats as stats_mod
from .widgets import (
    Card, DangerButton, GhostButton, PrimaryButton, SectionTitle, confirm, message, prompt_text,
)


class ProfilesPage(QWidget):
    profiles_changed = pyqtSignal()

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.addWidget(SectionTitle("Profiles"))
        header.addStretch(1)
        new_button = PrimaryButton("New profile")
        new_button.clicked.connect(self._create_profile)
        header.addWidget(new_button)
        layout.addLayout(header)

        intro = QLabel("Every profile on this computer has its own levels, stars and statistics. "
                       "Switch profiles from the home page.")
        intro.setObjectName("dim")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Level", "Stars", "Best WPM", "Created", "Last played"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        # -- export / import ---------------------------------------------------
        card = Card("Backup")
        row = QHBoxLayout()
        export_button = GhostButton("Export this profile")
        export_button.clicked.connect(self._export_profile)
        import_button = GhostButton("Import a profile")
        import_button.clicked.connect(self._import_profile)
        row.addWidget(export_button)
        row.addWidget(import_button)
        row.addStretch(1)
        card.add_layout(row)
        note = QLabel("Exports are plain JSON files you can copy to another computer and "
                      "import there.")
        note.setObjectName("dim")
        card.add_widget(note)
        layout.addWidget(card)

        # -- danger --------------------------------------------------------------
        danger = Card("Delete")
        delete_button = DangerButton("Delete current profile")
        delete_button.clicked.connect(self._delete_profile)
        danger.add_widget(delete_button)
        danger_note = QLabel("Deleting removes the profile and all of its progress from this "
                             "computer. Export first if you want a backup.")
        danger_note.setObjectName("dim")
        danger_note.setWordWrap(True)
        danger.add_widget(danger_note)
        layout.addWidget(danger)

    # -- data -------------------------------------------------------------------------
    def refresh(self) -> None:
        records = self.controller.storage.all_profile_records()
        current_id = self.controller.profile.get("id")
        self.table.setRowCount(len(records))
        for row, profile in enumerate(records):
            is_current = profile.get("id") == current_id
            values = [
                profile.get("name", "Player") + ("  (current)" if is_current else ""),
                str(stats_mod.best_level(profile)),
                f"{sum(int(r.get('stars', 0)) for r in profile.get('levels', {}).values())} / 300",
                f"{stats_mod.best_wpm(profile):.0f}",
                str(profile.get("created", ""))[:10],
                stats_mod.relative_day(profile.get("last_played", "")),
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if column else
                                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if is_current:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)

    # -- actions ------------------------------------------------------------------------
    def _create_profile(self) -> None:
        name = prompt_text(self, "New profile", "Profile name:", "Player", ok_text="Create")
        if not name:
            return
        self.controller.create_profile(name)
        self.profiles_changed.emit()
        message(self, "Profile created", f"'{name}' starts at level 1.")

    def _delete_profile(self) -> None:
        profile = self.controller.profile
        if not confirm(self, "Delete profile?",
                       f"'{profile.get('name')}' and all of its progress will be removed from "
                       "this computer. This cannot be undone.",
                       ok_text="Delete profile", danger=True):
            return
        self.controller.delete_profile(profile["id"])
        self.profiles_changed.emit()

    def _export_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export profile", str(Path.home() / f"typeflow-{self.controller.profile['name']}.json"),
            "JSON files (*.json)")
        if not path:
            return
        try:
            self.controller.storage.export_profile(self.controller.profile["id"], Path(path))
            message(self, "Export complete", f"Profile saved to:\n{path}")
        except OSError as error:
            message(self, "Export failed", str(error))

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import profile", str(Path.home()), "JSON files (*.json)")
        if not path:
            return
        try:
            profile = self.controller.storage.import_profile(Path(path))
        except (OSError, ValueError) as error:
            message(self, "Import failed", str(error))
            return
        self.controller.reload_profiles()
        self.profiles_changed.emit()
        message(self, "Import complete",
                f"Profile '{profile.get('name')}' was added. Switch to it from the home page.")
