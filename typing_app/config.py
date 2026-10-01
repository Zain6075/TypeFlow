"""TypeFlow - offline typing practice app.

Application-wide configuration: filesystem paths, tunable constants and
default settings.  Everything the app writes stays inside the per-user
application-data directory; nothing is ever sent over the network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
APP_NAME = "TypeFlow"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Offline typing trainer with 100 levels, profiles and stats."

# ---------------------------------------------------------------------------
# Gameplay constants
# ---------------------------------------------------------------------------
TOTAL_LEVELS = 100                 # number of levels in the campaign
FINAL_TEST_LEVELS = (25, 50, 75, 100)   # "final test" levels that mix everything
PASS_ACCURACY = 80.0               # minimum accuracy (%) required to unlock next level
BASE_MIN_WPM = 8.0                 # minimum WPM for levels 1-10
WPM_STEP_PER_TEN = 2.0             # min WPM rises by this much every 10 levels
STAR2_WPM_BONUS = 5.0              # extra WPM needed for the 2nd star
STAR2_ACCURACY = 90.0              # accuracy needed for the 2nd star
STAR3_WPM_BONUS = 10.0             # extra WPM needed for the 3rd star
STAR3_ACCURACY = 96.0              # accuracy needed for the 3rd star
MAX_PLAUSIBLE_WPM = 300.0          # results above this are considered impossible / invalid

# Fraction of every lesson that is recycled material (spaced repetition).
REVIEW_FRACTION = 0.30

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _data_dir() -> Path:
    """Per-user writable data directory.

    Windows : %APPDATA%\\TypeFlow          (e.g. C:\\Users\\me\\AppData\\Roaming\\TypeFlow)
    macOS   : ~/Library/Application Support/TypeFlow
    Linux   : ~/.local/share/TypeFlow

    The environment variable ``TYPEFLOW_DATA_DIR`` overrides everything, which
    the test-suite uses to run against a throw-away directory.
    """
    override = os.environ.get("TYPEFLOW_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = _data_dir()

SETTINGS_FILE = "settings.json"          # global app settings (theme, sound, ...)
PROFILES_FILE = "profiles.json"          # index of local profiles
LESSONS_FILE = "lessons.json"            # lesson content (ships inside the package)


def lessons_path() -> Path:
    """Location of lessons.json.

    When frozen with PyInstaller the bundled data lives under ``sys._MEIPASS``;
    during development it is a package sub-directory.
    """
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        candidate = Path(frozen) / "typing_app" / "data" / LESSONS_FILE
        if candidate.exists():
            return candidate
        return Path(frozen) / LESSONS_FILE
    return Path(__file__).resolve().parent / "data" / LESSONS_FILE


def profile_file(profile_id: str) -> Path:
    """File name that stores one profile's progress and statistics."""
    return DATA_DIR / f"profile_{profile_id}.json"


def sounds_dir() -> Path:
    """Directory for the tiny synthesised WAV files (created on first run)."""
    path = DATA_DIR / "sounds"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "theme": "dark",             # "dark" | "light"
    "sound": True,               # key click / error / success sounds
    "volume": 60,                # 0-100
    "font_size": 16,             # base UI font size in points
    "keyboard_guide": True,      # show the on-screen keyboard by default
}
