"""
Transcribe stage — SDD-004

Converts each separated stem into a PrettyMIDI object.  Pitched stems go
through Basic Pitch; the drum stem is routed to a DrumTranscriber instance
(onset detection by default — see ADR-003).

Contract
--------
    input  : stems: dict[str, np.ndarray]
               keys    : "drums" | "bass" | "vocals" | "other" | "piano" | "guitar"
               values  : shape=(2, N)  dtype=float32  sr=44100
             sr: int = 44100
             drum_transcriber: DrumTranscriber | None  (defaults to OnsetTranscriber)
    output : dict[str, pretty_midi.PrettyMIDI]
               same keys as input
"""

from __future__ import annotations

import logging
import tempfile
from typing import TYPE_CHECKING

import numpy as np

from src.pipeline.drums.base import DrumTranscriber

if TYPE_CHECKING:
    import pretty_midi

logger = logging.getLogger(__name__)

TARGET_SR: int = 44_100


class TranscribeError(Exception):
    """Domain exception for the transcribe stage."""


def transcribe(
    stems: dict[str, np.ndarray],
    sr: int = TARGET_SR,
    drum_transcriber: DrumTranscriber | None = None,
) -> dict[str, "pretty_midi.PrettyMIDI"]:
    """
    Transcribe each stem to MIDI.

    Parameters
    ----------
    stems : dict[str, np.ndarray]
        Output of the separate stage.  Each value is shape=(2, N), float32.
    sr : int
        Sample rate of the stems.
    drum_transcriber : DrumTranscriber | None
        Injectable drum transcription strategy.  Defaults to OnsetTranscriber.

    Returns
    -------
    dict[str, pretty_midi.PrettyMIDI]
        One PrettyMIDI object per stem, keyed identically to the input.

    Raises
    ------
    TranscribeError
        Any failure from audio conversion through MIDI construction.
    """
    if not isinstance(stems, dict):
        raise TranscribeError(
            f"expected dict[str, np.ndarray], got {type(stems).__name__}"
        )

    if drum_transcriber is None:
        from src.pipeline.drums.onset import OnsetTranscriber
        drum_transcriber = OnsetTranscriber()

    midi: dict[str, pretty_midi.PrettyMIDI] = {}

    for stem_name, stem in stems.items():
        if not isinstance(stem, np.ndarray):
            raise TranscribeError(
                f"stem '{stem_name}' is {type(stem).__name__}, expected np.ndarray"
            )

        if stem_name == "drums":
            try:
                midi[stem_name] = drum_transcriber.transcribe(stem, sr=sr)
            except Exception as exc:
                raise TranscribeError(
                    f"drum transcription failed for '{stem_name}': {exc}"
                ) from exc
        else:
            midi[stem_name] = _transcribe_with_basic_pitch(stem, sr, stem_name)

    logger.info("transcribe complete  stems=%s", list(midi.keys()))
    return midi


def _transcribe_with_basic_pitch(
    stem: np.ndarray,
    sr: int,
    stem_name: str,
) -> "pretty_midi.PrettyMIDI":
    """
    Write stem to a temp WAV, run Basic Pitch, return the PrettyMIDI object.

    Basic Pitch accepts a file path, not a numpy array.  The temp file is
    always cleaned up, even on failure.
    """
    import soundfile as sf

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        # soundfile expects (N, channels); our arrays are (channels, N)
        sf.write(tmp_path, stem.T, sr, subtype="PCM_16")

        try:
            from basic_pitch.inference import predict
            from basic_pitch import ICASSP_2022_MODEL_PATH

            _model_output, midi_data, _note_events = predict(
                tmp_path,
                ICASSP_2022_MODEL_PATH,
            )
        except Exception as exc:
            raise TranscribeError(
                f"Basic Pitch failed for stem '{stem_name}': {exc}"
            ) from exc

        return midi_data
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            logger.warning("failed to remove temp file: %s", tmp_path)
