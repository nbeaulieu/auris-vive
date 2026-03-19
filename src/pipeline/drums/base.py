"""
DrumTranscriber — abstract base class for drum stem transcription.

All implementations share one contract: accept a drum stem waveform,
return a PrettyMIDI object.  The note content of that MIDI varies by
implementation:

    OnsetTranscriber    Generic GM 38 (snare) notes at onset times.
                        Rhythmically accurate, instrument-agnostic.

    ADTLibTranscriber   Per-instrument GM notes (kick=36, snare=38,
                        hi-hat=42, etc.).  Full drum pattern MIDI.

The visual layer inspects GM note numbers to drive per-instrument
visual treatments.  When all notes are GM 38 (OnsetTranscriber), it
falls back to generic transient behaviour.  When GM note numbers
distinguish instruments (ADTLibTranscriber), it renders kick, snare,
and cymbal with different visual languages automatically.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pretty_midi

TARGET_SR: int = 44_100


class DrumTranscriber(abc.ABC):
    """
    Abstract base for drum stem transcription.

    Subclasses must implement transcribe().  They should raise
    DrumTranscribeError for any failure — never let internal exceptions
    escape the module boundary.
    """

    @abc.abstractmethod
    def transcribe(
        self,
        stem: np.ndarray,
        sr: int = TARGET_SR,
    ) -> "pretty_midi.PrettyMIDI":
        """
        Transcribe a separated drum stem to MIDI.

        Parameters
        ----------
        stem : np.ndarray
            Drum stem from the separate stage.
            shape=(2, N), dtype=float32, sr=44100.
        sr : int
            Sample rate of the stem. Must match TARGET_SR (44100).

        Returns
        -------
        pretty_midi.PrettyMIDI
            A MIDI object with a single drum instrument track.
            Note numbers follow the General MIDI percussion map.

        Raises
        ------
        DrumTranscribeError
            Any failure during transcription.
        """


class DrumTranscribeError(Exception):
    """Domain exception for drum transcription failures."""
