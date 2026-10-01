#!/usr/bin/env python3
"""Capture screenshots of every screen for the README.

    QT_QPA_PLATFORM=offscreen python tools/capture_screenshots.py

The script builds a throw-away profile with some demo progress, walks through
the app and writes PNGs into ``docs/screenshots/``.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["TYPEFLOW_DATA_DIR"] = tempfile.mkdtemp(prefix="typeflow-shots-")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtWidgets import QApplication  # noqa: E402

from typing_app.app import MainWindow     # noqa: E402
from typing_app.storage import Storage    # noqa: E402


def demo_progress(window: MainWindow) -> None:
    """Give the current profile believable progress for the screenshots."""
    profile = window.profile
    plan = [(1, 3, 34.0, 97.0), (2, 3, 31.0, 95.0), (3, 2, 29.0, 92.0), (4, 3, 36.0, 98.0),
            (5, 2, 33.0, 91.0), (6, 3, 38.0, 96.0), (7, 2, 30.0, 89.0), (8, 3, 41.0, 97.0),
            (9, 2, 27.0, 88.0), (10, 3, 44.0, 96.0), (11, 3, 46.0, 98.0), (12, 2, 39.0, 93.0),
            (13, 3, 52.0, 97.0), (14, 3, 55.0, 99.0), (15, 2, 48.0, 90.0)]
    for level, stars, wpm, accuracy in plan:
        profile["levels"][str(level)] = {
            "best_wpm": wpm, "best_acc": accuracy, "stars": stars, "attempts": 2,
            "completed": True, "completed_at": "2026-09-2%sT10:00:00" % (level % 10),
            "history": [],
        }
    stats = profile["stats"]
    stats["sessions"] = 42
    stats["total_time_sec"] = 5 * 3600 + 37 * 60
    stats["total_correct"] = 9800
    stats["total_typed"] = 10350
    stats["practice_dates"] = ["2026-09-2%d" % d for d in range(17, 28)] + \
                              ["2026-09-29", "2026-09-30", "2026-10-01"]
    stats["weak_keys"] = {"k": {"errors": 14, "typed": 120}, "p": {"errors": 9, "typed": 95},
                          "b": {"errors": 7, "typed": 60}, ";": {"errors": 5, "typed": 40},
                          "y": {"errors": 4, "typed": 80}}
    stats["weak_words"] = {"the": 6, "because": 4, "which": 3}
    for index, (level, _stars, wpm, accuracy) in enumerate(plan):
        stats["history"].append({
            "date": f"2026-09-{17 + index:02d}T10:00:00", "level": level, "wpm": wpm,
            "acc": accuracy, "stars": _stars, "duration": 180.0 + index * 7,
        })
    window.storage.save_profile(profile)
    window.refresh_all()


def main() -> None:
    app = QApplication(sys.argv[:1])
    app.typeflow_theme = "dark"
    window = MainWindow(storage=Storage(Path(os.environ["TYPEFLOW_DATA_DIR"])))
    window.resize(1240, 860)
    window.show()
    app.processEvents()

    demo_progress(window)

    # A second profile so the leaderboard has something to rank.
    rival = window.storage.create_profile("Ayesha")
    rival["levels"] = {str(level): {"completed": True, "stars": 3, "best_wpm": 61.0,
                                    "best_acc": 94.0, "attempts": 1}
                       for level in range(1, 19)}
    rival["last_played"] = "2026-09-30T18:20:00"
    window.storage.save_profile(rival)
    window.refresh_all()

    shots = {
        "home": lambda: window.navigate("home"),
        "levels": lambda: window.navigate("levels"),
        "typing": lambda: _typing_shot(window),
        "results": lambda: _results_shot(window),
        "leaderboard": lambda: window.navigate("leaderboard"),
        "stats": lambda: window.navigate("stats"),
        "settings": lambda: window.navigate("settings"),
        "profiles": lambda: window.navigate("profiles"),
    }
    for name, action in shots.items():
        action()
        for _ in range(6):
            app.processEvents()
        window.repaint()
        app.processEvents()
        window.grab().save(str(OUT / f"{name}.png"))
        print(f"saved {name}.png")

    # Light theme variant of the home screen.
    window.settings["theme"] = "light"
    window.apply_settings()
    window.navigate("home")
    for _ in range(6):
        app.processEvents()
    window.grab().save(str(OUT / "home-light.png"))
    print("saved home-light.png")


def _typing_shot(window: MainWindow) -> None:
    """Open a level and type a few characters so colours and keys are visible."""
    window.open_level(16)
    page = window.typing_page
    for char in page.engine.text[:26]:
        page._press(char)
    page._press("\\")                      # one deliberate mistake (shown red)
    page._press(" ")
    window.repaint()


def _results_shot(window: MainWindow) -> None:
    """Finish level 1 with a believable speed so the pass screen can be shown."""
    window.open_level(1)
    page = window.typing_page

    class Clock:
        t = 500.0

        def __call__(self):
            return self.t

    clock = Clock()
    page.engine._clock = clock
    for char in page.engine.text:
        clock.t += 0.12                      # ~90 WPM
        page._press(char)
    window.on_level_finished(1, page.engine.result())


if __name__ == "__main__":
    main()
