"""Settings page: theme, sound, font size, keyboard guide, data location,
progress reset and an about box."""
from __future__ import annotations

import os
import subprocess
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from .. import config
from . import theme
from .widgets import Card, DangerButton, GhostButton, SectionTitle, confirm, message


class SettingsPage(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self._loading = False          # guards against saving while loading
        self._build()
        self.load_settings()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)
        layout.addWidget(SectionTitle("Settings"))

        # -- appearance -------------------------------------------------------
        appearance = Card("Appearance")
        self.theme_dark = QCheckBox("Dark theme (light theme is also available)")
        self.theme_dark.clicked.connect(self._save)
        appearance.add_widget(self.theme_dark)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font size"))
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(11, 24)
        self.font_slider.setTickInterval(1)
        self.font_slider.valueChanged.connect(self._font_changed)
        font_row.addWidget(self.font_slider, 1)
        self.font_value = QLabel("16 pt")
        font_row.addWidget(self.font_value)
        appearance.add_layout(font_row)
        self.font_preview = QLabel("The quick brown fox jumps over the lazy dog. 0123456789")
        self.font_preview.setObjectName("dim")
        appearance.add_widget(self.font_preview)
        layout.addWidget(appearance)

        # -- typing ------------------------------------------------------------
        typing = Card("Typing")
        self.sound_check = QCheckBox("Sound effects (key clicks, errors, level complete)")
        self.sound_check.clicked.connect(self._save)
        typing.add_widget(self.sound_check)
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(self._save)
        volume_row.addWidget(self.volume_slider, 1)
        self.volume_value = QLabel("60%")
        volume_row.addWidget(self.volume_value)
        typing.add_layout(volume_row)
        self.guide_check = QCheckBox("Show the on-screen keyboard guide (turn off for a challenge)")
        self.guide_check.clicked.connect(self._save)
        typing.add_widget(self.guide_check)
        layout.addWidget(typing)

        # -- data ----------------------------------------------------------------
        data = Card("Data - stored only on this computer")
        self.data_label = QLabel(str(config.DATA_DIR))
        self.data_label.setObjectName("dim")
        self.data_label.setWordWrap(True)
        data.add_widget(self.data_label)
        open_button = GhostButton("Open data folder")
        open_button.clicked.connect(self._open_data_folder)
        data.add_widget(open_button)
        layout.addWidget(data)

        # -- danger zone ------------------------------------------------------------
        danger = Card("Reset")
        reset_button = DangerButton("Reset my progress")
        reset_button.clicked.connect(self._reset_progress)
        danger.add_widget(reset_button)
        reset_note = QLabel("Clears every level, star and statistic for the current profile. "
                            "The profile itself is kept.")
        reset_note.setObjectName("dim")
        reset_note.setWordWrap(True)
        danger.add_widget(reset_note)
        layout.addWidget(danger)

        # -- about ----------------------------------------------------------------------
        about = Card("About")
        about_text = QLabel(
            f"{config.APP_NAME} {config.APP_VERSION}\n{config.APP_DESCRIPTION}\n\n"
            "100% offline: no accounts, no internet connection, no analytics. "
            "Everything is stored as JSON in the folder above.")
        about_text.setWordWrap(True)
        about.add_widget(about_text)
        layout.addWidget(about)

        layout.addStretch(1)

    # -- settings I/O -------------------------------------------------------------------
    def load_settings(self) -> None:
        """Copy the stored settings into the widgets (without saving back)."""
        settings = self.controller.settings
        self._loading = True
        try:
            self.theme_dark.setChecked(settings.get("theme", "dark") == "dark")
            self.sound_check.setChecked(bool(settings.get("sound", True)))
            volume = int(settings.get("volume", 60))
            self.volume_slider.setValue(volume)
            self.volume_value.setText(f"{volume}%")
            self.guide_check.setChecked(bool(settings.get("keyboard_guide", True)))
            size = int(settings.get("font_size", 16))
            self.font_slider.setValue(size)
            self.font_value.setText(f"{size} pt")
        finally:
            self._loading = False
        self.font_preview.setFont(theme.mono_font(size))
        self.font_preview.setText(
            f"The quick brown fox jumps over the lazy dog. 0123456789\n"
            f"Levels 1-100  -  {config.TOTAL_LEVELS} lessons, 300 stars to collect")

    def _font_changed(self, value: int) -> None:
        self.font_value.setText(f"{value} pt")
        self.font_preview.setFont(theme.mono_font(value))
        self._save()

    def _save(self) -> None:
        if self._loading:
            return                      # do not write while widgets are being filled
        settings = self.controller.settings
        settings["theme"] = "dark" if self.theme_dark.isChecked() else "light"
        settings["sound"] = self.sound_check.isChecked()
        settings["volume"] = self.volume_slider.value()
        settings["keyboard_guide"] = self.guide_check.isChecked()
        settings["font_size"] = self.font_slider.value()
        self.controller.save_settings()
        self.settings_changed.emit()

    # -- actions ---------------------------------------------------------------------
    def _open_data_folder(self) -> None:
        path = config.DATA_DIR
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))            # noqa: S606 (Windows only)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as error:
            message(self, "Could not open folder", f"{path}\n\n{error}")

    def _reset_progress(self) -> None:
        profile = self.controller.profile
        if not confirm(self, "Reset progress?",
                       f"This erases all levels, stars and statistics for "
                       f"'{profile.get('name')}'. This cannot be undone.",
                       ok_text="Reset progress", danger=True):
            return
        self.controller.storage.reset_profile(profile["id"], profile.get("name"))
        self.controller.reload_profiles()
        message(self, "Progress reset", "You are back at level 1. Have fun!")
