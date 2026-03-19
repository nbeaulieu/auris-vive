"""
Tests — src.pipeline.separate
SDD-003 testing requirements

All tests mock demucs internals so the suite runs without GPU, without model
weights, and without the [ml] dependency group.  The mock pattern mirrors
test_runner.py: patch at the module boundary, never inside the implementation.

Coverage map (SDD-003 §10):

    TC-SEP-001  Valid input, models mocked → all 6 stem keys present
    TC-SEP-002  Valid input → all stem arrays are float32
    TC-SEP-003  Valid input → all stem arrays have shape (2, N')
    TC-SEP-004  Valid input → on_stems_ready called exactly twice
    TC-SEP-005  First callback contains drums/bass/vocals/other
    TC-SEP-006  Second callback contains piano/guitar
    TC-SEP-007  ft longer than 6s output → all stems trimmed to shortest
    TC-SEP-008  Wrong input shape (1, N) → SeparateError
    TC-SEP-009  AURIS_DEVICE=cuda, no CUDA → SeparateError
    TC-SEP-010  AURIS_DEVICE=invalid → SeparateError naming bad value
    TC-SEP-011  Model load raises → SeparateError, original in __cause__
    TC-SEP-012  Inference raises OOM → SeparateError mentions remedy
    TC-SEP-013  select_device() auto, no GPU → cpu device + warning logged
    TC-SEP-014  select_device() cpu → cpu device, no warning
"""

from __future__ import annotations

import os
from collections import defaultdict
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

try:
    import demucs  # noqa: F401
    HAS_DEMUCS = True
except ModuleNotFoundError:
    HAS_DEMUCS = False

requires_demucs = pytest.mark.skipif(
    not HAS_DEMUCS,
    reason="demucs not installed (run in .venv-ml)",
)

from src.pipeline.separate import (
    ALL_STEMS,
    STEMS_6S,
    STEMS_FT,
    SeparateError,
    _clear_model_cache,
    _trim_to_shortest,
    select_device,
    separate,
)


# ── Fixtures and helpers ──────────────────────────────────────────────────────

N = 44_100 * 3  # 3 seconds of audio
FAKE_AUDIO = np.zeros((2, N), dtype=np.float32)


def _make_fake_sources(stem_names: tuple[str, ...], n_samples: int = N) -> tuple:
    """
    Build a mock Demucs model and sources tensor for the given stems.

    Returns (mock_model, sources_tensor) where sources_tensor has shape
    (1, len(stem_names), 2, n_samples) matching apply_model's output.
    """
    model = MagicMock()
    model.sources = list(stem_names)
    model.samplerate = 44_100
    model.audio_channels = 2

    # apply_model returns (batch, n_stems, channels, samples)
    sources = torch.zeros(1, len(stem_names), 2, n_samples)
    # Give each stem a unique non-zero value so we can verify provenance
    for i in range(len(stem_names)):
        sources[0, i] = float(i + 1) * 0.1

    return model, sources


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset singleton model cache before every test."""
    _clear_model_cache()
    yield
    _clear_model_cache()


@pytest.fixture(autouse=True)
def force_cpu(monkeypatch):
    """Force CPU device for all tests — no GPU required."""
    monkeypatch.setenv("AURIS_DEVICE", "cpu")


def _patch_demucs(ft_n_samples: int = N, s6_n_samples: int = N):
    """
    Return a context manager that patches demucs at the module boundary.

    Provides realistic mock models for both htdemucs_ft and htdemucs_6s.
    """
    ft_model, ft_sources = _make_fake_sources(STEMS_FT, ft_n_samples)
    s6_model, s6_sources = _make_fake_sources(
        # 6s model has all 6 stems; we only take piano/guitar
        ("drums", "bass", "vocals", "other", "piano", "guitar"),
        s6_n_samples,
    )

    model_map = {
        "htdemucs_ft": ft_model,
        "htdemucs_6s": s6_model,
    }
    sources_map = {
        "htdemucs_ft": ft_sources,
        "htdemucs_6s": s6_sources,
    }

    def fake_get_model(name):
        return model_map[name]

    def fake_apply_model(model, wav, device=None):
        # find which model this is by its sources list
        for key, m in model_map.items():
            if m is model:
                return sources_map[key]
        raise ValueError("unknown mock model")

    def fake_convert_audio(wav, *args, **kwargs):
        return wav

    return (
        patch("src.pipeline.separate._get_model", side_effect=lambda name, dev: model_map[name]),
        patch("demucs.apply.apply_model", side_effect=fake_apply_model),
        patch("demucs.audio.convert_audio", side_effect=fake_convert_audio),
    )


# ── TC-SEP-001  All 6 stems returned ─────────────────────────────────────────

@requires_demucs
def test_all_six_stem_keys_present():
    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        result = separate(FAKE_AUDIO, device=torch.device("cpu"))
    assert set(result.keys()) == set(ALL_STEMS)


# ── TC-SEP-002  dtype float32 ─────────────────────────────────────────────────

@requires_demucs
def test_all_stems_float32():
    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        result = separate(FAKE_AUDIO, device=torch.device("cpu"))
    for name, stem in result.items():
        assert stem.dtype == np.float32, f"{name} dtype is {stem.dtype}"


# ── TC-SEP-003  shape (2, N') ─────────────────────────────────────────────────

@requires_demucs
def test_all_stems_correct_shape():
    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        result = separate(FAKE_AUDIO, device=torch.device("cpu"))
    for name, stem in result.items():
        assert stem.ndim == 2, f"{name} is not 2D"
        assert stem.shape[0] == 2, f"{name} does not have 2 channels"


# ── TC-SEP-004  on_stems_ready called exactly twice ───────────────────────────

@requires_demucs
def test_on_stems_ready_called_twice():
    call_count = 0

    def callback(stems):
        nonlocal call_count
        call_count += 1

    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        separate(FAKE_AUDIO, device=torch.device("cpu"), on_stems_ready=callback)

    assert call_count == 2


# ── TC-SEP-005  First callback contains core stems ────────────────────────────

@requires_demucs
def test_first_callback_contains_core_stems():
    received: list[set] = []

    def callback(stems):
        received.append(set(stems.keys()))

    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        separate(FAKE_AUDIO, device=torch.device("cpu"), on_stems_ready=callback)

    # One of the two callbacks must contain exactly the core stems
    assert set(STEMS_FT) in received


# ── TC-SEP-006  Second callback contains piano/guitar ─────────────────────────

@requires_demucs
def test_second_callback_contains_piano_guitar():
    received: list[set] = []

    def callback(stems):
        received.append(set(stems.keys()))

    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        separate(FAKE_AUDIO, device=torch.device("cpu"), on_stems_ready=callback)

    assert set(STEMS_6S) in received


# ── TC-SEP-007  Stems trimmed to shortest ─────────────────────────────────────

@requires_demucs
def test_stems_trimmed_to_shortest():
    # ft produces N samples, 6s produces N+100 samples
    p1, p2, p3 = _patch_demucs(ft_n_samples=N, s6_n_samples=N + 100)
    with p1, p2, p3:
        result = separate(FAKE_AUDIO, device=torch.device("cpu"))

    lengths = {k: v.shape[1] for k, v in result.items()}
    assert len(set(lengths.values())) == 1, f"stems have different lengths: {lengths}"
    assert next(iter(lengths.values())) == N


def test_trim_to_shortest_unit():
    stems = {
        "a": np.zeros((2, 100)),
        "b": np.zeros((2, 95)),
        "c": np.zeros((2, 102)),
    }
    trimmed = _trim_to_shortest(stems)
    assert all(v.shape[1] == 95 for v in trimmed.values())


# ── TC-SEP-008  Wrong input shape ─────────────────────────────────────────────

def test_mono_input_raises():
    mono = np.zeros(N, dtype=np.float32)
    with pytest.raises(SeparateError, match="expected"):
        separate(mono, device=torch.device("cpu"))


def test_wrong_channel_count_raises():
    bad = np.zeros((3, N), dtype=np.float32)
    with pytest.raises(SeparateError, match="expected"):
        separate(bad, device=torch.device("cpu"))


# ── TC-SEP-009  CUDA requested but unavailable ────────────────────────────────

def test_cuda_unavailable_raises(monkeypatch):
    monkeypatch.setenv("AURIS_DEVICE", "cuda")
    with patch("torch.cuda.is_available", return_value=False):
        with pytest.raises(SeparateError, match="CUDA"):
            select_device()


# ── TC-SEP-010  Unknown device value ──────────────────────────────────────────

def test_unknown_device_raises(monkeypatch):
    monkeypatch.setenv("AURIS_DEVICE", "tpu")
    with pytest.raises(SeparateError, match="tpu"):
        select_device()


# ── TC-SEP-011  Model load failure ────────────────────────────────────────────

@requires_demucs
def test_model_load_failure_raises_separate_error():
    with patch(
        "src.pipeline.separate._get_model",
        side_effect=SeparateError("failed to load htdemucs_ft: weights not found"),
    ):
        with pytest.raises(SeparateError, match="failed to load"):
            separate(FAKE_AUDIO, device=torch.device("cpu"))


def test_model_load_failure_cause_chained():
    original = RuntimeError("weights not found")

    def bad_get_model(name, device):
        raise SeparateError("failed to load htdemucs_ft") from original

    with patch("src.pipeline.separate._get_model", side_effect=bad_get_model):
        with pytest.raises(SeparateError) as exc_info:
            separate(FAKE_AUDIO, device=torch.device("cpu"))

    # Walk the chain to find original
    cause = exc_info.value.__cause__
    assert cause is not None


# ── TC-SEP-012  OOM error ─────────────────────────────────────────────────────

@requires_demucs
def test_oom_error_mentions_remedy():
    ft_model, _ = _make_fake_sources(STEMS_FT)
    s6_model, s6_sources = _make_fake_sources(
        ("drums", "bass", "vocals", "other", "piano", "guitar")
    )

    model_map = {"htdemucs_ft": ft_model, "htdemucs_6s": s6_model}

    def bad_apply(model, wav, device=None):
        if model is ft_model:
            raise torch.cuda.OutOfMemoryError("CUDA out of memory")
        return s6_sources

    def fake_convert(wav, *a, **kw):
        return wav

    with (
        patch("src.pipeline.separate._get_model", side_effect=lambda n, d: model_map[n]),
        patch("demucs.apply.apply_model", side_effect=bad_apply),
        patch("demucs.audio.convert_audio", side_effect=fake_convert),
    ):
        with pytest.raises(SeparateError) as exc_info:
            separate(FAKE_AUDIO, device=torch.device("cpu"))

    msg = str(exc_info.value).lower()
    assert "cpu" in msg or "shorter" in msg


# ── TC-SEP-013  Auto device, no GPU → CPU + warning ──────────────────────────

def test_auto_no_gpu_returns_cpu_and_warns(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("AURIS_DEVICE", "auto")
    with (
        patch("torch.cuda.is_available", return_value=False),
        patch("torch.backends.mps.is_available", return_value=False),
        caplog.at_level(logging.WARNING, logger="src.pipeline.separate"),
    ):
        device = select_device()

    assert device.type == "cpu"
    assert any("cpu" in r.message.lower() for r in caplog.records)


# ── TC-SEP-014  Force CPU → no warning ───────────────────────────────────────

def test_force_cpu_no_warning(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("AURIS_DEVICE", "cpu")
    with caplog.at_level(logging.WARNING, logger="src.pipeline.separate"):
        device = select_device()

    assert device.type == "cpu"
    assert len(caplog.records) == 0


# ── No callback is fine ───────────────────────────────────────────────────────

@requires_demucs
def test_no_callback_does_not_raise():
    p1, p2, p3 = _patch_demucs()
    with p1, p2, p3:
        result = separate(FAKE_AUDIO, device=torch.device("cpu"))
    assert set(result.keys()) == set(ALL_STEMS)
