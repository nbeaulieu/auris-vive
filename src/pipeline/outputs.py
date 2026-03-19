"""
Outputs stage — SDD-005 (pending)

Serialises the pipeline result to disk:
    - Per-stem FLAC files
    - Per-stem .mid files
    - MusicXML score (+ rendered PDF via music21 → LilyPond or MuseScore)

Contract
--------
    input  : result: JobResult
    output : OutputPaths  (written files, all paths absolute)

The output directory is caller-supplied; this stage does no path management
beyond writing into it.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pretty_midi


class OutputError(Exception):
    """Domain exception for the outputs stage."""


@dataclasses.dataclass(frozen=True)
class JobResult:
    """
    Intermediate pipeline result passed from runner to outputs.

    Attributes
    ----------
    stems : dict[str, np.ndarray]
        Separated waveforms.  shape=(2, N), float32, sr=44100.
    midi  : dict[str, pretty_midi.PrettyMIDI]
        Transcribed MIDI, keyed by stem name.
    """
    stems: dict[str, np.ndarray]
    midi: dict[str, pretty_midi.PrettyMIDI]


@dataclasses.dataclass(frozen=True)
class OutputPaths:
    """Absolute paths to every file written by the outputs stage."""
    stems: dict[str, Path]      # stem name → .flac path
    midi: dict[str, Path]       # stem name → .mid path
    score_xml: Path | None      # MusicXML, None if generation failed
    score_pdf: Path | None      # rendered PDF, None if LilyPond unavailable


def write(result: JobResult, output_dir: Path) -> OutputPaths:
    """
    Write all output artefacts for a completed pipeline job.

    Parameters
    ----------
    result     : JobResult
    output_dir : Path  Must exist and be writable.

    Returns
    -------
    OutputPaths

    Raises
    ------
    OutputError
        Any failure from FLAC encoding through score generation.
        PDF generation failure is non-fatal and returns score_pdf=None.
    """
    raise NotImplementedError("SDD-005 pending")
