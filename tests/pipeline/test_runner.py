"""
Tests — src.pipeline.runner

The runner is fully implemented but its three downstream stages (separate,
transcribe, outputs) are stubs.  These tests therefore cover:

    1. Successful end-to-end path when all stages are mocked (happy path)
    2. PipelineError wrapping for each stage failure
    3. __cause__ chaining — original exception is always preserved
    4. Logging (start / complete messages)

When SDD-003/004/005 land, delete the mocks and let the real stages run.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

try:
    import pretty_midi
except ModuleNotFoundError:
    pretty_midi = None  # type: ignore[assignment]

from src.pipeline.ingest import IngestError
from src.pipeline.outputs import JobResult, OutputPaths
from src.pipeline.runner import PipelineError, run
from src.pipeline.separate import SeparateError
from src.pipeline.transcribe import TranscribeError


# ── Shared test data ──────────────────────────────────────────────────────────

N = 44_100 * 3  # 3 seconds

FAKE_AUDIO = np.zeros((2, N), dtype=np.float32)

FAKE_STEMS = {
    "drums":  np.zeros((2, N), dtype=np.float32),
    "bass":   np.zeros((2, N), dtype=np.float32),
    "vocals": np.zeros((2, N), dtype=np.float32),
    "other":  np.zeros((2, N), dtype=np.float32),
}

FAKE_MIDI = {name: pretty_midi.PrettyMIDI() for name in FAKE_STEMS} if pretty_midi else {name: None for name in FAKE_STEMS}

FAKE_OUTPUT_PATHS = OutputPaths(
    stems={k: Path(f"/tmp/{k}.flac") for k in FAKE_STEMS},
    midi={k: Path(f"/tmp/{k}.mid") for k in FAKE_STEMS},
    score_xml=Path("/tmp/score.xml"),
    score_pdf=None,
)


def _mock_all_stages():
    """Return a stack of patches that makes every stage succeed."""
    return [
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",    return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe",  return_value=FAKE_MIDI),
        patch("src.pipeline.runner.write",       return_value=FAKE_OUTPUT_PATHS),
    ]


# ── Happy path ────────────────────────────────────────────────────────────────

def test_run_returns_output_paths(tmp_path):
    with (
        patch("src.pipeline.runner.load",      return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",  return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe",return_value=FAKE_MIDI),
        patch("src.pipeline.runner.write",     return_value=FAKE_OUTPUT_PATHS),
    ):
        result = run(tmp_path / "track.wav", tmp_path)

    assert isinstance(result, OutputPaths)


def test_run_passes_audio_to_separate(tmp_path):
    with (
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO) as mock_load,
        patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS) as mock_sep,
        patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI),
        patch("src.pipeline.runner.write",      return_value=FAKE_OUTPUT_PATHS),
    ):
        run(tmp_path / "track.wav", tmp_path)

    mock_sep.assert_called_once_with(FAKE_AUDIO)


def test_run_passes_stems_to_transcribe(tmp_path):
    with (
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI) as mock_trx,
        patch("src.pipeline.runner.write",      return_value=FAKE_OUTPUT_PATHS),
    ):
        run(tmp_path / "track.wav", tmp_path)

    mock_trx.assert_called_once_with(FAKE_STEMS)


def test_run_passes_job_result_to_write(tmp_path):
    with (
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI),
        patch("src.pipeline.runner.write",      return_value=FAKE_OUTPUT_PATHS) as mock_write,
    ):
        run(tmp_path / "track.wav", tmp_path)

    call_args = mock_write.call_args
    result_arg = call_args[0][0]
    assert isinstance(result_arg, JobResult)
    assert result_arg.stems is FAKE_STEMS
    assert result_arg.midi is FAKE_MIDI


# ── PipelineError wrapping ────────────────────────────────────────────────────

def test_ingest_failure_raises_pipeline_error(tmp_path):
    with patch("src.pipeline.runner.load", side_effect=IngestError("bad file")):
        with pytest.raises(PipelineError):
            run(tmp_path / "track.wav", tmp_path)


def test_separate_failure_raises_pipeline_error(tmp_path):
    with (
        patch("src.pipeline.runner.load",     return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate", side_effect=SeparateError("gpu oom")),
    ):
        with pytest.raises(PipelineError):
            run(tmp_path / "track.wav", tmp_path)


def test_transcribe_failure_raises_pipeline_error(tmp_path):
    with (
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe", side_effect=TranscribeError("bad midi")),
    ):
        with pytest.raises(PipelineError):
            run(tmp_path / "track.wav", tmp_path)


def test_write_failure_raises_pipeline_error(tmp_path):
    with (
        patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
        patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI),
        patch("src.pipeline.runner.write",      side_effect=OSError("disk full")),
    ):
        with pytest.raises(PipelineError):
            run(tmp_path / "track.wav", tmp_path)


# ── __cause__ chaining ────────────────────────────────────────────────────────

def test_ingest_cause_chained(tmp_path):
    original = IngestError("corrupt header")
    with patch("src.pipeline.runner.load", side_effect=original):
        with pytest.raises(PipelineError) as exc_info:
            run(tmp_path / "track.wav", tmp_path)
    assert exc_info.value.__cause__ is original


def test_separate_cause_chained(tmp_path):
    original = SeparateError("cuda error")
    with (
        patch("src.pipeline.runner.load",     return_value=FAKE_AUDIO),
        patch("src.pipeline.runner.separate", side_effect=original),
    ):
        with pytest.raises(PipelineError) as exc_info:
            run(tmp_path / "track.wav", tmp_path)
    assert exc_info.value.__cause__ is original


# ── Logging ───────────────────────────────────────────────────────────────────

def test_logs_pipeline_start(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="src.pipeline.runner"):
        with (
            patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
            patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
            patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI),
            patch("src.pipeline.runner.write",      return_value=FAKE_OUTPUT_PATHS),
        ):
            run(tmp_path / "track.wav", tmp_path)

    messages = " ".join(r.message for r in caplog.records).lower()
    assert "pipeline start" in messages or "start" in messages


def test_logs_pipeline_complete(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="src.pipeline.runner"):
        with (
            patch("src.pipeline.runner.load",       return_value=FAKE_AUDIO),
            patch("src.pipeline.runner.separate",   return_value=FAKE_STEMS),
            patch("src.pipeline.runner.transcribe", return_value=FAKE_MIDI),
            patch("src.pipeline.runner.write",      return_value=FAKE_OUTPUT_PATHS),
        ):
            run(tmp_path / "track.wav", tmp_path)

    messages = " ".join(r.message for r in caplog.records).lower()
    assert "complete" in messages


def test_no_complete_log_on_failure(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="src.pipeline.runner"):
        with patch("src.pipeline.runner.load", side_effect=IngestError("bad")):
            with pytest.raises(PipelineError):
                run(tmp_path / "track.wav", tmp_path)

    messages = " ".join(r.message for r in caplog.records).lower()
    assert "complete" not in messages
