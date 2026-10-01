"""Sound effects, generated on first run - fully offline.

The four short WAV files (key click, error buzz, level-complete chime and a
success arpeggio) are synthesised with the standard-library ``wave`` module,
so the repository ships no binary audio assets.  They are played through
``QSoundEffect`` (Qt Multimedia); if that module is unavailable the manager
degrades silently instead of crashing.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 22050

# (name, [(frequency_hz, duration_s, volume), ...]) - simple note sequences.
_SOUNDS = {
    "click":   [(1400.0, 0.035, 0.55)],
    "error":   [(190.0, 0.09, 0.50)],
    "success": [(880.0, 0.07, 0.55), (1174.7, 0.07, 0.55)],
    "complete": [(659.3, 0.09, 0.55), (830.6, 0.09, 0.55), (987.8, 0.14, 0.55)],
}


def _write_wav(path: Path, notes: list[tuple[float, float, float]]) -> None:
    """Render a sequence of decaying sine tones into a 16-bit mono WAV file."""
    frames = bytearray()
    for freq, duration, volume in notes:
        total = int(SAMPLE_RATE * duration)
        for i in range(total):
            t = i / SAMPLE_RATE
            envelope = math.exp(-t * (12.0 / duration))       # quick decay
            sample = math.sin(2.0 * math.pi * freq * t) * envelope * volume
            frames += struct.pack("<h", int(sample * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))


class SoundManager:
    """Creates (once) and plays the app's short sound effects."""

    def __init__(self, sounds_dir: Path, enabled: bool = True, volume: int = 60):
        self.dir = Path(sounds_dir)
        self.enabled = enabled
        self.volume = max(0, min(100, int(volume))) / 100.0
        self.available = False
        self._effects: dict[str, object] = {}
        try:
            self._ensure_files()
            self._load()
        except Exception:
            # Never let audio problems break the app.
            self.available = False

    # -- setup ---------------------------------------------------------------
    def _ensure_files(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        for name, notes in _SOUNDS.items():
            path = self.dir / f"{name}.wav"
            if not path.exists():
                _write_wav(path, notes)

    def _load(self) -> None:
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QSoundEffect
        except Exception:
            self.available = False
            return
        for name in _SOUNDS:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(self.dir / f"{name}.wav")))
            effect.setVolume(self.volume)
            self._effects[name] = effect
        self.available = True

    # -- playback --------------------------------------------------------------
    def play(self, name: str) -> None:
        if not self.enabled or not self.available:
            return
        effect = self._effects.get(name)
        if effect is None:
            return
        try:
            effect.play()
        except Exception:
            pass

    # -- settings ----------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume))) / 100.0
        for effect in self._effects.values():
            try:
                effect.setVolume(self.volume)
            except Exception:
                pass
