"""
Test suite — src/pipeline/ingest.py
SDD-002 testing requirements

Coverage map (matches SDD-002 §7 test table):

    TC-ING-001  Stereo WAV at 44100 Hz → correct shape, dtype, value range
    TC-ING-002  Mono WAV → channels duplicated, both channels identical
    TC-ING-003  4-channel WAV → first two channels preserved, rest discarded
    TC-ING-004  Stereo WAV at 48000 Hz → resampled to 44100 Hz
    TC-ING-005  Pre-clipped audio (peak > 1.0) → clipped, warning logged
    TC-ING-006  Audio < 1s → IngestError "too short"
    TC-ING-007  Corrupt / undecodable file → IngestError
    TC-ING-008  Missing file path → IngestError "not found"
    TC-ING-009  NaN in decoded audio → IngestError "non-finite"
    TC-ING-010  Channel-last layout (N, C) → transposed correctly
    TC-ING-011  Missing FFmpeg backend → IngestError, message names FFmpeg
    TC-ING-012  Any valid input → full output contract satisfied

Unit tests for each internal function are in TestToStereo, TestNormalise,
TestValidate at the bottom.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from src.pipeline.ingest import (
    IngestError,
    MIN_DURATION_S,
    TARGET_SR,
    _normalise,
    _to_stereo,
    _validate,
    load,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sine(freq_hz: float, duration_s: float, sr: int = TARGET_SR, amp: float = 0.5) -> np.ndarray:
    """Return a mono float32 sine wave, shape (N,)."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return (np.sin(2 * np.pi * freq_hz * t) * amp).astype(np.float32)


def _write_wav(path: Path, audio: np.ndarray, sr: int = TARGET_SR) -> None:
    """
    Write audio to a WAV file via soundfile.

    Accepts:
        (N,)   mono
        (C, N) channel-first, C channels
    soundfile expects channel-last (N, C), so we transpose when needed.
    """
    if audio.ndim == 1:
        sf.write(str(path), audio, sr, subtype="PCM_16")
    else:
        # (C, N) → (N, C)
        sf.write(str(path), audio.T, sr, subtype="PCM_16")


def _fake_path(tmp_path: Path, name: str = "fake.wav") -> Path:
    """Create an empty file so _resolve_path passes; decode is mocked."""
    p = tmp_path / name
    p.touch()
    return p


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def stereo_wav(tmp_path: Path) -> Path:
    left = _sine(440, 2.0)
    right = _sine(880, 2.0)
    p = tmp_path / "stereo_44100.wav"
    _write_wav(p, np.stack([left, right]))
    return p


@pytest.fixture
def mono_wav(tmp_path: Path) -> Path:
    p = tmp_path / "mono_44100.wav"
    _write_wav(p, _sine(440, 2.0))
    return p


@pytest.fixture
def four_channel_wav(tmp_path: Path) -> Path:
    channels = np.stack([_sine(220 * (i + 1), 2.0) for i in range(4)])  # (4, N)
    p = tmp_path / "4ch_44100.wav"
    _write_wav(p, channels)
    return p


@pytest.fixture
def wav_48k(tmp_path: Path) -> Path:
    sr = 48_000
    left = _sine(440, 2.0, sr=sr)
    right = _sine(880, 2.0, sr=sr)
    p = tmp_path / "stereo_48000.wav"
    _write_wav(p, np.stack([left, right]), sr=sr)
    return p


@pytest.fixture
def short_wav(tmp_path: Path) -> Path:
    """0.5 s — below MIN_DURATION_S."""
    p = tmp_path / "short.wav"
    _write_wav(p, _sine(440, 0.5))
    return p


@pytest.fixture
def corrupt_file(tmp_path: Path) -> Path:
    p = tmp_path / "corrupt.wav"
    # Valid RIFF header magic, then garbage — soundfile / audioread will fail
    p.write_bytes(b"RIFF\x10\x00\x00\x00WAVEfmt \xff\xff\xff\xff\x00\x00\x00\x00")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-001  Stereo WAV at 44100 Hz
# ─────────────────────────────────────────────────────────────────────────────

def test_stereo_wav_shape(stereo_wav: Path):
    audio = load(stereo_wav)
    assert audio.ndim == 2
    assert audio.shape[0] == 2


def test_stereo_wav_dtype(stereo_wav: Path):
    assert load(stereo_wav).dtype == np.float32


def test_stereo_wav_sample_count(stereo_wav: Path):
    # 2 s at 44100 Hz → 88200 samples ± 1 %
    n = load(stereo_wav).shape[1]
    assert abs(n - TARGET_SR * 2) < TARGET_SR * 0.01


def test_stereo_wav_values_in_range(stereo_wav: Path):
    audio = load(stereo_wav)
    assert float(np.max(audio)) <= 1.0
    assert float(np.min(audio)) >= -1.0


def test_stereo_wav_finite(stereo_wav: Path):
    assert np.all(np.isfinite(load(stereo_wav)))


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-002  Mono → channel duplication
# ─────────────────────────────────────────────────────────────────────────────

def test_mono_becomes_two_channels(mono_wav: Path):
    assert load(mono_wav).shape[0] == 2


def test_mono_channels_are_identical(mono_wav: Path):
    audio = load(mono_wav)
    np.testing.assert_array_equal(audio[0], audio[1])


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-003  4-channel → first two channels
# ─────────────────────────────────────────────────────────────────────────────

def test_four_channel_becomes_stereo(four_channel_wav: Path):
    assert load(four_channel_wav).shape[0] == 2


def test_four_channel_correct_channels_preserved(four_channel_wav: Path, tmp_path: Path):
    """Channels 0 and 1 of the source should be the output channels."""
    import librosa as _librosa

    # Load raw to get original channel data before ingest resampling/clipping
    raw, _ = _librosa.load(str(four_channel_wav), sr=None, mono=False, dtype=np.float32)
    audio = load(four_channel_wav)

    # After resampling and normalising, channels should still track ch0/ch1
    # We verify sign (polarity) rather than exact values, because resampling
    # introduces minor floating-point differences.
    correlation_ch0 = float(np.corrcoef(audio[0], raw[0, : audio.shape[1]])[0, 1])
    correlation_ch1 = float(np.corrcoef(audio[1], raw[1, : audio.shape[1]])[0, 1])
    assert correlation_ch0 > 0.99
    assert correlation_ch1 > 0.99


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-004  Non-44100 Hz → resampled
# ─────────────────────────────────────────────────────────────────────────────

def test_48k_resampled_sample_count(wav_48k: Path):
    # Source: 2 s at 48000 Hz → 88200 samples at 44100 Hz
    n = load(wav_48k).shape[1]
    assert abs(n - TARGET_SR * 2) < TARGET_SR * 0.01


def test_48k_output_dtype(wav_48k: Path):
    assert load(wav_48k).dtype == np.float32


def test_48k_output_channels(wav_48k: Path):
    assert load(wav_48k).shape[0] == 2


def test_48k_output_values_in_range(wav_48k: Path):
    audio = load(wav_48k)
    assert float(np.max(audio)) <= 1.0
    assert float(np.min(audio)) >= -1.0


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-005  Pre-clipped audio
# ─────────────────────────────────────────────────────────────────────────────

def test_overdriven_audio_clipped_to_contract(tmp_path: Path):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    overdrive = np.full((2, n), 1.5, dtype=np.float32)

    with patch("librosa.load", return_value=(overdrive, TARGET_SR)):
        audio = load(fake)

    assert float(np.max(audio)) <= 1.0
    assert float(np.min(audio)) >= -1.0


def test_overdriven_audio_does_not_raise(tmp_path: Path):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    overdrive = np.full((2, n), 1.5, dtype=np.float32)

    with patch("librosa.load", return_value=(overdrive, TARGET_SR)):
        load(fake)  # must not raise


def test_overdriven_audio_logs_warning(tmp_path: Path, caplog):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    overdrive = np.full((2, n), 1.5, dtype=np.float32)

    with caplog.at_level(logging.WARNING, logger="src.pipeline.ingest"):
        with patch("librosa.load", return_value=(overdrive, TARGET_SR)):
            load(fake)

    messages = [r.message.lower() for r in caplog.records]
    assert any("pre-clipped" in m or "clipping" in m for m in messages)


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-006  Too short
# ─────────────────────────────────────────────────────────────────────────────

def test_short_audio_raises_ingest_error(short_wav: Path):
    with pytest.raises(IngestError):
        load(short_wav)


def test_short_audio_error_message_mentions_duration(short_wav: Path):
    with pytest.raises(IngestError, match="too short"):
        load(short_wav)


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-007  Corrupt file
# ─────────────────────────────────────────────────────────────────────────────

def test_corrupt_file_raises_ingest_error(corrupt_file: Path):
    with pytest.raises(IngestError):
        load(corrupt_file)


def test_corrupt_file_does_not_raise_raw_librosa_exception(corrupt_file: Path):
    """The domain exception must wrap; no internal exception should escape."""
    try:
        load(corrupt_file)
    except IngestError:
        pass
    except Exception as exc:
        pytest.fail(f"Raw exception escaped ingest boundary: {type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-008  Missing file
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_file_raises_ingest_error(tmp_path: Path):
    with pytest.raises(IngestError):
        load(tmp_path / "does_not_exist.wav")


def test_missing_file_error_message_mentions_not_found(tmp_path: Path):
    with pytest.raises(IngestError, match="not found"):
        load(tmp_path / "does_not_exist.wav")


def test_path_is_directory_raises(tmp_path: Path):
    with pytest.raises(IngestError):
        load(tmp_path)  # tmp_path itself is a directory


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-009  NaN / ±inf in decoded audio
# ─────────────────────────────────────────────────────────────────────────────

def test_nan_audio_raises_ingest_error(tmp_path: Path):
    fake = _fake_path(tmp_path, "nan.wav")
    nan_audio = np.full((2, TARGET_SR * 2), np.nan, dtype=np.float32)

    with pytest.raises(IngestError, match="non-finite"):
        with patch("librosa.load", return_value=(nan_audio, TARGET_SR)):
            load(fake)


def test_inf_audio_raises_ingest_error(tmp_path: Path):
    fake = _fake_path(tmp_path, "inf.wav")
    inf_audio = np.full((2, TARGET_SR * 2), np.inf, dtype=np.float32)

    with pytest.raises(IngestError, match="non-finite"):
        with patch("librosa.load", return_value=(inf_audio, TARGET_SR)):
            load(fake)


def test_neg_inf_audio_raises_ingest_error(tmp_path: Path):
    fake = _fake_path(tmp_path, "neginf.wav")
    audio = np.zeros((2, TARGET_SR * 2), dtype=np.float32)
    audio[1, 500] = -np.inf

    with pytest.raises(IngestError, match="non-finite"):
        with patch("librosa.load", return_value=(audio, TARGET_SR)):
            load(fake)


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-010  Channel-last layout
# ─────────────────────────────────────────────────────────────────────────────

def test_channel_last_stereo_shape(tmp_path: Path):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    channel_last = np.random.randn(n, 2).astype(np.float32) * 0.5

    with patch("librosa.load", return_value=(channel_last, TARGET_SR)):
        audio = load(fake)

    assert audio.shape == (2, n)


def test_channel_last_mono_duplicated(tmp_path: Path):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    channel_last_mono = np.random.randn(n, 1).astype(np.float32) * 0.5

    with patch("librosa.load", return_value=(channel_last_mono, TARGET_SR)):
        audio = load(fake)

    assert audio.shape[0] == 2
    np.testing.assert_array_equal(audio[0], audio[1])


def test_channel_last_four_channel_takes_first_two(tmp_path: Path):
    fake = _fake_path(tmp_path)
    n = TARGET_SR * 2
    quad_cl = np.random.randn(n, 4).astype(np.float32) * 0.5

    with patch("librosa.load", return_value=(quad_cl, TARGET_SR)):
        audio = load(fake)

    assert audio.shape[0] == 2
    # Channel 0 of output should match first column of channel-last input
    np.testing.assert_array_almost_equal(audio[0], np.clip(quad_cl[:, 0], -1, 1))


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-011  Missing FFmpeg backend
# ─────────────────────────────────────────────────────────────────────────────

def test_no_backend_raises_ingest_error(tmp_path: Path):
    fake = _fake_path(tmp_path, "track.mp3")

    class _NoBackendError(Exception):
        """Simulates audioread.NoBackendError."""

    _NoBackendError.__name__ = "NoBackendError"
    _NoBackendError.__qualname__ = "NoBackendError"

    with patch("librosa.load", side_effect=_NoBackendError("no backend available")):
        with pytest.raises(IngestError):
            load(fake)


def test_no_backend_error_message_actionable(tmp_path: Path):
    fake = _fake_path(tmp_path, "track.mp3")

    class _NoBackendError(Exception):
        pass

    _NoBackendError.__name__ = "NoBackendError"

    with patch("librosa.load", side_effect=_NoBackendError("no backend available")):
        with pytest.raises(IngestError) as exc_info:
            load(fake)

    msg = str(exc_info.value).lower()
    # Error must mention the remedy, not just echo the librosa internals
    assert "ffmpeg" in msg or "backend" in msg


def test_ffmpeg_in_error_message_triggers_backend_path(tmp_path: Path):
    fake = _fake_path(tmp_path, "track.m4a")

    with patch(
        "librosa.load",
        side_effect=RuntimeError("could not find ffmpeg on PATH"),
    ):
        with pytest.raises(IngestError) as exc_info:
            load(fake)

    assert "ffmpeg" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-ING-012  Full output contract satisfied for all valid inputs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture_name", ["stereo_wav", "mono_wav", "four_channel_wav", "wav_48k"])
def test_full_contract(fixture_name: str, request: pytest.FixtureRequest):
    path = request.getfixturevalue(fixture_name)
    audio = load(path)

    # Shape
    assert audio.ndim == 2, "must be 2-D"
    assert audio.shape[0] == 2, "must have exactly 2 channels"
    assert audio.shape[1] > 0, "must have at least one sample"

    # dtype
    assert audio.dtype == np.float32, "must be float32"

    # Range
    assert float(np.max(audio)) <= 1.0, "max must be ≤ 1.0"
    assert float(np.min(audio)) >= -1.0, "min must be ≥ -1.0"

    # Finite
    assert np.all(np.isfinite(audio)), "must contain no NaN or ±inf"

    # Duration
    duration_s = audio.shape[1] / TARGET_SR
    assert duration_s >= MIN_DURATION_S, f"must be ≥ {MIN_DURATION_S}s"


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: _to_stereo
# ─────────────────────────────────────────────────────────────────────────────

class TestToStereo:
    def test_1d_mono_duplicated(self):
        mono = np.ones(1000, dtype=np.float32)
        out = _to_stereo(mono)
        assert out.shape == (2, 1000)
        np.testing.assert_array_equal(out[0], out[1])

    def test_2d_stereo_channel_first_passthrough(self):
        stereo = np.ones((2, 1000), dtype=np.float32)
        assert _to_stereo(stereo).shape == (2, 1000)

    def test_2d_mono_1xN_duplicated(self):
        mono = np.ones((1, 1000), dtype=np.float32)
        out = _to_stereo(mono)
        assert out.shape == (2, 1000)
        np.testing.assert_array_equal(out[0], out[1])

    def test_quad_takes_first_two(self):
        quad = np.arange(4 * 1000, dtype=np.float32).reshape(4, 1000)
        out = _to_stereo(quad)
        assert out.shape == (2, 1000)
        np.testing.assert_array_equal(out[0], quad[0])
        np.testing.assert_array_equal(out[1], quad[1])

    def test_channel_last_stereo_transposed(self):
        cl = np.ones((44100, 2), dtype=np.float32)
        out = _to_stereo(cl)
        assert out.shape == (2, 44100)

    def test_channel_last_mono_duplicated(self):
        cl_mono = np.ones((44100, 1), dtype=np.float32)
        out = _to_stereo(cl_mono)
        assert out.shape == (2, 44100)
        np.testing.assert_array_equal(out[0], out[1])

    def test_3d_raises(self):
        bad = np.ones((2, 100, 100), dtype=np.float32)
        with pytest.raises(IngestError):
            _to_stereo(bad)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: _normalise
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalise:
    def _path(self, tmp_path: Path) -> Path:
        return tmp_path / "x.wav"

    def test_float32_unchanged(self, tmp_path: Path):
        audio = np.random.uniform(-0.5, 0.5, (2, 1000)).astype(np.float32)
        out = _normalise(audio, self._path(tmp_path))
        assert out.dtype == np.float32

    def test_float64_converted(self, tmp_path: Path):
        audio = np.random.uniform(-0.5, 0.5, (2, 1000)).astype(np.float64)
        out = _normalise(audio, self._path(tmp_path))
        assert out.dtype == np.float32

    def test_overdrive_clipped_above(self, tmp_path: Path):
        audio = np.full((2, 1000), 2.0, dtype=np.float32)
        out = _normalise(audio, self._path(tmp_path))
        assert float(np.max(out)) == pytest.approx(1.0)

    def test_overdrive_clipped_below(self, tmp_path: Path):
        audio = np.full((2, 1000), -2.0, dtype=np.float32)
        out = _normalise(audio, self._path(tmp_path))
        assert float(np.min(out)) == pytest.approx(-1.0)

    def test_in_range_values_preserved(self, tmp_path: Path):
        audio = np.random.uniform(-0.5, 0.5, (2, 1000)).astype(np.float32)
        out = _normalise(audio, self._path(tmp_path))
        np.testing.assert_array_almost_equal(out, audio)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: _validate
# ─────────────────────────────────────────────────────────────────────────────

class TestValidate:
    def _path(self, tmp_path: Path) -> Path:
        return tmp_path / "x.wav"

    def _valid(self) -> np.ndarray:
        return np.random.uniform(-0.5, 0.5, (2, TARGET_SR * 2)).astype(np.float32)

    def test_valid_audio_passes(self, tmp_path: Path):
        _validate(self._valid(), self._path(tmp_path))  # no raise

    def test_wrong_channel_count_raises(self, tmp_path: Path):
        bad = np.ones((3, TARGET_SR * 2), dtype=np.float32)
        with pytest.raises(IngestError):
            _validate(bad, self._path(tmp_path))

    def test_1d_array_raises(self, tmp_path: Path):
        bad = np.ones(TARGET_SR * 2, dtype=np.float32)
        with pytest.raises(IngestError):
            _validate(bad, self._path(tmp_path))

    def test_wrong_dtype_raises(self, tmp_path: Path):
        bad = np.ones((2, TARGET_SR * 2), dtype=np.float64)
        with pytest.raises(IngestError):
            _validate(bad, self._path(tmp_path))

    def test_nan_raises(self, tmp_path: Path):
        audio = self._valid()
        audio[0, 100] = np.nan
        with pytest.raises(IngestError, match="non-finite"):
            _validate(audio, self._path(tmp_path))

    def test_inf_raises(self, tmp_path: Path):
        audio = self._valid()
        audio[1, 50] = np.inf
        with pytest.raises(IngestError, match="non-finite"):
            _validate(audio, self._path(tmp_path))

    def test_too_short_raises(self, tmp_path: Path):
        short = np.ones((2, int(TARGET_SR * 0.5)), dtype=np.float32)
        with pytest.raises(IngestError, match="too short"):
            _validate(short, self._path(tmp_path))

    def test_exactly_min_duration_passes(self, tmp_path: Path):
        exactly = np.zeros((2, TARGET_SR), dtype=np.float32)  # exactly 1.0 s
        _validate(exactly, self._path(tmp_path))  # no raise
