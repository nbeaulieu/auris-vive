"""
ADTLibTranscriber — v2 drum transcription via ADTLib (stub).

ADTLib (Automatic Drum Transcription Library) classifies individual drum
instruments and maps them to standard GM percussion note numbers:

    36 — Kick drum
    38 — Snare
    42 — Closed hi-hat
    46 — Open hi-hat
    49 — Crash cymbal
    51 — Ride cymbal

This produces genuine, musically useful drum MIDI that the visual layer
can use to render per-instrument treatments — kick gets a different visual
language than hi-hat.

Status: stub.  Not implemented for v1.  Blocked on:
    Q-DRUM-2  When is ADTLib ready to evaluate?  What quality threshold
              justifies the added ML dependency?

When implemented, this class is a drop-in replacement for OnsetTranscriber.
No changes to the transcribe stage or visual layer are required.

References
----------
    https://github.com/CarlSouthall/ADTLib
"""

from __future__ import annotations

import numpy as np

from src.pipeline.drums.base import DrumTranscribeError, DrumTranscriber, TARGET_SR


class ADTLibTranscriber(DrumTranscriber):
    """
    Full per-instrument drum transcription via ADTLib.

    Stub — raises NotImplementedError until Q-DRUM-2 is resolved and
    ADTLib quality has been evaluated.
    """

    def transcribe(
        self,
        stem: np.ndarray,
        sr: int = TARGET_SR,
    ) -> "pretty_midi.PrettyMIDI":
        raise NotImplementedError(
            "ADTLibTranscriber is not yet implemented — "
            "use OnsetTranscriber for v1. "
            "See ADR-003 Q-DRUM-2."
        )
