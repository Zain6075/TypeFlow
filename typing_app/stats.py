"""Statistics helpers: everything derived from a profile's saved records.

Pure functions - no Qt, no I/O - so they can be unit-tested and reused by the
stats dashboard, the home page and the leaderboard.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def is_valid_result(wpm: float, accuracy: float) -> bool:
    """Reject impossible results (e.g. > 300 WPM or out-of-range accuracy)."""
    return 0.0 <= wpm <= config.MAX_PLAUSIBLE_WPM and 0.0 <= accuracy <= 100.0


# ---------------------------------------------------------------------------
# Basic aggregates
# ---------------------------------------------------------------------------
def overall_accuracy(profile: dict) -> float:
    stats = profile.get("stats", {})
    typed = int(stats.get("total_typed", 0))
    if typed <= 0:
        return 0.0
    return int(stats.get("total_correct", 0)) / typed * 100.0


def best_wpm(profile: dict) -> float:
    """Highest WPM ever recorded on a completed level (invalid results ignored)."""
    best = 0.0
    for record in profile.get("levels", {}).values():
        wpm = float(record.get("best_wpm", 0.0) or 0.0)
        acc = float(record.get("best_acc", 0.0) or 0.0)
        if record.get("completed") and is_valid_result(wpm, acc):
            best = max(best, wpm)
    return best


def best_level(profile: dict) -> int:
    """Highest level number that has been completed."""
    best = 0
    for key, record in profile.get("levels", {}).items():
        try:
            level = int(key)
        except (TypeError, ValueError):
            continue
        if record.get("completed"):
            best = max(best, level)
    return best


def best_accuracy(profile: dict) -> float:
    best = 0.0
    for record in profile.get("levels", {}).values():
        wpm = float(record.get("best_wpm", 0.0) or 0.0)
        acc = float(record.get("best_acc", 0.0) or 0.0)
        if record.get("completed") and is_valid_result(wpm, acc):
            best = max(best, acc)
    return best


def average_wpm(profile: dict) -> float:
    """Mean WPM over valid session history (one entry per completed level)."""
    values = [float(h.get("wpm", 0.0)) for h in _valid_history(profile)]
    return sum(values) / len(values) if values else 0.0


def average_accuracy(profile: dict) -> float:
    values = [float(h.get("acc", 0.0)) for h in _valid_history(profile)]
    return sum(values) / len(values) if values else 0.0


def total_practice_seconds(profile: dict) -> float:
    return float(profile.get("stats", {}).get("total_time_sec", 0.0) or 0.0)


def session_count(profile: dict) -> int:
    return int(profile.get("stats", {}).get("sessions", 0) or 0)


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------
def _parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def practice_days(profile: dict) -> list[date]:
    days = set()
    for raw in profile.get("stats", {}).get("practice_dates", []):
        day = _parse_day(raw)
        if day:
            days.add(day)
    return sorted(days)


def current_streak(profile: dict, today: date | None = None) -> int:
    """Consecutive days practised, counting back from today (or yesterday)."""
    today = today or date.today()
    days = set(practice_days(profile))
    if not days:
        return 0
    streak = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(profile: dict) -> int:
    days = practice_days(profile)
    best = run = 0
    previous: date | None = None
    for day in days:
        run = run + 1 if previous is not None and day == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


# ---------------------------------------------------------------------------
# Weak keys / series for charts
# ---------------------------------------------------------------------------
def weakest_keys(profile: dict, limit: int = 8, min_typed: int = 5) -> list[dict]:
    """Keys with the highest error rate (needs a few samples to count)."""
    rows = []
    for key, rec in profile.get("stats", {}).get("weak_keys", {}).items():
        typed = int(rec.get("typed", 0))
        errors = int(rec.get("errors", 0))
        if typed >= min_typed and errors > 0:
            rows.append({"key": key, "typed": typed, "errors": errors,
                         "rate": errors / typed * 100.0})
    rows.sort(key=lambda r: r["rate"], reverse=True)
    return rows[:limit]


def _valid_history(profile: dict) -> list[dict]:
    out = []
    for entry in profile.get("stats", {}).get("history", []):
        try:
            wpm, acc = float(entry.get("wpm", 0)), float(entry.get("acc", 0))
        except (TypeError, ValueError):
            continue
        if is_valid_result(wpm, acc):
            out.append(entry)
    return out


def wpm_accuracy_series(profile: dict) -> list[dict]:
    """Valid session history sorted chronologically (for the line charts)."""
    entries = list(_valid_history(profile))
    entries.sort(key=lambda e: str(e.get("date", "")))
    return entries


def practice_by_day(profile: dict) -> dict[str, float]:
    """Total practice minutes per calendar day (for the streak/time charts)."""
    per_day: dict[str, float] = {}
    for entry in _valid_history(profile):
        day = str(entry.get("date", ""))[:10]
        try:
            per_day[day] = per_day.get(day, 0.0) + float(entry.get("duration", 0.0)) / 60.0
        except (TypeError, ValueError):
            continue
    return per_day


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def relative_day(value: str) -> str:
    day = _parse_day(value)
    if not day:
        return str(value)
    delta = (date.today() - day).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta < 7:
        return f"{delta} days ago"
    return day.isoformat()


def last_played(profile: dict) -> str:
    return str(profile.get("last_played", "") or "")


def last_played_display(profile: dict) -> str:
    raw = last_played(profile)
    if not raw:
        return "never"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return stamp.strftime("%Y-%m-%d %H:%M")
