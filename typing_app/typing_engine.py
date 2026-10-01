"""Typing engine: character-by-character state machine for one lesson.

The UI (``ui/typing_page.py``) drives this class with ``press()`` /
``backspace()`` calls and paints ``char_states()``.  Keeping the logic here,
free of Qt, makes it unit-testable.

Metrics follow the usual conventions:
* WPM       = (correct characters / 5) / minutes      (a "word" = 5 chars)
* accuracy  = correct keystrokes / total keystrokes * 100
* errors    = keystrokes that did not match the expected character
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# Character states used by the renderer.
UNTYPED, CORRECT, WRONG = 0, 1, 2


@dataclass
class TypingResult:
    """Final outcome of one lesson attempt."""
    wpm: float = 0.0
    accuracy: float = 0.0
    errors: int = 0
    correct: int = 0
    typed: int = 0
    chars: int = 0
    duration: float = 0.0
    finished: bool = False
    weak_keys: dict = field(default_factory=dict)   # key -> {"errors", "typed"}
    weak_words: dict = field(default_factory=dict)  # word -> errors


class TypingEngine:
    """Tracks progress through ``text`` and computes live statistics."""

    def __init__(self, text: str, clock=None):
        self.text = text
        self._clock = clock or time.monotonic   # injectable for tests
        self.length = len(text)
        self.pos = 0                     # index of the next expected character
        self.states = [UNTYPED] * self.length
        self.errors = 0                  # wrong keystrokes (never reduced)
        self.correct = 0                 # right keystrokes
        self.started_at: float | None = None
        self.ended_at: float | None = None
        self.key_stats: dict[str, dict] = {}   # per-key {"errors", "typed"}
        self.word_errors: dict[str, int] = {}  # word -> mistakes inside it
        self._word_start = 0             # index where the current word began

    # -- state ---------------------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.pos >= self.length

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at if self.ended_at is not None else self._clock()
        return max(0.0, end - self.started_at)

    @property
    def next_char(self) -> str | None:
        return self.text[self.pos] if self.pos < self.length else None

    # -- input ---------------------------------------------------------------
    def press(self, char: str) -> None:
        """Handle one typed character."""
        if self.finished or not char:
            return
        if self.started_at is None:
            self.started_at = self._clock()

        expected = self.text[self.pos]
        key = _key_name(expected)
        stats = self.key_stats.setdefault(key, {"errors": 0, "typed": 0})
        stats["typed"] += 1

        if char == expected:
            self.states[self.pos] = CORRECT
            self.correct += 1
        else:
            self.states[self.pos] = WRONG
            self.errors += 1
            stats["errors"] += 1
        self.pos += 1
        self._track_word(expected)
        if self.finished:
            self.ended_at = self._clock()

    def backspace(self) -> None:
        """Step back one character (keystroke counters stay as they were)."""
        if self.pos <= 0 or self.started_at is None:
            return
        self.pos -= 1
        self.states[self.pos] = UNTYPED
        self.ended_at = None

    def _track_word(self, expected: str) -> None:
        """Record a finished word if it contained a mistake."""
        boundary = expected in " \n"
        if boundary or self.finished:
            end = self.pos - 1 if boundary else self.pos
            if end > self._word_start:
                word = self.text[self._word_start:end].strip().lower()
                if word and WRONG in self.states[self._word_start:end]:
                    self.word_errors[word] = self.word_errors.get(word, 0) + 1
            self._word_start = self.pos

    # -- metrics ---------------------------------------------------------------
    def live_wpm(self) -> float:
        minutes = self.elapsed / 60.0
        if minutes <= 0:
            return 0.0
        return (self.correct / 5.0) / minutes

    def live_accuracy(self) -> float:
        total = self.correct + self.errors
        if total == 0:
            return 100.0
        return self.correct / total * 100.0

    def progress(self) -> float:
        return self.pos / self.length if self.length else 1.0

    def result(self) -> TypingResult:
        return TypingResult(
            wpm=self.live_wpm(),
            accuracy=self.live_accuracy(),
            errors=self.errors,
            correct=self.correct,
            typed=self.correct + self.errors,
            chars=self.length,
            duration=self.elapsed,
            finished=self.finished,
            weak_keys=dict(self.key_stats),
            weak_words=dict(self.word_errors),
        )


def _key_name(char: str) -> str:
    """Normalise a character to the physical key it belongs to.

    'A' -> 'a' (same key, just shifted), everything else stays as-is so the
    weak-key heat-map aggregates shifted and unshifted presses together.
    """
    return char.lower() if char.isalpha() else char
