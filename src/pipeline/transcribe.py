"""
Transcribe stage — SDD-004 (pending)

Converts each separated stem into a PrettyMIDI object via Basic Pitch.
Drum stems receive special handling (onset detection rather than pitch
estimation) — see ADR-003.

Contract
--------
    input  : stems: dict[str, np.ndarray]
               keys    : "drums" | "bass" | "vocals" | "other"
               values  : shape=(2, N)  dtype=float32  sr=44100
    output : dict[str, pretty_midi.PrettyMIDI]
               same keys as input

Open questions (see SDD-004)
----------------------------
    Q-TRX-1  Basic Pitch confidence threshold — default 0.5 may over-generate
             notes in dense polyphonic material.  Needs empirical tuning per
             stem type.
    Q-TRX-2  Drum transcription strategy — ADTLib (full drum pattern
             recognition), onset-only (simple but lossy), or skip entirely
             and emit a placeholder.  Blocked on ADR-003.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pretty_midi

class TranscribeError(Exception):
    """Domain exception for the transcribe stage."""


def transcribe(stems: dict[str, np.ndarray]) -> dict[str, pretty_midi.PrettyMIDI]:
    """
    Transcribe each stem to MIDI via Basic Pitch.

    Parameters
    ----------
    stems : dict[str, np.ndarray]
        Output of the separate stage.

    Returns
    -------
    dict[str, pretty_midi.PrettyMIDI]
        One PrettyMIDI object per stem, keyed identically to the input.

    Raises
    ------
    TranscribeError
        Any failure from audio conversion through MIDI construction.
    """
    raise NotImplementedError("SDD-004 pending — resolve Q-TRX-2 / ADR-003 first")
