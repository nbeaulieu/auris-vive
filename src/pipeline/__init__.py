"""
src.pipeline — audio analysis pipeline

Sub-modules
-----------
    ingest      load(path) → np.ndarray (2, N) float32 44100 Hz
    separate    separate(audio) → dict[str, np.ndarray]
    transcribe  transcribe(stems) → dict[str, PrettyMIDI]
    outputs     write(result, output_dir) → OutputPaths
    runner      run(path, output_dir) → OutputPaths
    drums       DrumTranscriber ABC + OnsetTranscriber / ADTLibTranscriber

Import directly from submodules rather than from this package to avoid
eager-loading the full dependency chain at import time.

    from src.pipeline.ingest import load, IngestError
    from src.pipeline.separate import separate, SeparateError
"""
