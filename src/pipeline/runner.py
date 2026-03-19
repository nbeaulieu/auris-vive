"""
Pipeline runner

Wires ingest → separate → transcribe → outputs into a single callable.
Invoked by the job queue; not called directly from the API layer.

The runner owns no I/O of its own — it receives a path (produced by an
adapter) and an output directory (allocated by the job queue).

Contract
--------
    input  : path: str | os.PathLike
             output_dir: Path
    output : OutputPaths
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.pipeline.ingest import load
from src.pipeline.outputs import JobResult, OutputPaths, write
from src.pipeline.separate import separate
from src.pipeline.transcribe import transcribe

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """
    Top-level pipeline failure.

    Wraps stage-specific errors (IngestError, SeparateError, etc.) so the
    job queue has a single exception type to handle.  The original exception
    is always chained via `__cause__`.
    """


def run(path: str | os.PathLike, output_dir: Path) -> OutputPaths:
    """
    Execute the full pipeline for a single audio file.

    Parameters
    ----------
    path       : Absolute path produced by an input adapter.
    output_dir : Pre-existing directory where outputs will be written.

    Returns
    -------
    OutputPaths

    Raises
    ------
    PipelineError
        Wraps any stage exception.  Check __cause__ for the original.
    """
    p = Path(path)
    logger.info("pipeline start  path=%s", p.name)

    try:
        audio = load(p)
    except Exception as exc:
        raise PipelineError(f"ingest failed: {exc}") from exc

    try:
        stems = separate(audio)
    except Exception as exc:
        raise PipelineError(f"separation failed: {exc}") from exc

    try:
        midi = transcribe(stems)
    except Exception as exc:
        raise PipelineError(f"transcription failed: {exc}") from exc

    try:
        result = JobResult(stems=stems, midi=midi)
        paths = write(result, output_dir)
    except Exception as exc:
        raise PipelineError(f"output writing failed: {exc}") from exc

    logger.info("pipeline complete  path=%s  outputs=%s", p.name, output_dir)
    return paths
