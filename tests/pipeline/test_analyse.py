"""
Tests — src.pipeline.analyse
Analyse stage testing requirements

No ML dependencies — uses only librosa, numpy, scipy (base deps).
All tests use synthetic stems.  Runs in both .venv and .venv-ml.

Coverage map:

    TC-ANA-001  Valid 6-stem input → returns dict with all 6 keys
    TC-ANA-002  Each StemCurves has six float32 (T,) arrays in [0, 1]
    TC-ANA-003  Single-stem input works
    TC-ANA-004  Wrong input type → AnalyseError
    TC-ANA-005  Wrong stem value type → AnalyseError
    TC-ANA-006  Silent stem (all zeros) → valid curves (all zeros)
    TC-ANA-007  at_fps() decimation halves frame count
    TC-ANA-008  at_fps() with target >= native returns same object
    TC-ANA-009  DiskCurvesSource round-trip (save + load)
    TC-ANA-010  DiskCurvesSource load missing stem → AnalyseError
    TC-ANA-011  MemoryCurvesSource round-trip
    TC-ANA-012  MemoryCurvesSource load missing → KeyError
"""

from __future__ import annotations

import numpy as np
import pytest

from src.pipeline.analyse.analyse import analyse
from src.pipeline.analyse.curves import CURVE_NAMES, AnalyseError, StemCurves
from src.pipeline.analyse.disk import DiskCurvesSource
from src.pipeline.analyse.memory import MemoryCurvesSource


# ── Fixtures and helpers ──────────────────────────────────────────────────────

SR = 44_100
DURATION_S = 2
N = SR * DURATION_S
STEM_NAMES = ("drums", "bass", "vocals", "other", "piano", "guitar")
FPS = 100


def _make_stems(
    names: tuple[str, ...] = STEM_NAMES,
    kind: str = "sine",
) -> dict[str, np.ndarray]:
    """
    Synthetic 6-stem dict matching the separate stage output contract.

    kind:
        "sine"  — 440 Hz sine wave (exercises all spectral features)
        "zeros" — silence
        "ones"  — DC offset
    """
    result: dict[str, np.ndarray] = {}
    for name in names:
        if kind == "zeros":
            result[name] = np.zeros((2, N), dtype=np.float32)
        elif kind == "ones":
            result[name] = np.ones((2, N), dtype=np.float32) * 0.5
        else:
            t = np.linspace(0, DURATION_S, N, endpoint=False, dtype=np.float32)
            wave = 0.5 * np.sin(2 * np.pi * 440 * t)
            result[name] = np.stack([wave, wave])
    return result


def _make_curves(n_frames: int = 200, fps: int = FPS) -> StemCurves:
    """Create a StemCurves with known values for round-trip tests."""
    rng = np.random.default_rng(42)
    return StemCurves(
        energy=rng.random(n_frames).astype(np.float32),
        brightness=rng.random(n_frames).astype(np.float32),
        onset=rng.random(n_frames).astype(np.float32),
        warmth=rng.random(n_frames).astype(np.float32),
        texture=rng.random(n_frames).astype(np.float32),
        flux=rng.random(n_frames).astype(np.float32),
        fps=fps,
        sr=SR,
    )


# ── TC-ANA-001  All 6 stem keys returned ─────────────────────────────────────

def test_all_six_stem_keys_returned():
    stems = _make_stems()
    result = analyse(stems, sr=SR, fps=FPS)
    assert set(result.keys()) == set(STEM_NAMES)


# ── TC-ANA-002  Curve contract: float32, (T,), [0, 1] ────────────────────────

def test_curve_contract():
    stems = _make_stems(names=("bass",))
    result = analyse(stems, sr=SR, fps=FPS)
    curves = result["bass"]

    for name in CURVE_NAMES:
        arr = getattr(curves, name)
        assert arr.dtype == np.float32, f"{name} dtype is {arr.dtype}"
        assert arr.ndim == 1, f"{name} ndim is {arr.ndim}"
        assert float(arr.min()) >= 0.0, f"{name} min is {arr.min()}"
        assert float(arr.max()) <= 1.0, f"{name} max is {arr.max()}"

    assert curves.fps == FPS
    assert curves.sr == SR


# ── TC-ANA-003  Single-stem input works ───────────────────────────────────────

def test_single_stem():
    stems = _make_stems(names=("vocals",))
    result = analyse(stems, sr=SR, fps=FPS)
    assert "vocals" in result
    assert len(result) == 1


# ── TC-ANA-004  Wrong input type → AnalyseError ──────────────────────────────

def test_wrong_input_type():
    with pytest.raises(AnalyseError, match="expected dict"):
        analyse("not a dict")  # type: ignore[arg-type]


# ── TC-ANA-005  Wrong stem value type → AnalyseError ─────────────────────────

def test_wrong_stem_value_type():
    with pytest.raises(AnalyseError, match="expected np.ndarray"):
        analyse({"bass": "not an array"})  # type: ignore[dict-item]


# ── TC-ANA-006  Silent stem → valid zero curves ──────────────────────────────

def test_silent_stem_produces_zero_curves():
    stems = _make_stems(names=("drums",), kind="zeros")
    result = analyse(stems, sr=SR, fps=FPS)
    curves = result["drums"]

    for name in CURVE_NAMES:
        arr = getattr(curves, name)
        assert arr.dtype == np.float32
        assert float(arr.max()) <= 1.0
        assert float(arr.min()) >= 0.0


# ── TC-ANA-007  at_fps() decimation ──────────────────────────────────────────

def test_at_fps_decimation():
    curves = _make_curves(n_frames=200, fps=100)
    decimated = curves.at_fps(50)

    assert decimated.fps == 50
    assert len(decimated.energy) == 100  # 200 / stride(2) = 100
    # Values should be from the original at stride positions
    np.testing.assert_array_equal(decimated.energy, curves.energy[::2])


# ── TC-ANA-008  at_fps() with target >= native → same object ─────────────────

def test_at_fps_no_upsample():
    curves = _make_curves(n_frames=200, fps=100)
    same = curves.at_fps(100)
    assert same is curves

    higher = curves.at_fps(200)
    assert higher is curves


# ── TC-ANA-009  DiskCurvesSource round-trip ───────────────────────────────────

def test_disk_source_round_trip(tmp_path):
    source = DiskCurvesSource(tmp_path / "curves")
    original = _make_curves()

    source.save("bass", original)

    assert source.exists("bass")
    assert not source.exists("drums")
    assert "bass" in source.available_stems()

    loaded = source.load("bass")
    assert loaded.fps == original.fps
    assert loaded.sr == original.sr
    for name in CURVE_NAMES:
        np.testing.assert_array_almost_equal(
            getattr(loaded, name),
            getattr(original, name),
            decimal=5,
        )


# ── TC-ANA-010  DiskCurvesSource load missing → AnalyseError ─────────────────

def test_disk_source_load_missing(tmp_path):
    source = DiskCurvesSource(tmp_path / "curves")
    with pytest.raises(AnalyseError, match="metadata not found"):
        source.load("nonexistent")


# ── TC-ANA-011  MemoryCurvesSource round-trip ─────────────────────────────────

def test_memory_source_round_trip():
    source = MemoryCurvesSource()
    original = _make_curves()

    assert not source.exists("vocals")
    source.save("vocals", original)
    assert source.exists("vocals")
    assert "vocals" in source.available_stems()

    loaded = source.load("vocals")
    assert loaded is original  # in-memory — same object


# ── TC-ANA-012  MemoryCurvesSource load missing → KeyError ────────────────────

def test_memory_source_load_missing():
    source = MemoryCurvesSource()
    with pytest.raises(KeyError, match="no curves for stem"):
        source.load("nonexistent")
