"""
src.pipeline.drums — drum stem transcription

Drum stems cannot be transcribed via Basic Pitch (which is a pitch estimator —
drums are unpitched).  This package provides a DrumTranscriber ABC with
swappable implementations:

    OnsetTranscriber   — v1, onset detection only, no ML, no extra deps
    ADTLibTranscriber  — v2 stub, full per-instrument drum MIDI via ADTLib

Usage
-----
    from src.pipeline.drums import DrumTranscriber, OnsetTranscriber

    transcriber = OnsetTranscriber()
    midi = transcriber.transcribe(drum_stem)

The transcribe stage receives a DrumTranscriber instance and calls
transcribe() — it never references a concrete implementation directly.
The active implementation is selected via configuration.
"""

from src.pipeline.drums.base import DrumTranscriber
from src.pipeline.drums.onset import OnsetTranscriber
from src.pipeline.drums.adtlib import ADTLibTranscriber

__all__ = [
    "DrumTranscriber",
    "OnsetTranscriber",
    "ADTLibTranscriber",
]
