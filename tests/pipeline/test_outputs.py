"""
Tests — src.pipeline.outputs
SDD-005 testing requirements

Uses tmp_path pytest fixture for output directories.  No audio processing —
all data is synthetic numpy arrays.

Coverage map:

    TC-OUT-001  All 6 FLAC stems written to output_dir
    TC-OUT-002  All 6 MIDI files written to output_dir
    TC-OUT-003  Returned OutputPaths contains correct absolute paths
    TC-OUT-004  FLAC files are readable by soundfile
    TC-OUT-005  MIDI files are readable by pretty_midi
    TC-OUT-006  output_dir does not exist → OutputError
    TC-OUT-007  score_xml and score_pdf are None (SDD-005 pending)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

try:
    import pretty_midi
    HAS_PRETTY_MIDI = True
except ModuleNotFoundError:
    pretty_midi = None  # type: ignore[assignment]
    HAS_PRETTY_MIDI = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ModuleNotFoundError:
    sf = None  # type: ignore[assignment]
    HAS_SOUNDFILE = False

requires_pretty_midi = pytest.mark.skipif(
    not HAS_PRETTY_MIDI,
    reason="pretty_midi not installed (run in .venv-ml)",
)

requires_soundfile = pytest.mark.skipif(
    not HAS_SOUNDFILE,
    reason="soundfile not installed",
)

from src.pipeline.outputs import JobResult, OutputError, OutputPaths, write


# ── Fixtures and helpers ──────────────────────────────────────────────────────

SR = 44_100
N = SR * 2  # 2 seconds
STEM_NAMES = ("drums", "bass", "vocals", "other", "piano", "guitar")


def _make_stems() -> dict[str, np.ndarray]:
    """Synthetic stems — short sine waves so FLAC/MIDI writes are realistic."""
    t = np.linspace(0, N / SR, N, dtype=np.float32)
    stems = {}
    for i, name in enumerate(STEM_NAMES):
        freq = 220.0 * (i + 1)
        signal = 0.5 * np.sin(2 * np.pi * freq * t)
        stems[name] = np.stack([signal, signal]).astype(np.float32)
    return stems


def _make_midi() -> dict[str, "pretty_midi.PrettyMIDI"]:
    """Build real PrettyMIDI objects if available, else mocks that create files."""
    midi = {}
    for name in STEM_NAMES:
        if HAS_PRETTY_MIDI:
            pm = pretty_midi.PrettyMIDI()
            inst = pretty_midi.Instrument(
                program=0,
                is_drum=(name == "drums"),
                name=name,
            )
            note = pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5)
            inst.notes.append(note)
            pm.instruments.append(inst)
            midi[name] = pm
        else:
            mock = MagicMock()
            # Mock write must actually create the file so assertions pass
            def _fake_write(path, _name=name):
                Path(path).touch()
            mock.write = MagicMock(side_effect=_fake_write)
            midi[name] = mock
    return midi


def _make_job_result() -> JobResult:
    return JobResult(stems=_make_stems(), midi=_make_midi())


# ── TC-OUT-001  All 6 FLAC stems written ─────────────────────────────────────

@requires_soundfile
def test_all_flac_stems_written(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    for name in STEM_NAMES:
        flac_path = paths.stems[name]
        assert flac_path.exists(), f"{name}.flac not written"
        assert flac_path.suffix == ".flac"


# ── TC-OUT-002  All 6 MIDI files written ─────────────────────────────────────

@requires_soundfile
def test_all_midi_files_written(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    for name in STEM_NAMES:
        mid_path = paths.midi[name]
        assert mid_path.exists(), f"{name}.mid not written"
        assert mid_path.suffix == ".mid"


# ── TC-OUT-003  OutputPaths contains absolute paths ──────────────────────────

@requires_soundfile
def test_output_paths_are_absolute(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    for name, p in paths.stems.items():
        assert p.is_absolute(), f"stem path for {name} is not absolute"
    for name, p in paths.midi.items():
        assert p.is_absolute(), f"midi path for {name} is not absolute"


# ── TC-OUT-004  FLAC files are readable by soundfile ─────────────────────────

@requires_soundfile
def test_flac_files_readable(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    for name, flac_path in paths.stems.items():
        data, sr = sf.read(str(flac_path))
        assert sr == SR
        assert data.ndim == 2
        assert data.shape[1] == 2  # soundfile returns (N, channels)


# ── TC-OUT-005  MIDI files are readable by pretty_midi ───────────────────────

@requires_pretty_midi
@requires_soundfile
def test_midi_files_readable(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    for name, mid_path in paths.midi.items():
        pm = pretty_midi.PrettyMIDI(str(mid_path))
        assert len(pm.instruments) >= 1


# ── TC-OUT-006  output_dir does not exist → OutputError ──────────────────────

def test_nonexistent_output_dir_raises(tmp_path):
    result = _make_job_result()
    bad_dir = tmp_path / "does_not_exist"

    with pytest.raises(OutputError, match="does not exist"):
        write(result, bad_dir)


# ── TC-OUT-007  score_xml and score_pdf are None ─────────────────────────────

@requires_soundfile
def test_score_paths_are_none(tmp_path):
    result = _make_job_result()
    paths = write(result, tmp_path)

    assert paths.score_xml is None
    assert paths.score_pdf is None
