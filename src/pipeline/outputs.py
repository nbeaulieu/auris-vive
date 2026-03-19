"""
Outputs stage — SDD-005

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
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pretty_midi

logger = logging.getLogger(__name__)

TARGET_SR: int = 44_100


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
        Any failure from FLAC encoding through MIDI writing.
        MIDI write failures for individual stems do not prevent FLAC writes;
        errors are collected and raised at the end.
    """
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise OutputError(f"output directory does not exist: {output_dir}")

    stem_paths: dict[str, Path] = {}
    midi_paths: dict[str, Path] = {}
    errors: list[str] = []

    # Write FLAC stems
    stem_paths = _write_flac_stems(result.stems, output_dir)

    # Write MIDI files — collect errors, don't abort on individual failures
    for stem_name, midi_obj in result.midi.items():
        mid_path = (output_dir / f"{stem_name}.mid").resolve()
        try:
            midi_obj.write(str(mid_path))
            midi_paths[stem_name] = mid_path
        except Exception as exc:
            errors.append(f"MIDI write failed for '{stem_name}': {exc}")
            logger.error("MIDI write failed for '%s': %s", stem_name, exc)

    if errors:
        raise OutputError(
            f"{len(errors)} MIDI write failure(s): " + "; ".join(errors)
        )

    # Score generation is SDD-005 — stubbed for now
    paths = OutputPaths(
        stems=stem_paths,
        midi=midi_paths,
        score_xml=None,
        score_pdf=None,
    )

    logger.info(
        "outputs complete  flac=%d  midi=%d",
        len(stem_paths), len(midi_paths),
    )
    return paths


def _write_flac_stems(
    stems: dict[str, np.ndarray],
    output_dir: Path,
) -> dict[str, Path]:
    """Write each stem as a 24-bit FLAC file."""
    import soundfile as sf

    paths: dict[str, Path] = {}
    for stem_name, audio in stems.items():
        flac_path = (output_dir / f"{stem_name}.flac").resolve()
        try:
            # soundfile expects (N, channels); our arrays are (channels, N)
            sf.write(str(flac_path), audio.T, TARGET_SR, subtype="PCM_24")
            paths[stem_name] = flac_path
        except Exception as exc:
            raise OutputError(
                f"FLAC write failed for '{stem_name}': {exc}"
            ) from exc

    return paths
