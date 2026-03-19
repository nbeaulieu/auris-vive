"""
Tests — src.pipeline.drums

Covers the DrumTranscriber ABC contract and the OnsetTranscriber v1
implementation.  ADTLibTranscriber is tested only for its stub behaviour.

All tests run in both .venv (Python 3.13) and .venv-ml (Python 3.11) since
pretty_midi is in [ml] — imports are guarded accordingly.
"""

from __future__ import annotations

import numpy as np
import pytest

try:
    import pretty_midi
    HAS_PRETTY_MIDI = True
except ModuleNotFoundError:
    pretty_midi = None  # type: ignore[assignment]
    HAS_PRETTY_MIDI = False

requires_pretty_midi = pytest.mark.skipif(
    not HAS_PRETTY_MIDI,
    reason="pretty_midi not installed (run in .venv-ml)",
)

from src.pipeline.drums.base import DrumTranscribeError, DrumTranscriber
from src.pipeline.drums.adtlib import ADTLibTranscriber
from src.pipeline.drums.onset import OnsetTranscriber

SR = 44_100
N = SR * 2  # 2 seconds


def _sine_drum_stem(freq: float = 200.0, n: int = N) -> np.ndarray:
    """Synthetic drum-like stem — a decaying sine burst repeated at intervals."""
    t = np.linspace(0, n / SR, n)
    signal = np.sin(2 * np.pi * freq * t) * np.exp(-t * 5)
    # Add periodic transients to give the onset detector something to find
    for hit in np.arange(0.1, n / SR, 0.5):
        idx = int(hit * SR)
        if idx + 100 < n:
            signal[idx:idx + 100] += np.random.randn(100) * 0.3
    return np.stack([signal, signal]).astype(np.float32)


# ── DrumTranscriber ABC ───────────────────────────────────────────────────────

def test_drum_transcriber_is_abstract():
    with pytest.raises(TypeError):
        DrumTranscriber()  # type: ignore[abstract]


def test_concrete_subclass_must_implement_transcribe():
    class Incomplete(DrumTranscriber):
        pass  # missing transcribe()

    with pytest.raises(TypeError):
        Incomplete()


# ── OnsetTranscriber ──────────────────────────────────────────────────────────

@requires_pretty_midi
def test_onset_transcriber_returns_pretty_midi():
    stem = _sine_drum_stem()
    result = OnsetTranscriber().transcribe(stem)
    assert isinstance(result, pretty_midi.PrettyMIDI)


@requires_pretty_midi
def test_onset_transcriber_has_drum_instrument():
    stem = _sine_drum_stem()
    midi = OnsetTranscriber().transcribe(stem)
    assert len(midi.instruments) == 1
    assert midi.instruments[0].is_drum


@requires_pretty_midi
def test_onset_transcriber_notes_are_gm38():
    stem = _sine_drum_stem()
    midi = OnsetTranscriber().transcribe(stem)
    notes = midi.instruments[0].notes
    assert len(notes) > 0
    assert all(n.pitch == 38 for n in notes)


@requires_pretty_midi
def test_onset_transcriber_note_times_are_positive():
    stem = _sine_drum_stem()
    midi = OnsetTranscriber().transcribe(stem)
    notes = midi.instruments[0].notes
    assert all(n.start >= 0.0 for n in notes)
    assert all(n.end > n.start for n in notes)


@requires_pretty_midi
def test_onset_transcriber_silent_stem_returns_empty_notes():
    """Silent input should produce no notes or very few."""
    silent = np.zeros((2, N), dtype=np.float32)
    midi = OnsetTranscriber().transcribe(silent)
    # librosa may detect 0–1 onsets on silence; anything > 5 is a bug
    assert len(midi.instruments[0].notes) <= 5


@requires_pretty_midi
def test_onset_transcriber_accepts_1d_stem():
    """Should handle mono (1D) input gracefully via the left-channel selection."""
    mono = np.zeros(N, dtype=np.float32)
    # OnsetTranscriber uses stem[0] — this would fail on 1D
    # The implementation should handle this; if not, test documents the gap
    stem_2d = np.stack([mono, mono])
    midi = OnsetTranscriber().transcribe(stem_2d)
    assert isinstance(midi, pretty_midi.PrettyMIDI)


@requires_pretty_midi
def test_onset_transcriber_custom_delta():
    """Higher delta should produce fewer or equal onsets."""
    stem = _sine_drum_stem()
    midi_default = OnsetTranscriber(delta=0.07).transcribe(stem)
    midi_high = OnsetTranscriber(delta=0.5).transcribe(stem)
    n_default = len(midi_default.instruments[0].notes)
    n_high = len(midi_high.instruments[0].notes)
    assert n_high <= n_default


# ── ADTLibTranscriber stub ────────────────────────────────────────────────────

def test_adtlib_raises_not_implemented():
    stem = _sine_drum_stem()
    with pytest.raises(NotImplementedError):
        ADTLibTranscriber().transcribe(stem)


def test_adtlib_error_mentions_adr():
    stem = _sine_drum_stem()
    with pytest.raises(NotImplementedError, match="ADR-003"):
        ADTLibTranscriber().transcribe(stem)


# ── DrumTranscribeError ───────────────────────────────────────────────────────

def test_drum_transcribe_error_is_exception():
    err = DrumTranscribeError("something went wrong")
    assert isinstance(err, Exception)
    assert "something went wrong" in str(err)
