"""Test suite for TypeFlow.

Run with either::

    python tests/run_tests.py          # no dependencies, prints a summary
    python -m pytest tests -q          # if pytest is installed

The suite covers the four things that must be trustworthy:
  1. level locking / unlocking rules
  2. progress saving (storage round-trips, resets, export/import)
  3. the local leaderboard (ranking, impossible-result filtering, medals)
  4. the level engine (stars, adaptive review content, final tests)
plus an end-to-end UI test that plays a level through the real typing screen
and checks that the next level unlocks and the save file on disk is correct.

The Qt parts run on the "offscreen" platform so no display is required.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("TYPEFLOW_DATA_DIR", tempfile.mkdtemp(prefix="typeflow-test-"))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing_app import config, leaderboard, stats as stats_mod          # noqa: E402
from typing_app.level_engine import LevelEngine, load_lessons          # noqa: E402
from typing_app.storage import Storage, new_profile                    # noqa: E402
from typing_app.typing_engine import TypingEngine                      # noqa: E402

ENGINE = LevelEngine(load_lessons())

# One QApplication for the whole session: it must outlive every test function,
# otherwise PyQt destroys the C++ widgets of windows created earlier.
_QT_APP = None


def qt_app():
    """Return (creating on first use) the shared offscreen QApplication."""
    global _QT_APP
    from PyQt6.QtWidgets import QApplication
    if _QT_APP is None:
        _QT_APP = QApplication.instance() or QApplication(sys.argv[:1])
        _QT_APP.typeflow_theme = "dark"
    return _QT_APP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class FakeClock:
    """Deterministic monotonic clock: tests advance time by hand."""

    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def fresh_storage() -> Storage:
    """A Storage pointed at a brand-new temporary directory."""
    return Storage(Path(tempfile.mkdtemp(prefix="typeflow-test-")))


def play(engine: TypingEngine, text: str, clock: FakeClock, errors: int = 0,
         seconds_per_key: float = 0.15) -> None:
    """Type ``text`` through ``engine``, optionally making ``errors`` mistakes."""
    mistakes_at = set()
    if errors:
        step = max(1, len(text) // (errors + 1))
        mistakes_at = {i * step for i in range(1, errors + 1)}
    for index, char in enumerate(text):
        clock.advance(seconds_per_key)
        if index in mistakes_at:
            engine.press("\\" if char != "\\" else "/")     # guaranteed wrong
        else:
            engine.press(char)


def completed_profile(name: str = "Tester", levels: int = 3, wpm: float = 40.0,
                      accuracy: float = 95.0, stars: int = 3) -> dict:
    """A synthetic profile with ``levels`` completed levels."""
    profile = new_profile(name)
    for level in range(1, levels + 1):
        profile["levels"][str(level)] = {
            "best_wpm": wpm, "best_acc": accuracy, "stars": stars, "attempts": 1,
            "completed": True, "completed_at": "2026-09-30T10:00:00", "history": [],
        }
    profile["stats"]["sessions"] = levels
    profile["stats"]["total_time_sec"] = 300.0 * levels
    profile["stats"]["total_correct"] = 1000 * levels
    profile["stats"]["total_typed"] = 1050 * levels
    return profile


# ---------------------------------------------------------------------------
# 1. Level engine
# ---------------------------------------------------------------------------
def test_every_level_generates_practice_text():
    profile = new_profile("Generator")
    for level in range(1, config.TOTAL_LEVELS + 1):
        text = ENGINE.build_text(level, profile)
        assert isinstance(text, str) and len(text) > 20, f"level {level} produced no text"
        assert "  " not in text, f"level {level} has double spaces"


def test_min_wpm_rises_every_ten_levels():
    values = [ENGINE.min_wpm(level) for level in range(1, 101)]
    assert values[0] == config.BASE_MIN_WPM
    for level in (1, 11, 21, 31, 41, 51, 61, 71, 81, 91):
        expected = config.BASE_MIN_WPM + config.WPM_STEP_PER_TEN * ((level - 1) // 10)
        assert ENGINE.min_wpm(level) == expected
    assert values[-1] > values[0], "min WPM must rise over the campaign"
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_final_tests_mix_everything():
    for level in config.FINAL_TEST_LEVELS:
        spec = ENGINE.spec(level)
        assert spec["kind"] == "test" and spec["is_test"]
        text = ENGINE.build_text(level, new_profile("Mixer"))
        assert len(text) > 400, f"final test {level} is too short"


def test_row_levels_cover_the_keyboard():
    seen = set()
    for level in range(1, 11):
        text = ENGINE.build_text(level, new_profile("Rows"))
        seen |= {c for c in text if c.isalnum()}
    home = {c for c in "asdfghjkl;" if c.isalnum()}
    top = {c for c in "qwertyuiop" if c.isalnum()}
    bottom = {c for c in "zxcvbnm,./" if c.isalnum()}
    numbers = set("1234567890")
    assert home <= seen, "home row letters must appear"
    assert top <= seen, "top row letters must appear"
    assert bottom <= seen, "bottom row letters must appear"
    assert numbers <= seen, "digits must appear"
    # Level 10 must exercise punctuation.
    punctuation = set(load_lessons()["rows"]["punctuation"])
    level_ten = ENGINE.build_text(10, new_profile("Punct"))
    assert punctuation & set(level_ten), "punctuation level must use punctuation"


def test_star_thresholds():
    # Level 1 needs 8 WPM / 80 %.
    assert ENGINE.stars(1, 8.0, 80.0) == 1
    assert ENGINE.stars(1, 7.9, 99.0) == 0            # too slow
    assert ENGINE.stars(1, 50.0, 79.9) == 0           # not accurate enough
    assert ENGINE.stars(1, 13.0, 90.0) == 2
    assert ENGINE.stars(1, 13.0, 89.9) == 1
    assert ENGINE.stars(1, 18.0, 96.0) == 3
    assert ENGINE.stars(1, 17.9, 99.0) == 2
    # Harder levels demand more speed for the same star.
    assert ENGINE.stars(50, 16.0, 80.0) == 1
    assert ENGINE.stars(50, 21.0, 90.0) == 2
    assert ENGINE.stars(50, 26.0, 96.0) == 3


def test_review_content_uses_weak_keys_and_words():
    profile = new_profile("Weak")
    profile["stats"]["weak_keys"] = {"f": {"errors": 9, "typed": 20}}
    profile["stats"]["weak_words"] = {"the": 4}
    text = ENGINE.build_text(4, profile)          # row level -> key drill
    assert "f" in text and text.count("f") > 5
    words_text = ENGINE.build_text(15, profile)   # word level -> weak words
    assert "the" in words_text.split()


def test_review_never_uses_harder_material():
    """A level-15 lesson may not contain 'hard' pool words the player has not reached."""
    lessons = load_lessons()
    hard_only = set(lessons["words"]["hard"]) - set(lessons["words"]["medium"])
    for level in (11, 12, 13, 14, 15, 16, 20, 21):
        text = ENGINE.build_text(level, new_profile("Easy"))
        used = {w.strip(".,!?;:'\"()").lower() for w in text.split()}
        assert not (used & hard_only), f"level {level} leaked hard words"


# ---------------------------------------------------------------------------
# 2. Level locking & progression
# ---------------------------------------------------------------------------
def test_level_locking_rules():
    profile = new_profile("Locked")
    assert ENGINE.is_unlocked(1, profile)
    assert not ENGINE.is_unlocked(2, profile)
    assert ENGINE.status(2, profile) == "locked"
    assert ENGINE.next_level(profile) == 1

    # Failing a level does not unlock the next one.
    profile["levels"]["1"] = {"completed": False, "best_wpm": 40, "best_acc": 95,
                              "stars": 0, "attempts": 1}
    assert not ENGINE.is_unlocked(2, profile)

    # Passing it does.
    profile["levels"]["1"]["completed"] = True
    profile["levels"]["1"]["stars"] = 2
    assert ENGINE.is_unlocked(2, profile)
    assert ENGINE.status(2, profile) == "unlocked"
    assert ENGINE.next_level(profile) == 2
    assert ENGINE.status(1, profile) == "completed"


def test_pass_requires_accuracy_and_speed():
    assert not ENGINE.passed(10, 100.0, 79.9)      # fast but sloppy
    assert not ENGINE.passed(10, 7.9, 100.0)       # accurate but slow
    assert ENGINE.passed(10, 8.0, 80.0)            # exactly the requirement


def test_progress_helpers():
    profile = completed_profile(levels=5)
    assert ENGINE.highest_completed(profile) == 5
    assert ENGINE.total_stars(profile) == 15
    assert ENGINE.next_level(profile) == 6


# ---------------------------------------------------------------------------
# 3. Typing engine
# ---------------------------------------------------------------------------
def test_perfect_run_scores_100_percent():
    clock = FakeClock()
    engine = TypingEngine("the quick brown fox", clock=clock)
    play(engine, engine.text, clock, seconds_per_key=0.12)
    assert engine.finished
    assert engine.errors == 0
    assert engine.live_accuracy() == 100.0
    assert engine.live_wpm() > 0
    result = engine.result()
    assert result.finished and result.chars == len(engine.text)


def test_mistakes_lower_accuracy_and_track_weak_keys():
    clock = FakeClock()
    engine = TypingEngine("accuracy matters more than speed", clock=clock)
    play(engine, engine.text, clock, errors=6)
    assert engine.errors == 6
    assert engine.live_accuracy() < 100.0
    tracked = engine.result().weak_keys
    assert tracked, "keys must be tracked"
    assert sum(entry["errors"] for entry in tracked.values()) == engine.errors
    assert any(entry["errors"] >= 1 for entry in tracked.values())


def test_backspace_rewinds_position():
    engine = TypingEngine("hello")
    for char in "hel":
        engine.press(char)
    assert engine.pos == 3
    engine.backspace()
    assert engine.pos == 2 and engine.states[2] == 0
    engine.press("l")
    assert engine.pos == 3


def test_weak_words_are_recorded():
    clock = FakeClock()
    engine = TypingEngine("the cat and the dog", clock=clock)
    for index, char in enumerate(engine.text):
        clock.advance(0.1)
        engine.press("x" if index in (4, 5) else char)   # mistype "cat"
    assert engine.result().weak_words.get("cat", 0) >= 1


# ---------------------------------------------------------------------------
# 4. Storage: progress saving
# ---------------------------------------------------------------------------
def test_profile_round_trip_and_persistence():
    store = fresh_storage()
    profile = store.create_profile("Saver")
    profile["levels"]["1"] = {"best_wpm": 33.3, "best_acc": 97.5, "stars": 2,
                              "attempts": 2, "completed": True,
                              "completed_at": "2026-10-01T09:00:00", "history": []}
    store.save_profile(profile)

    reloaded = store.load_profile(profile["id"])
    assert reloaded is not None
    assert reloaded["name"] == "Saver"
    assert reloaded["levels"]["1"]["best_wpm"] == 33.3
    assert reloaded["levels"]["1"]["stars"] == 2
    # A fresh Storage instance (app restart) sees the same data.
    assert Storage(store.root).load_profile(profile["id"])["levels"]["1"]["stars"] == 2


def test_settings_round_trip():
    store = fresh_storage()
    settings = store.load_settings()
    assert settings["theme"] in ("dark", "light")
    settings["theme"] = "light"
    settings["font_size"] = 18
    store.save_settings(settings)
    assert store.load_settings()["theme"] == "light"
    assert store.load_settings()["font_size"] == 18


def test_reset_profile_keeps_identity():
    store = fresh_storage()
    profile = store.create_profile("Resettable")
    profile["levels"]["1"] = {"completed": True, "stars": 3, "best_wpm": 50, "best_acc": 99,
                              "attempts": 1}
    store.save_profile(profile)
    fresh = store.reset_profile(profile["id"], "Resettable")
    assert fresh["id"] == profile["id"]
    assert fresh["levels"] == {}
    assert fresh["name"] == "Resettable"
    assert [p["id"] for p in store.load_profiles()] == [profile["id"]]


def test_delete_profile_removes_it():
    store = fresh_storage()
    first = store.create_profile("One")
    second = store.create_profile("Two")
    store.delete_profile(first["id"])
    ids = [p["id"] for p in store.load_profiles()]
    assert first["id"] not in ids and second["id"] in ids
    assert store.load_profile(first["id"]) is None


def test_export_import_profile():
    store = fresh_storage()
    profile = store.create_profile("Exporter")
    profile["levels"]["3"] = {"completed": True, "stars": 2, "best_wpm": 25, "best_acc": 91,
                              "attempts": 1}
    store.save_profile(profile)
    target = store.root / "export.json"
    store.export_profile(profile["id"], target)
    payload = json.loads(target.read_text())
    assert payload["kind"] == "profile" and payload["profile"]["name"] == "Exporter"

    other = fresh_storage()
    imported = other.import_profile(target)
    assert imported["name"] == "Exporter"
    assert imported["levels"]["3"]["best_wpm"] == 25


def test_export_import_everything():
    store = fresh_storage()
    store.create_profile("A")
    store.create_profile("B")
    store.save_settings({"theme": "light", "sound": False, "font_size": 14,
                         "volume": 30, "keyboard_guide": False})
    target = store.root / "backup.json"
    store.export_all(target)

    other = fresh_storage()
    imported = other.import_all(target)
    assert {p["name"] for p in imported} == {"A", "B"}
    assert other.load_settings()["theme"] == "light"
    assert len(other.load_profiles()) == 2


def test_corrupt_save_files_do_not_crash():
    store = fresh_storage()
    profile = store.create_profile("Corrupt")
    (store.root / f"profile_{profile['id']}.json").write_text("{ not json", encoding="utf-8")
    assert store.load_profile(profile["id"]) is None
    (store.root / config.SETTINGS_FILE).write_text("garbage", encoding="utf-8")
    assert store.load_settings()["theme"] == config.DEFAULT_SETTINGS["theme"]


# ---------------------------------------------------------------------------
# 5. Statistics
# ---------------------------------------------------------------------------
def test_streak_calculation():
    profile = new_profile("Streaks")
    today = date.today()
    profile["stats"]["practice_dates"] = [
        (today - timedelta(days=2)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
        today.isoformat(),
    ]
    assert stats_mod.current_streak(profile) == 3
    assert stats_mod.longest_streak(profile) == 3

    profile["stats"]["practice_dates"].append((today - timedelta(days=5)).isoformat())
    assert stats_mod.longest_streak(profile) == 3       # gap breaks the older run
    assert stats_mod.current_streak(profile) == 3       # today still ends a 3-day run


def test_streak_counts_yesterday_when_today_is_missing():
    profile = new_profile("Yesterday")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    profile["stats"]["practice_dates"] = [yesterday]
    assert stats_mod.current_streak(profile) == 1


def test_weakest_keys_ordering():
    profile = new_profile("Weak")
    profile["stats"]["weak_keys"] = {
        "a": {"errors": 1, "typed": 50},
        "k": {"errors": 9, "typed": 30},
        "p": {"errors": 4, "typed": 20},
    }
    weakest = stats_mod.weakest_keys(profile)
    assert [row["key"] for row in weakest] == ["k", "p", "a"]
    assert abs(weakest[0]["rate"] - 30.0) < 0.01


def test_impossible_results_are_rejected():
    assert not stats_mod.is_valid_result(450.0, 95.0)
    assert not stats_mod.is_valid_result(-1.0, 95.0)
    assert not stats_mod.is_valid_result(60.0, 101.0)
    assert stats_mod.is_valid_result(60.0, 95.0)


# ---------------------------------------------------------------------------
# 6. Leaderboard
# ---------------------------------------------------------------------------
def test_leaderboard_ranking_per_metric():
    profiles = [
        completed_profile("SlowButHigh", levels=2, wpm=20.0, accuracy=99.0, stars=3),
        completed_profile("Fast", levels=9, wpm=95.0, accuracy=85.0, stars=2),
        completed_profile("StarCollector", levels=5, wpm=40.0, accuracy=90.0, stars=3),
    ]
    entries = leaderboard.build(profiles)

    by_level = leaderboard.rank(entries, "level")
    assert [e["name"] for e in by_level][:2] == ["Fast", "StarCollector"]
    assert by_level[0]["rank"] == 1

    by_wpm = leaderboard.rank(entries, "wpm")
    assert by_wpm[0]["name"] == "Fast" and by_wpm[0]["rank"] == 1

    by_accuracy = leaderboard.rank(entries, "accuracy")
    assert by_accuracy[0]["name"] == "SlowButHigh"

    by_stars = leaderboard.rank(entries, "stars")
    assert by_stars[0]["name"] == "Fast"          # 9 levels x 2 stars = 18
    assert by_stars[0]["rank"] == 1


def test_leaderboard_ignores_impossible_results():
    profile = new_profile("Cheater")
    profile["levels"]["1"] = {"completed": True, "stars": 3, "best_wpm": 9000.0,
                              "best_acc": 100.0, "attempts": 1}
    profile["levels"]["2"] = {"completed": True, "stars": 1, "best_wpm": 45.0,
                              "best_acc": 88.0, "attempts": 1}
    entry = leaderboard.profile_entry(profile)
    assert entry["best_wpm"] == 45.0, "results over 300 WPM must be ignored"
    assert entry["level"] == 2
    assert leaderboard.personal_bests(profile)[0]["level"] == 2


def test_medals_for_top_three():
    assert leaderboard.medal(1) == "gold"
    assert leaderboard.medal(2) == "silver"
    assert leaderboard.medal(3) == "bronze"
    assert leaderboard.medal(4) is None


def test_tied_entries_share_a_rank():
    entries = leaderboard.build([completed_profile("A", levels=4),
                                 completed_profile("B", levels=4)])
    ranked = leaderboard.rank(entries, "level")
    assert ranked[0]["rank"] == 1 and ranked[1]["rank"] == 1


# ---------------------------------------------------------------------------
# 7. End-to-end UI test: play a level through the real typing screen
# ---------------------------------------------------------------------------
def _make_window(store: Storage):
    from typing_app.app import MainWindow
    qt_app()                       # make sure a QApplication exists first
    return MainWindow(storage=store)


def test_end_to_end_play_unlock_and_save():
    from PyQt6.QtWidgets import QApplication

    store = fresh_storage()
    window = _make_window(store)
    app = QApplication.instance()

    # --- level 2 must be locked at the start -------------------------------
    assert window.engine.is_unlocked(1, window.profile)
    assert not window.engine.is_unlocked(2, window.profile)
    assert not window.engine.is_unlocked(50, window.profile)

    # --- play level 1 through the real typing screen ------------------------
    window.open_level(1)
    assert window.stack.currentWidget() is window.typing_page
    page = window.typing_page
    text = page.engine.text
    clock = FakeClock()
    page.engine._clock = clock                     # deterministic timing
    for char in text:
        clock.advance(0.12)                        # ~90 WPM: comfortably passes
        page._press(char)
    assert page.engine.finished
    app.processEvents()

    # The page schedules the results screen with a short timer; let it fire.
    from PyQt6.QtTest import QTest
    QTest.qWait(500)
    assert window.stack.currentWidget() is window.results_page, "results screen not shown"

    # --- the result was saved and level 2 is now unlocked -------------------
    assert window.profile["levels"]["1"]["completed"] is True
    assert window.profile["levels"]["1"]["stars"] >= 1
    assert window.engine.is_unlocked(2, window.profile)
    assert window.engine.next_level(window.profile) == 2

    # --- and it survived a full app restart ---------------------------------
    reloaded = store.load_profile(window.profile["id"])
    assert reloaded["levels"]["1"]["completed"] is True
    assert reloaded["stats"]["sessions"] == 1
    assert reloaded["stats"]["total_typed"] > 0
    assert reloaded["stats"]["practice_dates"], "today must be recorded as a practice day"

    # --- a sloppy attempt does not unlock anything ---------------------------
    window.open_level(2)
    page = window.typing_page
    clock = FakeClock()
    page.engine._clock = clock
    text = page.engine.text
    for index, char in enumerate(text):
        clock.advance(0.4)                         # far too slow for level 2
        if index % 3 == 0:
            page._press("#")                       # and very inaccurate
        page._press(char)
    assert page.engine.finished
    window.on_level_finished(2, page.engine.result())
    assert window.profile["levels"]["2"]["completed"] is False
    assert window.engine.is_unlocked(3, window.profile) is False
    assert window.profile["levels"]["1"]["completed"] is True, "earlier progress is kept"

    # --- the results screen offers a retry -----------------------------------
    assert window.results_page.retry_button.isEnabled()


def test_leaderboard_across_profiles_and_current_highlight():
    store = fresh_storage()
    window = _make_window(store)

    # Give the current profile some progress and create a rival.
    window.profile["levels"]["1"] = {"completed": True, "stars": 2, "best_wpm": 42.0,
                                     "best_acc": 92.0, "attempts": 1}
    window.storage.save_profile(window.profile)
    rival = window.storage.create_profile("Rival")
    rival["levels"] = {str(level): {"completed": True, "stars": 3, "best_wpm": 70.0,
                                    "best_acc": 88.0, "attempts": 1}
                       for level in range(1, 6)}
    window.storage.save_profile(rival)

    window.navigate("leaderboard")
    page = window.leaderboard_page
    assert page.tables["level"].rowCount() == 2
    top_name = page.tables["level"].item(0, 1).text()
    assert "Rival" in top_name, "the profile with more levels must rank first"
    assert page.tables["wpm"].item(0, 1).text().startswith("Rival")

    # The current profile is highlighted and its personal bests are listed.
    assert any("(you)" in (page.tables["level"].item(r, 1).text() or "")
               for r in range(page.tables["level"].rowCount()))
    assert page.bests_table.rowCount() >= 1
    assert page.bests_table.item(0, 0).text() == "1"


def test_profile_switching_isolates_progress():
    store = fresh_storage()
    window = _make_window(store)
    window.create_profile("Second")
    assert window.profile["name"] == "Second"
    assert window.engine.next_level(window.profile) == 1

    first = store.load_profiles()[0]["id"]
    window.switch_profile(first)
    assert window.profile["name"] == "Player"
    assert len(window.profiles) == 2


def test_settings_persist_and_switch_theme():
    store = fresh_storage()
    window = _make_window(store)
    window.settings["theme"] = "light"
    window.settings["font_size"] = 18
    window.save_settings()
    assert store.load_settings()["theme"] == "light"
    assert store.load_settings()["font_size"] == 18

    window.apply_settings()
    from PyQt6.QtWidgets import QApplication
    assert QApplication.instance().typeflow_theme == "light"


def test_adaptive_lesson_content_changes_with_progress():
    """The same level produces different review material once mistakes exist."""
    store = fresh_storage()
    window = _make_window(store)
    clean = window.engine.build_text(4, window.profile)

    window.profile["stats"]["weak_keys"] = {"d": {"errors": 12, "typed": 25}}
    window.profile["stats"]["weak_words"] = {"the": 6}
    adaptive = window.engine.build_text(4, window.profile)
    assert adaptive != clean
    assert adaptive.count("d") > clean.count("d")
