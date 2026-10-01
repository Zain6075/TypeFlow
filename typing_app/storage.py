"""Local JSON storage for settings, profiles and per-profile progress.

Design notes
------------
* 100 % offline: plain JSON files inside the per-user app-data directory.
* Every write is **atomic** (write to a temporary file, then ``os.replace``)
  so an unexpected crash can never truncate a save file.
* A "profile" bundles the player's name, per-level records and statistics.
  Each profile is its own file (``profile_<id>.json``) so exporting, importing
  or deleting one player never touches anybody else's data.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config


# ---------------------------------------------------------------------------
# Low-level JSON helpers
# ---------------------------------------------------------------------------
def _atomic_write_json(path: Path, data: Any) -> None:
    """Write ``data`` as pretty JSON to ``path`` atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)  # atomic on POSIX and Windows
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _read_json(path: Path, default: Any) -> Any:
    """Read JSON from ``path`` returning ``default`` if missing or corrupt."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().date().isoformat()


# ---------------------------------------------------------------------------
# Blank records
# ---------------------------------------------------------------------------
def new_profile(name: str) -> dict:
    """Return a fresh profile record with empty progress and statistics."""
    return {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip() or "Player",
        "created": _now_iso(),
        "last_played": _now_iso(),
        "levels": {},          # "1" -> {best_wpm, best_acc, stars, attempts, completed_at, history[]}
        "stats": {
            "sessions": 0,
            "total_time_sec": 0.0,
            "total_correct": 0,
            "total_typed": 0,
            "practice_dates": [],   # ["2026-10-01", ...] one entry per day played
            "weak_keys": {},        # "a" -> {"errors": int, "typed": int}
            "weak_words": {},       # "the" -> error count
            "history": [],          # [{date, level, wpm, acc, stars, duration}]
        },
    }


# ---------------------------------------------------------------------------
# Storage facade
# ---------------------------------------------------------------------------
class Storage:
    """Reads and writes every piece of local app data."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else config.DATA_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    # -- settings -----------------------------------------------------------
    def load_settings(self) -> dict:
        settings = dict(config.DEFAULT_SETTINGS)
        settings.update(_read_json(self.root / config.SETTINGS_FILE, {}))
        return settings

    def save_settings(self, settings: dict) -> None:
        _atomic_write_json(self.root / config.SETTINGS_FILE, settings)

    # -- profile index ------------------------------------------------------
    def load_profiles(self) -> list[dict]:
        """Return the list of profile *headers* (id, name, created, ...)."""
        data = _read_json(self.root / config.PROFILES_FILE, {"profiles": []})
        return list(data.get("profiles", []))

    def save_profiles(self, profiles: list[dict]) -> None:
        _atomic_write_json(self.root / config.PROFILES_FILE, {"profiles": profiles})

    # -- individual profiles -------------------------------------------------
    def load_profile(self, profile_id: str) -> dict | None:
        profile = _read_json(self.root / f"profile_{profile_id}.json", None)
        if profile is None:
            return None
        # Make sure older/partial records still contain every expected key.
        template = new_profile(profile.get("name", "Player"))
        template.update(profile)
        template["stats"] = {**new_profile("x")["stats"], **profile.get("stats", {})}
        return template

    def save_profile(self, profile: dict) -> None:
        _atomic_write_json(self._profile_path(profile["id"]), profile)

    def delete_profile(self, profile_id: str) -> None:
        try:
            self._profile_path(profile_id).unlink()
        except OSError:
            pass
        self.save_profiles([p for p in self.load_profiles() if p.get("id") != profile_id])

    def create_profile(self, name: str) -> dict:
        """Create, persist and return a new profile."""
        profile = new_profile(name)
        profiles = self.load_profiles()
        profiles.append({"id": profile["id"], "name": profile["name"], "created": profile["created"]})
        self.save_profiles(profiles)
        self.save_profile(profile)
        return profile

    # -- export / import ------------------------------------------------------
    def export_profile(self, profile_id: str, target: Path) -> Path:
        """Copy one profile to ``target`` (a user-chosen JSON file)."""
        profile = self.load_profile(profile_id)
        if profile is None:
            raise FileNotFoundError(f"No profile with id {profile_id!r}")
        payload = {
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "kind": "profile",
            "exported": _now_iso(),
            "profile": profile,
        }
        _atomic_write_json(Path(target), payload)
        return Path(target)

    def import_profile(self, source: Path) -> dict:
        """Import a profile JSON file; returns the imported profile."""
        payload = _read_json(Path(source), None)
        if not isinstance(payload, dict) or "profile" not in payload:
            raise ValueError("Not a TypeFlow profile export file")
        profile = payload["profile"]
        if not profile.get("id") or not profile.get("name"):
            raise ValueError("Profile export is missing id/name")
        # Avoid clobbering an existing profile with the same id.
        existing = {p.get("id") for p in self.load_profiles()}
        if profile["id"] in existing:
            profile["id"] = uuid.uuid4().hex[:12]
        profile.setdefault("created", _now_iso())
        profile["last_played"] = _now_iso()
        profiles = self.load_profiles()
        profiles.append({"id": profile["id"], "name": profile["name"], "created": profile["created"]})
        self.save_profiles(profiles)
        self.save_profile(profile)
        return profile

    def export_all(self, target: Path) -> Path:
        """Export every profile + settings into a single backup file."""
        payload = {
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "kind": "full-backup",
            "exported": _now_iso(),
            "settings": self.load_settings(),
            "profiles": [self.load_profile(p["id"]) for p in self.load_profiles()],
        }
        _atomic_write_json(Path(target), payload)
        return Path(target)

    def import_all(self, source: Path) -> list[dict]:
        """Import a full backup; returns the imported profiles."""
        payload = _read_json(Path(source), None)
        if not isinstance(payload, dict) or payload.get("kind") != "full-backup":
            raise ValueError("Not a TypeFlow full-backup file")
        imported = []
        for profile in payload.get("profiles", []):
            if profile and profile.get("id"):
                if any(p.get("id") == profile["id"] for p in self.load_profiles()):
                    profile["id"] = uuid.uuid4().hex[:12]
                profiles = self.load_profiles()
                profiles.append({"id": profile["id"], "name": profile.get("name", "Player"),
                                 "created": profile.get("created", _now_iso())})
                self.save_profiles(profiles)
                self.save_profile(profile)
                imported.append(profile)
        if "settings" in payload:
            self.save_settings(payload["settings"])
        return imported

    # -- reset ----------------------------------------------------------------
    def reset_profile(self, profile_id: str, name: str | None = None) -> dict:
        """Wipe one profile's progress/stats, keeping its identity."""
        profiles = self.load_profiles()
        header = next((p for p in profiles if p.get("id") == profile_id), None)
        fresh = new_profile(name or (header or {}).get("name") or "Player")
        fresh["id"] = profile_id
        fresh["created"] = (header or {}).get("created", _now_iso())
        self.save_profile(fresh)
        return fresh

    # -- misc ------------------------------------------------------------------
    def all_profile_records(self) -> list[dict]:
        """Load every profile's full record (used by the leaderboard)."""
        return [p for p in (self.load_profile(h["id"]) for h in self.load_profiles()) if p]

    def _profile_path(self, profile_id: str) -> Path:
        return self.root / f"profile_{profile_id}.json"
