"""
Tests — src.pipeline.transcribe
SDD-004 testing requirements

All Basic Pitch calls are mocked — no model weights needed.  Tests run in
both .venv (Python 3.13) and .venv-ml (Python 3.11).

Coverage map:

    TC-TRX-001  Valid 6-stem input → returns dict with all 6 keys
    TC-TRX-002  Drum stem routed to DrumTranscriber, not Basic Pitch
    TC-TRX-003  Non-drum stems call Basic Pitch predict
    TC-TRX-004  Custom DrumTranscriber instance is used when provided
    TC-TRX-005  Basic Pitch failure → TranscribeError with __cause__ chained
    TC-TRX-006  Temp files cleaned up on success
    TC-TRX-007  Temp files cleaned up on failure
    TC-TRX-008  Wrong input type → TranscribeError
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

try:
    import pretty_midi  # noqa: F401
    HAS_PRETTY_MIDI = True
except ModuleNotFoundError:
    HAS_PRETTY_MIDI = False

requires_pretty_midi = pytest.mark.skipif(
    not HAS_PRETTY_MIDI,
    reason="pretty_midi not installed (run in .venv-ml)",
)

from src.pipeline.transcribe import TranscribeError, transcribe


# ── Fixtures and helpers ──────────────────────────────────────────────────────

SR = 44_100
N = SR * 2  # 2 seconds
STEM_NAMES = ("drums", "bass", "vocals", "other", "piano", "guitar")


def _make_stems(names: tuple[str, ...] = STEM_NAMES) -> dict[str, np.ndarray]:
    """Synthetic 6-stem dict matching the separate stage output contract."""
    return {name: np.zeros((2, N), dtype=np.float32) for name in names}


def _mock_predict(audio_path, model_path, **kwargs):
    """Return a fake Basic Pitch predict result with a mock PrettyMIDI."""
    mock_midi = MagicMock()
    return (MagicMock(), mock_midi, [])


class FakeDrumTranscriber:
    """Test double for DrumTranscriber — records calls."""

    def __init__(self):
        self.calls: list[tuple] = []

    def transcribe(self, stem, sr=44_100):
        self.calls.append((stem, sr))
        return MagicMock()


class FailingDrumTranscriber:
    """DrumTranscriber that always raises."""

    def transcribe(self, stem, sr=44_100):
        raise RuntimeError("drum hardware on fire")


@pytest.fixture()
def _patch_basic_pitch():
    """
    Ensure basic_pitch is importable as a mock module, even in .venv where
    the real package is not installed.  Patches sys.modules for the duration
    of the test.
    """
    fake_inference = types.ModuleType("basic_pitch.inference")
    fake_inference.predict = MagicMock(side_effect=_mock_predict)

    fake_bp = types.ModuleType("basic_pitch")
    fake_bp.ICASSP_2022_MODEL_PATH = "fake_model_path"
    fake_bp.inference = fake_inference

    with patch.dict(sys.modules, {
        "basic_pitch": fake_bp,
        "basic_pitch.inference": fake_inference,
    }):
        yield fake_inference


# ── TC-TRX-001  All 6 stem keys returned ─────────────────────────────────────

def test_all_six_stem_keys_returned(_patch_basic_pitch):
    stems = _make_stems()
    fake_drums = FakeDrumTranscriber()

    result = transcribe(stems, drum_transcriber=fake_drums)
    assert set(result.keys()) == set(STEM_NAMES)


# ── TC-TRX-002  Drum stem routed to DrumTranscriber ──────────────────────────

def test_drum_stem_uses_drum_transcriber(_patch_basic_pitch):
    stems = _make_stems()
    fake_drums = FakeDrumTranscriber()

    transcribe(stems, drum_transcriber=fake_drums)

    assert len(fake_drums.calls) == 1
    np.testing.assert_array_equal(fake_drums.calls[0][0], stems["drums"])


# ── TC-TRX-003  Non-drum stems call Basic Pitch ──────────────────────────────

def test_non_drum_stems_call_basic_pitch(_patch_basic_pitch):
    stems = _make_stems()
    fake_drums = FakeDrumTranscriber()

    transcribe(stems, drum_transcriber=fake_drums)

    # 5 non-drum stems should each call predict once
    assert _patch_basic_pitch.predict.call_count == 5


# ── TC-TRX-004  Custom DrumTranscriber is used ───────────────────────────────

def test_custom_drum_transcriber_used():
    stems = {"drums": np.zeros((2, N), dtype=np.float32)}
    custom = FakeDrumTranscriber()

    result = transcribe(stems, drum_transcriber=custom)

    assert len(custom.calls) == 1
    assert "drums" in result


# ── TC-TRX-005  Basic Pitch failure → TranscribeError with __cause__ ─────────

def test_basic_pitch_failure_raises_transcribe_error():
    stems = {"bass": np.zeros((2, N), dtype=np.float32)}
    original = RuntimeError("model exploded")

    fake_inference = types.ModuleType("basic_pitch.inference")
    fake_inference.predict = MagicMock(side_effect=original)

    fake_bp = types.ModuleType("basic_pitch")
    fake_bp.ICASSP_2022_MODEL_PATH = "fake_model_path"
    fake_bp.inference = fake_inference

    with patch.dict(sys.modules, {
        "basic_pitch": fake_bp,
        "basic_pitch.inference": fake_inference,
    }):
        with pytest.raises(TranscribeError) as exc_info:
            transcribe(stems)

    assert exc_info.value.__cause__ is original


# ── TC-TRX-006  Temp files cleaned up on success ─────────────────────────────

def test_temp_files_cleaned_on_success():
    stems = {"bass": np.zeros((2, N), dtype=np.float32)}
    created_files: list[str] = []

    def tracking_predict(audio_path, model_path, **kwargs):
        created_files.append(audio_path)
        assert os.path.exists(audio_path), "temp file should exist during predict"
        return _mock_predict(audio_path, model_path)

    fake_inference = types.ModuleType("basic_pitch.inference")
    fake_inference.predict = MagicMock(side_effect=tracking_predict)

    fake_bp = types.ModuleType("basic_pitch")
    fake_bp.ICASSP_2022_MODEL_PATH = "fake_model_path"
    fake_bp.inference = fake_inference

    with patch.dict(sys.modules, {
        "basic_pitch": fake_bp,
        "basic_pitch.inference": fake_inference,
    }):
        transcribe(stems)

    for f in created_files:
        assert not os.path.exists(f), f"temp file should be deleted: {f}"


# ── TC-TRX-007  Temp files cleaned up on failure ─────────────────────────────

def test_temp_files_cleaned_on_failure():
    stems = {"bass": np.zeros((2, N), dtype=np.float32)}
    created_files: list[str] = []

    def failing_predict(audio_path, model_path, **kwargs):
        created_files.append(audio_path)
        raise RuntimeError("kaboom")

    fake_inference = types.ModuleType("basic_pitch.inference")
    fake_inference.predict = MagicMock(side_effect=failing_predict)

    fake_bp = types.ModuleType("basic_pitch")
    fake_bp.ICASSP_2022_MODEL_PATH = "fake_model_path"
    fake_bp.inference = fake_inference

    with patch.dict(sys.modules, {
        "basic_pitch": fake_bp,
        "basic_pitch.inference": fake_inference,
    }):
        with pytest.raises(TranscribeError):
            transcribe(stems)

    for f in created_files:
        assert not os.path.exists(f), f"temp file should be deleted on failure: {f}"


# ── TC-TRX-008  Wrong input type → TranscribeError ──────────────────────────

def test_wrong_input_type_raises():
    with pytest.raises(TranscribeError, match="expected dict"):
        transcribe("not a dict")  # type: ignore[arg-type]


def test_wrong_stem_value_type_raises():
    with pytest.raises(TranscribeError, match="expected np.ndarray"):
        transcribe({"bass": "not an array"})  # type: ignore[dict-item]


# ── TC-TRX-009  Drum transcriber failure → TranscribeError ───────────────────

def test_drum_transcriber_failure_raises():
    stems = {"drums": np.zeros((2, N), dtype=np.float32)}
    failing = FailingDrumTranscriber()

    with pytest.raises(TranscribeError, match="drum transcription failed") as exc_info:
        transcribe(stems, drum_transcriber=failing)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
