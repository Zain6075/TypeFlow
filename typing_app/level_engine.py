"""Level engine: the 100-level campaign, unlock rules, stars and the
adaptive lesson generator.

Progression rules
-----------------
* Levels 1-10 teach the keyboard row by row (home, top, bottom, numbers,
  shift/capitals, punctuation).
* Levels 11-100 move from single words to sentences to paragraphs with
  steadily rising difficulty; levels 25/50/75/100 are "final tests" that mix
  everything learned so far.
* A level is passed with >= 80 % accuracy **and** at least a minimum WPM that
  rises by 2 WPM every ten levels (8, 10, 12, ... 26 WPM).
* Every lesson is ~70 % new material + ~30 % review drawn from earlier
  lessons, biased towards the player's weakest keys and words (a simple form
  of spaced repetition).
* Stars: 1 star = passed, 2 stars = +5 WPM & 90 % accuracy,
  3 stars = +10 WPM & 96 % accuracy.
* Retries are unlimited and never penalised.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from . import config

# ---------------------------------------------------------------------------
# Fallback content (used only if lessons.json is missing/corrupt so that the
# app can never crash because of bad data).
# ---------------------------------------------------------------------------
FALLBACK_LESSONS: dict[str, Any] = {
    "rows": {
        "home": "asdfghjkl;",
        "top": "qwertyuiop",
        "bottom": "zxcvbnm,./",
        "numbers": "1234567890",
        "punctuation": "!?.,;:'\"()-_$%&*",
    },
    "words": {"easy": ["the", "and", "for", "you", "cat", "dog"],
              "medium": ["water", "house", "green", "light"],
              "hard": ["beautiful", "adventure", "knowledge"]},
    "sentences": {"easy": ["the cat sat on the mat."],
                  "medium": ["practice makes progress every single day."],
                  "hard": ["accuracy matters far more than raw speed."]},
    "paragraphs": {"medium": ["typing well is a skill built one key at a time."],
                   "hard": ["steady practice and calm hands beat frantic speed."]},
}

# Row-by-row teaching plan for levels 1-10.
ROW_PLAN: dict[int, dict[str, str]] = {
    1:  {"title": "Home row: index fingers",      "new": "fj",       "review": ""},
    2:  {"title": "Home row: left hand",          "new": "asdg",     "review": "fj"},
    3:  {"title": "Home row: right hand",         "new": "hkl;",     "review": "asdgfj"},
    4:  {"title": "Top row: left hand",           "new": "qwert",    "review": "asdgfjhkl;"},
    5:  {"title": "Top row: right hand",          "new": "yuiop",    "review": "qwertasdg"},
    6:  {"title": "Bottom row: left hand",        "new": "zxcvb",    "review": "qwertasdgfj"},
    7:  {"title": "Bottom row: right hand",       "new": "nm,./",    "review": "yuiophjkl;zxcvb"},
    8:  {"title": "Numbers",                      "new": "1234567890", "review": "asdfghjkl;"},
    9:  {"title": "Shift and capitals",           "new": "",         "review": ""},
    10: {"title": "Punctuation marks",            "new": "",         "review": ""},
}

# Characters per drill for the row levels (grows a little).
ROW_TARGET_CHARS = {1: 160, 2: 180, 3: 200, 4: 240, 5: 260, 6: 280, 7: 300, 8: 320, 9: 340, 10: 360}

POOL_ORDER = ["easy", "medium", "hard"]  # easy -> hard; used to pick "old" pools


def load_lessons(path: Path | None = None) -> dict:
    """Load the editable lesson data (``typing_app/data/lessons.json``)."""
    path = path or config.lessons_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("lessons.json must contain an object")
        merged = dict(FALLBACK_LESSONS)
        merged.update(data)
        return merged
    except (OSError, json.JSONDecodeError, ValueError):
        return dict(FALLBACK_LESSONS)


class LevelEngine:
    """Pure logic for levels: specs, unlocking, stars and lesson generation."""

    TOTAL = config.TOTAL_LEVELS

    def __init__(self, lessons: dict | None = None):
        self.lessons = lessons or load_lessons()
        self._pools = {
            "words": self.lessons.get("words", FALLBACK_LESSONS["words"]),
            "sentences": self.lessons.get("sentences", FALLBACK_LESSONS["sentences"]),
            "paragraphs": self.lessons.get("paragraphs", FALLBACK_LESSONS["paragraphs"]),
        }

    # -- level specifications ------------------------------------------------
    def spec(self, level: int) -> dict:
        """Return the blueprint for ``level`` (kind, pools, size, min WPM...)."""
        level = int(level)
        if not 1 <= level <= self.TOTAL:
            raise ValueError(f"level must be 1..{self.TOTAL}, got {level}")

        if level in config.FINAL_TEST_LEVELS:
            return self._test_spec(level)
        if level <= 10:
            plan = ROW_PLAN[level]
            return {
                "level": level,
                "kind": "shift" if level == 9 else "punctuation" if level == 10 else "row",
                "title": plan["title"],
                "description": self._row_description(level, plan),
                "keys": plan["new"],
                "review_keys": plan["review"],
                "target_chars": ROW_TARGET_CHARS[level],
                "min_wpm": self.min_wpm(level),
                "is_test": False,
            }
        if level <= 24:
            return self._words_spec(level)
        if level <= 49:
            return self._sentence_spec(level)
        if level <= 74:
            return self._mid_late_spec(level)
        return self._paragraph_spec(level)

    # -- unlock / stars ------------------------------------------------------
    def min_wpm(self, level: int) -> float:
        """Minimum WPM needed to pass ``level`` (rises every 10 levels)."""
        return config.BASE_MIN_WPM + config.WPM_STEP_PER_TEN * ((int(level) - 1) // 10)

    def passed(self, level: int, wpm: float, accuracy: float) -> bool:
        return accuracy >= config.PASS_ACCURACY and wpm >= self.min_wpm(level)

    def stars(self, level: int, wpm: float, accuracy: float) -> int:
        """0 = not passed, otherwise 1-3 stars."""
        if not self.passed(level, wpm, accuracy):
            return 0
        need = self.min_wpm(level)
        if accuracy >= config.STAR3_ACCURACY and wpm >= need + config.STAR3_WPM_BONUS:
            return 3
        if accuracy >= config.STAR2_ACCURACY and wpm >= need + config.STAR2_WPM_BONUS:
            return 2
        return 1

    def level_record(self, profile: dict, level: int) -> dict | None:
        return profile.get("levels", {}).get(str(int(level)))

    def is_unlocked(self, level: int, profile: dict) -> bool:
        """Level 1 is always open; level N needs level N-1 completed."""
        level = int(level)
        if level <= 1:
            return True
        record = self.level_record(profile, level - 1)
        return bool(record and record.get("completed"))

    def status(self, level: int, profile: dict) -> str:
        record = self.level_record(profile, level)
        if record and record.get("completed"):
            return "completed"
        return "unlocked" if self.is_unlocked(level, profile) else "locked"

    def next_level(self, profile: dict) -> int:
        """First level that is not completed yet (clamped to the campaign)."""
        for level in range(1, self.TOTAL + 1):
            if not (self.level_record(profile, level) or {}).get("completed"):
                return level
        return self.TOTAL

    def highest_completed(self, profile: dict) -> int:
        best = 0
        for level in range(1, self.TOTAL + 1):
            if (self.level_record(profile, level) or {}).get("completed"):
                best = level
        return best

    def total_stars(self, profile: dict) -> int:
        return sum(int(r.get("stars", 0)) for r in profile.get("levels", {}).values())

    # -- lesson generation ---------------------------------------------------
    def build_text(self, level: int, profile: dict) -> str:
        """Build the practice text for ``level`` for this player.

        Deterministic per (profile, level) so retries use the same text, but
        adaptive because the review part depends on the player's weak keys and
        weak words.
        """
        spec = self.spec(level)
        rng = random.Random(f"{profile.get('id', 'local')}:{int(level)}")
        kind = spec["kind"]
        if kind in ("shift", "punctuation"):
            return self._symbol_text(spec, profile, rng)
        if kind == "row":
            return self._row_text(spec, profile, rng)
        if kind == "words":
            return self._words_text(spec, profile, rng)
        if kind == "sentences":
            return self._sentences_text(spec, profile, rng)
        if kind == "paragraphs":
            return self._paragraph_text(spec, profile, rng)
        return self._test_text(spec, profile, rng)

    # -- generators ----------------------------------------------------------
    def _row_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        """Random key groups from the new keys, with ~30 % recycled keys."""
        new_keys = list(spec["keys"])
        review_keys = list(spec["review_keys"])
        weak = self._weak_key_order(profile)
        # Weight the pool: new keys dominate, weak/review keys get extra pulls.
        pool = new_keys * 4
        pool += review_keys * max(1, int(len(new_keys) * 0.5))
        for key in weak[:4]:
            pool += [key] * 3 if key in pool else []
        groups: list[str] = []
        total = 0
        while total < spec["target_chars"]:
            size = rng.randint(3, 6)
            group = "".join(rng.choice(pool) for _ in range(size))
            groups.append(group)
            total += size + 1
        text = " ".join(groups)
        return self._with_weak_drill(text, profile, rng)

    def _symbol_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        """Levels 9 (shift/capitals) and 10 (punctuation)."""
        words = self._pool("words", "easy") + self._pool("words", "medium")
        marks = list(self.lessons.get("rows", FALLBACK_LESSONS["rows"])["punctuation"])
        tokens: list[str] = []
        target = spec["target_chars"]
        if spec["kind"] == "shift":
            # Capitalised words + ALL-CAPS words -> shift key practice.
            while sum(len(t) + 1 for t in tokens) < target:
                word = rng.choice(words)
                style = rng.random()
                if style < 0.4:
                    word = word.capitalize()
                elif style < 0.55:
                    word = word.upper()
                tokens.append(word)
            # A drill of shifted symbols for good measure.
            tokens.append(" ".join("".join(rng.choice("!@#$%^&*()") for _ in range(4))
                                   for _ in range(3)))
        else:
            # Words carrying punctuation marks.
            while sum(len(t) + 1 for t in tokens) < target:
                word = rng.choice(words)
                if rng.random() < 0.45:
                    word += rng.choice(marks)
                tokens.append(word)
            tokens.append(" ".join(marks))
        text = " ".join(tokens)
        return self._with_weak_drill(text, profile, rng)

    def _words_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        new_pool = self._merged_pool(spec["pools"], "words")
        review_pool = self._review_words(spec, profile)
        count = spec["count"]
        n_review = max(1, round(count * config.REVIEW_FRACTION))
        words = [rng.choice(review_pool) for _ in range(n_review)]
        words += [rng.choice(new_pool) for _ in range(count - n_review)]
        rng.shuffle(words)
        text = " ".join(words)
        return self._with_weak_drill(text, profile, rng)

    def _sentences_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        new_pool = self._merged_pool(spec["pools"], "sentences")
        review_pool = self._review_sentences(spec, profile)
        count = spec["count"]
        n_review = max(1, round(count * config.REVIEW_FRACTION))
        picked = [rng.choice(review_pool) for _ in range(n_review)]
        picked += [rng.choice(new_pool) for _ in range(count - n_review)]
        rng.shuffle(picked)
        text = " ".join(picked)
        return self._with_weak_drill(text, profile, rng)

    def _paragraph_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        new_pool = self._merged_pool(spec["pools"], "paragraphs")
        review_pool = self._review_paragraphs(spec, profile)
        target_words = spec["words"]
        chunks: list[str] = []
        total = 0
        while total < target_words:
            source = review_pool if (chunks and rng.random() < config.REVIEW_FRACTION) else new_pool
            paragraph = rng.choice(source)
            chunks.append(paragraph)
            total += len(paragraph.split())
        text = " ".join(chunks)
        return self._with_weak_drill(text, profile, rng)

    def _test_text(self, spec: dict, profile: dict, rng: random.Random) -> str:
        """Final tests: a balanced mix of everything learned so far."""
        chapters = spec["chapters"]
        parts: list[str] = []
        # Words from every difficulty unlocked by this point.
        words = self._merged_pool(POOL_ORDER[:chapters], "words")
        sentences = self._merged_pool(POOL_ORDER[:chapters], "sentences")
        paragraphs = self._merged_pool(POOL_ORDER[:chapters], "paragraphs")
        parts.append(" ".join(rng.choice(words) for _ in range(14)))
        parts.append(" ".join(rng.choice(sentences) for _ in range(4)))
        # Keep pulling paragraphs until the target length is reached.
        total = sum(len(p.split()) for p in parts)
        while total < spec["words"]:
            paragraph = rng.choice(paragraphs)
            parts.append(paragraph)
            total += len(paragraph.split())
        rng.shuffle(parts)
        return self._with_weak_drill(" ".join(parts), profile, rng)

    # -- review helpers (spaced repetition) ----------------------------------
    def _weak_key_order(self, profile: dict) -> list[str]:
        """Keys ordered by error rate (worst first)."""
        weak = profile.get("stats", {}).get("weak_keys", {})
        ranked = []
        for key, rec in weak.items():
            typed = max(1, int(rec.get("typed", 0)))
            errors = int(rec.get("errors", 0))
            if errors > 0:
                ranked.append((errors / typed, errors, key))
        ranked.sort(reverse=True)
        return [key for _, _, key in ranked]

    def _review_words(self, spec: dict, profile: dict) -> list[str]:
        """Words to recycle: the player's worst words first, then old pools."""
        weak_words = [w for w, _ in sorted(profile.get("stats", {}).get("weak_words", {}).items(),
                                           key=lambda kv: kv[1], reverse=True)[:12]]
        old = self._older_pools(spec["pools"])
        pool = list(weak_words)
        for name in old:
            pool += self._pool("words", name)
        return pool or self._pool("words", "easy")

    def _review_sentences(self, spec: dict, profile: dict) -> list[str]:
        pool: list[str] = []
        for name in self._older_pools(spec["pools"]):
            pool += self._pool("sentences", name)
        return pool or self._pool("sentences", "easy")

    def _review_paragraphs(self, spec: dict, profile: dict) -> list[str]:
        pool: list[str] = []
        for name in self._older_pools(spec["pools"]):
            pool += self._pool("paragraphs", name)
        return pool or self._pool("paragraphs", "medium")

    def _with_weak_drill(self, text: str, profile: dict, rng: random.Random) -> str:
        """Prepend a short drill for the player's weakest keys/words."""
        stats = profile.get("stats", {})
        weak_keys = self._weak_key_order(profile)[:3]
        weak_words = [w for w, _ in sorted(stats.get("weak_words", {}).items(),
                                           key=lambda kv: kv[1], reverse=True)[:4]]
        if not weak_keys and not weak_words:
            return text
        drill: list[str] = []
        for key in weak_keys:
            drill.append(" ".join(key * rng.randint(2, 4) for _ in range(2)))
        if weak_words:
            drill.append(" ".join(weak_words * 2))
        return " ".join(drill) + " " + text

    # -- pool utilities -------------------------------------------------------
    def _pool(self, kind: str, name: str) -> list[str]:
        return list(self._pools[kind].get(name, []))

    def _merged_pool(self, names: list[str], kind: str) -> list[str]:
        pool: list[str] = []
        for name in names:
            pool += self._pool(kind, name)
        return pool or self._pool(kind, "easy")

    @staticmethod
    def _older_pools(current: list[str]) -> list[str]:
        """Pools that are *easier* than the ones currently being practised.

        Review material must come from earlier (easier) lessons, never from
        harder pools the player has not reached yet.
        """
        first_index = min((POOL_ORDER.index(name) for name in current if name in POOL_ORDER),
                          default=len(POOL_ORDER))
        return POOL_ORDER[:first_index]

    # -- spec builders ---------------------------------------------------------
    def _words_spec(self, level: int) -> dict:
        if level < 14:
            pools, count = ["easy"], 16 + (level - 11) * 2
        elif level < 17:
            pools, count = ["easy", "medium"], 22 + (level - 14) * 2
        elif level < 23:
            pools, count = ["medium"], 30 + (level - 17) * 2
        else:
            pools, count = ["medium", "hard"], 38 + (level - 21) * 3
        return {
            "level": level, "kind": "words",
            "title": f"Word practice {level - 10}/14",
            "description": f"Type {' and '.join(pools)} words - {count} words",
            "pools": pools, "count": count,
            "min_wpm": self.min_wpm(level), "is_test": False,
        }

    def _sentence_spec(self, level: int) -> dict:
        if level < 33:
            pools, count = ["easy"], 3 + (level - 26) // 2
        elif level < 41:
            pools, count = ["easy", "medium"], 5 + (level - 33) // 2
        elif level < 49:
            pools, count = ["medium"], 7 + (level - 41) // 2
        else:
            pools, count = ["medium", "hard"], 10
        return {
            "level": level, "kind": "sentences",
            "title": f"Sentence practice {level - 25}/24",
            "description": f"Type {count} {' and '.join(pools)} sentences",
            "pools": pools, "count": count,
            "min_wpm": self.min_wpm(level), "is_test": False,
        }

    def _mid_late_spec(self, level: int) -> dict:
        if level <= 60:
            return {
                "level": level, "kind": "sentences",
                "title": f"Sentence practice {level - 25}/24",
                "description": "Type 8 challenging sentences",
                "pools": ["hard"], "count": 8,
                "min_wpm": self.min_wpm(level), "is_test": False,
            }
        if level <= 70:
            return {
                "level": level, "kind": "paragraphs",
                "title": f"Short paragraphs {level - 60}/10",
                "description": "Type short paragraphs (~100 words)",
                "pools": ["medium"], "words": 90 + (level - 61) * 6,
                "min_wpm": self.min_wpm(level), "is_test": False,
            }
        return {
            "level": level, "kind": "paragraphs",
            "title": f"Longer paragraphs {level - 70}/4",
            "description": "Type longer paragraphs (~150 words)",
            "pools": ["medium", "hard"], "words": 130 + (level - 71) * 10,
            "min_wpm": self.min_wpm(level), "is_test": False,
        }

    def _paragraph_spec(self, level: int) -> dict:
        if level <= 84:
            return {
                "level": level, "kind": "paragraphs",
                "title": f"Paragraph practice {level - 75}/9",
                "description": "Type medium paragraphs (~160 words)",
                "pools": ["medium", "hard"], "words": 140 + (level - 76) * 6,
                "min_wpm": self.min_wpm(level), "is_test": False,
            }
        if level <= 94:
            return {
                "level": level, "kind": "paragraphs",
                "title": f"Paragraph practice {level - 75}/9",
                "description": "Type long paragraphs (~230 words)",
                "pools": ["hard"], "words": 200 + (level - 85) * 6,
                "min_wpm": self.min_wpm(level), "is_test": False,
            }
        return {
            "level": level, "kind": "paragraphs",
            "title": f"Marathon {level - 75}/9",
            "description": "Type a long paragraph (~300 words)",
            "pools": ["hard"], "words": 260 + (level - 95) * 10,
            "min_wpm": self.min_wpm(level), "is_test": False,
        }

    def _test_spec(self, level: int) -> dict:
        chapters = {25: 2, 50: 3, 75: 3, 100: 3}[level]
        titles = {
            25: "Final test 1: rows and words",
            50: "Final test 2: words and sentences",
            75: "Final test 3: sentences and paragraphs",
            100: "Grand final test: everything",
        }
        return {
            "level": level, "kind": "test",
            "title": titles[level],
            "description": "A balanced mix of everything you have learned so far",
            "chapters": chapters, "words": {25: 90, 50: 130, 75: 170, 100: 220}[level],
            "min_wpm": self.min_wpm(level), "is_test": True,
        }

    def _row_description(self, level: int, plan: dict) -> str:
        if level == 9:
            return "Capital letters and shifted symbols - hold Shift!"
        if level == 10:
            return "Punctuation marks mixed with common words"
        keys = " ".join(plan["new"].upper())
        return f"New keys: {keys} - mixed with keys you already know"
