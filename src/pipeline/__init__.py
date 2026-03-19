"""
src.pipeline — audio analysis pipeline

Public surface
--------------
    load(path)                → np.ndarray (2, N) float32 44100 Hz
    separate(audio)           → dict[str, np.ndarray]
    transcribe(stems)         → dict[str, PrettyMIDI]
    write(result, output_dir) → OutputPaths
    run(path, output_dir)     → OutputPaths   (full pipeline)

Import individual stages for testing; use run() for production.
"""

from src.pipeline.ingest import IngestError, load
from src.pipeline.outputs import JobResult, OutputError, OutputPaths, write
from src.pipeline.runner import PipelineError, run
from src.pipeline.separate import SeparateError, separate
from src.pipeline.transcribe import TranscribeError, transcribe

__all__ = [
    # stages
    "load",
    "separate",
    "transcribe",
    "write",
    "run",
    # data types
    "JobResult",
    "OutputPaths",
    # exceptions
    "IngestError",
    "SeparateError",
    "TranscribeError",
    "OutputError",
    "PipelineError",
]
