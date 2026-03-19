"""
OnsetTranscriber — v1 drum transcription via onset detection.

Uses librosa.onset.onset_detect() to find percussive transient timestamps
in the drum stem.  Each onset is mapped to a generic GM snare note (38)
at a fixed velocity.

The output is rhythmically accurate — it encodes *when* hits occur with
high temporal precision — but does not distinguish between kick, snare,
hi-hat, or cymbal.  All notes are GM 38.

This is intentional for v1.  The visual layer uses onset timestamps as
transient triggers and applies generic rhythmic behaviour.  When
ADTLibTranscriber lands in v2, the same visual layer will automatically
gain per-instrument rendering by inspecting the GM note numbers.

Open questions
--------------
    Q-DRUM-1  What onset detection parameters work best across genres?
              Default librosa values vs tuned per-genre?
    Q-DRUM-3  Should velocity be derived from onset strength rather than
              fixed at 100?  More expressive output for the visual layer.
"""

from __future__ import annotations

import logging

import numpy as np

from src.pipeline.drums.base import DrumTranscribeError, DrumTranscriber, TARGET_SR

logger = logging.getLogger(__name__)

# General MIDI percussion note numbers
_GM_SNARE = 38       # generic placeholder for all v1 drum hits
_NOTE_DURATION = 0.05  # seconds — short enough to not overlap at high tempo
_VELOCITY = 100


class OnsetTranscriber(DrumTranscriber):
    """
    Drum transcription via librosa onset detection.

    No ML model, no extra dependencies beyond librosa (already in stack).
    Runs on CPU in milliseconds.

    Parameters
    ----------
    delta : float
        Onset detection threshold.  Higher values reduce false positives
        on dense material; lower values catch subtle hits.  Default 0.07
        is librosa's recommended starting point.
    wait : int
        Minimum number of frames between onsets.  Prevents double-detection
        on single hits with slow decay.
    """

    def __init__(self, delta: float = 0.07, wait: int = 10) -> None:
        self.delta = delta
        self.wait = wait

    def transcribe(
        self,
        stem: np.ndarray,
        sr: int = TARGET_SR,
    ) -> "pretty_midi.PrettyMIDI":
        """
        Detect onsets in the drum stem and return a PrettyMIDI object.

        Uses the left channel only for onset detection — summing channels
        can cause phase cancellation on hard-panned material.
        """
        import librosa
        import pretty_midi

        try:
            # Use left channel for onset detection
            mono = stem[0] if stem.ndim == 2 else stem

            onset_times: np.ndarray = librosa.onset.onset_detect(
                y=mono,
                sr=sr,
                units="time",
                delta=self.delta,
                wait=self.wait,
            )
        except Exception as exc:
            raise DrumTranscribeError(
                f"onset detection failed: {exc}"
            ) from exc

        logger.debug(
            "OnsetTranscriber: detected %d onsets", len(onset_times)
        )

        try:
            midi = pretty_midi.PrettyMIDI()
            drums = pretty_midi.Instrument(
                program=0,
                is_drum=True,
                name="Drums (onset)",
            )

            for onset_time in onset_times:
                note = pretty_midi.Note(
                    velocity=_VELOCITY,
                    pitch=_GM_SNARE,
                    start=float(onset_time),
                    end=float(onset_time) + _NOTE_DURATION,
                )
                drums.notes.append(note)

            midi.instruments.append(drums)
        except Exception as exc:
            raise DrumTranscribeError(
                f"MIDI construction failed: {exc}"
            ) from exc

        return midi
