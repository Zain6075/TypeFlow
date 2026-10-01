"""Local leaderboard: ranks the profiles stored on this PC.

Rankings are computed from the profile records themselves, so there is no
server and nothing to sync.  Impossible results (over 300 WPM, or accuracy
outside 0-100 %) are ignored so a corrupted or hand-edited save file cannot
pollute the board.
"""
from __future__ import annotations

from . import stats

# The four ranking tabs, in display order: (metric id, tab label, entry key).
METRICS = [
    ("level", "Level", "level"),
    ("wpm", "Best WPM", "best_wpm"),
    ("accuracy", "Best Accuracy", "best_accuracy"),
    ("stars", "Stars", "stars"),
]
METRIC_KEYS = {metric: key for metric, _label, key in METRICS}


def profile_entry(profile: dict) -> dict:
    """Condense a full profile record into one leaderboard row."""
    return {
        "id": profile.get("id", ""),
        "name": profile.get("name", "Player"),
        "level": stats.best_level(profile),
        "best_wpm": stats.best_wpm(profile),
        "best_accuracy": stats.best_accuracy(profile),
        "stars": sum(int(r.get("stars", 0)) for r in profile.get("levels", {}).values()),
        "sessions": stats.session_count(profile),
        "last_played": profile.get("last_played", ""),
    }


def build(profiles: list[dict]) -> list[dict]:
    """Build one leaderboard row per profile."""
    return [profile_entry(p) for p in profiles]


def rank(entries: list[dict], metric: str = "level") -> list[dict]:
    """Sort entries by ``metric`` (descending) and attach rank numbers.

    Ties share the same rank (competition ranking: 1, 2, 2, 4).
    """
    key = METRIC_KEYS.get(metric, "level")
    ordered = sorted(entries, key=lambda e: (-float(e.get(key, 0) or 0), e.get("name", "")))
    ranked: list[dict] = []
    previous_value = None
    previous_rank = 0
    for index, entry in enumerate(ordered, start=1):
        value = float(entry.get(key, 0) or 0)
        if previous_value is not None and value == previous_value:
            entry_rank = previous_rank
        else:
            entry_rank = index
            previous_rank = index
            previous_value = value
        ranked.append({**entry, "rank": entry_rank})
    return ranked


def medal(rank_number: int) -> str | None:
    """'gold' / 'silver' / 'bronze' for the top three, else None."""
    return {1: "gold", 2: "silver", 3: "bronze"}.get(rank_number)


def personal_bests(profile: dict) -> list[dict]:
    """Per-level best results for one profile (used by the history view)."""
    rows = []
    for key, record in profile.get("levels", {}).items():
        if not record.get("completed"):
            continue
        wpm = float(record.get("best_wpm", 0.0) or 0.0)
        acc = float(record.get("best_acc", 0.0) or 0.0)
        if not stats.is_valid_result(wpm, acc):
            continue  # ignore impossible stored results
        rows.append({
            "level": int(key),
            "wpm": wpm,
            "accuracy": acc,
            "stars": int(record.get("stars", 0) or 0),
            "attempts": int(record.get("attempts", 0) or 0),
            "completed_at": record.get("completed_at", ""),
        })
    rows.sort(key=lambda r: r["level"])
    return rows


def describe_metric(metric: str) -> str:
    """Human label for a metric id."""
    return {name: label for name, label, _key in METRICS}.get(metric, metric)
