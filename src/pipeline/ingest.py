"""
Ingest stage — SDD-002

Accepts a file path from an input adapter and returns a normalised audio array
ready for Demucs source separation.

Contract
--------
    input  : path: str | os.PathLike
    output : np.ndarray  shape=(2, N)  dtype=float32  sr=44100  values∈[-1.0, 1.0]

Architectural boundary
----------------------
This stage is intentionally ignorant of how the path was produced.
File, URL, stream, and device adapters all converge on a path before reaching
here.  Adding new input sources is zero-impact on this module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Union

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TARGET_SR: int = 44_100
MIN_DURATION_S: float = 1.0          # files shorter than this are rejected
CLIP_WARN_THRESHOLD: float = 0.9999  # source amplitude above this → warn; >1.0 → hard warn

PathLike = Union[str, os.PathLike]


# ── Domain exception ──────────────────────────────────────────────────────────

class IngestError(Exception):
    """
    Raised for any failure within the ingest stage.

    Callers catch this type only; librosa, soundfile, and NumPy internals
    never escape the module boundary.
    """


# ── Public interface ──────────────────────────────────────────────────────────

def load(path: PathLike) -> np.ndarray:
    """
    Decode, normalise, and validate an audio file.

    Parameters
    ----------
    path : str | os.PathLike
        Absolute or relative path produced by an input adapter.
        Must be readable by librosa (WAV, FLAC, OGG, AIFF natively;
        MP3/MP4/AAC require a working FFmpeg installation).

    Returns
    -------
    np.ndarray
        shape  : (2, N)
        dtype  : float32
        values : [-1.0, 1.0]
        sr     : 44 100 Hz (implicit — downstream stages must not resample again)

    Raises
    ------
    IngestError
        Any failure from path resolution through post-load validation.
        The message is actionable: it names the file, describes what went
        wrong, and (for the FFmpeg case) tells the operator how to fix it.
    """
    resolved = _resolve_path(path)

    audio, native_sr = _decode(resolved)          # (C, N) or (N,)  float32
    audio = _to_stereo(audio)                     # (2, N)           float32
    audio = _resample(audio, native_sr, resolved) # (2, N')          float32  sr=44100
    audio = _normalise(audio, resolved)           # (2, N')          float32  ∈[-1,1]
    _validate(audio, resolved)                    # raises on contract violation

    logger.info(
        "ingest ok  path=%s  shape=%s  duration=%.2fs",
        resolved.name, audio.shape, audio.shape[1] / TARGET_SR,
    )
    return audio


# ── Step 1: path resolution ───────────────────────────────────────────────────

def _resolve_path(path: PathLike) -> Path:
    p = Path(path)
    if not p.exists():
        raise IngestError(f"file not found: {p}")
    if not p.is_file():
        raise IngestError(f"path is not a regular file: {p}")
    return p


# ── Step 2: decode ────────────────────────────────────────────────────────────

def _decode(path: Path) -> tuple[np.ndarray, int]:
    """
    Decode audio to a float32 array, preserving native sample rate and channels.

    Returns
    -------
    audio : np.ndarray
        (N,) for mono sources, (C, N) for multi-channel sources.
        librosa 0.9+ returns channel-first; older versions or some soundfile
        backends may return channel-last (N, C) — handled in _to_stereo.
    native_sr : int
        Original sample rate of the file.

    MP3 / MP4 / AAC require FFmpeg.  librosa surfaces a missing backend as
    audioread.NoBackendError or a RuntimeError wrapping it.  We detect both
    and emit an actionable IngestError.
    """
    try:
        # sr=None  → preserve native sample rate; we resample explicitly
        # mono=False → preserve channels; we normalise layout in _to_stereo
        audio, native_sr = librosa.load(
            str(path),
            sr=None,
            mono=False,
            dtype=np.float32,
        )
    except Exception as exc:
        _raise_if_backend_error(exc, path)
        raise IngestError(f"failed to decode {path.name}: {exc}") from exc

    return audio, int(native_sr)


def _raise_if_backend_error(exc: Exception, path: Path) -> None:
    """
    Re-raise exc as an actionable IngestError when it represents a missing
    audio backend (FFmpeg not on PATH).

    Detection is done by class name to avoid a hard dependency on audioread
    being importable in test environments where it may be mocked.
    """
    type_name = type(exc).__name__          # e.g. "NoBackendError"
    exc_msg = str(exc).lower()

    is_backend_error = (
        "NoBackendError" in type_name
        or "nobackenderror" in type_name
        or "ffmpeg" in exc_msg
        or "no backend" in exc_msg
        or ("backend" in exc_msg and "found" in exc_msg)
    )
    if is_backend_error:
        raise IngestError(
            f"no audio backend found for '{path.name}' — "
            "install FFmpeg (macOS: brew install ffmpeg  |  "
            "Linux: apt install ffmpeg) and ensure it is on PATH"
        ) from exc


# ── Step 3: channel normalisation ─────────────────────────────────────────────

def _to_stereo(audio: np.ndarray) -> np.ndarray:
    """
    Normalise channel layout to (2, N) float32.

    Handles every layout librosa can return:

        (N,)    mono waveform                → duplicate to (2, N)
        (1, N)  mono stored as 2-D           → duplicate to (2, N)
        (2, N)  stereo channel-first         → pass-through
        (C, N)  multi-channel C > 2          → take first two channels
        (N, 2)  stereo channel-last          → transpose → (2, N)
        (N, C)  multi-channel channel-last   → transpose → take first two

    Channel-last detection heuristic: if axis-1 is ≤ 8 and axis-0 is
    substantially larger, the array is (N, C).  The threshold of 8 safely
    covers up to 7.1 surround; a legitimate (N, C=8) file at 1s would have
    N=44100, making the ambiguity impossible.
    """
    if audio.ndim == 1:
        logger.debug("mono (1-D) — duplicating channel")
        return np.stack([audio, audio], axis=0)

    if audio.ndim == 2:
        rows, cols = audio.shape

        # Channel-last detection: (N, C) where C is small and N is large
        if cols <= 8 and rows > cols:
            logger.debug("channel-last layout (%d, %d) — transposing", rows, cols)
            audio = audio.T           # now (C, N)
            rows, cols = audio.shape  # re-read after transpose

        # audio is now (C, N)
        if rows == 1:
            logger.debug("mono (1, N) — duplicating channel")
            return np.concatenate([audio, audio], axis=0)

        if rows == 2:
            return audio  # already stereo, channel-first

        # More than 2 channels — discard beyond the first two
        logger.warning(
            "%d-channel input — using channels 0 and 1, discarding the rest",
            rows,
        )
        return audio[:2, :]

    raise IngestError(
        f"unexpected audio array shape {audio.shape} from decoder; "
        "expected 1-D (mono) or 2-D (channel × samples) array"
    )


# ── Step 4: resample ──────────────────────────────────────────────────────────

def _resample(audio: np.ndarray, native_sr: int, path: Path) -> np.ndarray:
    """
    Resample both channels to TARGET_SR (44 100 Hz) using kaiser_best.

    kaiser_best is librosa's highest-quality resampler — resampy under the
    hood, equivalent to SoX's sinc_best.  At production volume we can revisit
    soxr_hq (lower latency, similar quality) when the dependency ships cleanly
    on all target platforms.

    Identity case (native_sr == TARGET_SR) returns the input unchanged; no
    copy is made.
    """
    if native_sr == TARGET_SR:
        logger.debug("native sr=%d Hz — skipping resample", TARGET_SR)
        return audio

    logger.debug("resampling %s: %d Hz → %d Hz", path.name, native_sr, TARGET_SR)

    try:
        resampled = librosa.resample(
            audio,
            orig_sr=native_sr,
            target_sr=TARGET_SR,
            res_type="kaiser_best",
        )
    except Exception as exc:
        raise IngestError(
            f"resampling failed for {path.name} "
            f"({native_sr} Hz → {TARGET_SR} Hz): {exc}"
        ) from exc

    return resampled.astype(np.float32)


# ── Step 5: float32 + clip ────────────────────────────────────────────────────

def _normalise(audio: np.ndarray, path: Path) -> np.ndarray:
    """
    Ensure dtype=float32 and values ∈ [-1.0, 1.0].

    Non-finite values (NaN, ±inf) are detected and raised as IngestError
    before clipping — np.clip(±inf) = ±1.0 would otherwise silently mask
    corrupt source data.

    Pre-clipped audio (finite peak > 1.0) is detected and logged before
    clipping.  We do not attempt repair — brick-wall limiting is a mastering
    concern.
    """
    audio = audio.astype(np.float32)

    # Non-finite check must come before clip — inf clips silently to ±1.0
    if not np.all(np.isfinite(audio)):
        n_bad = int(np.sum(~np.isfinite(audio)))
        raise IngestError(
            f"{path.name} contains {n_bad} non-finite sample(s) "
            "(NaN or ±inf) — the source file may be corrupt or truncated"
        )

    peak = float(np.max(np.abs(audio)))

    if peak > 1.0:
        logger.warning(
            "pre-clipped audio in %s (peak=%.5f) — clipping to [-1.0, 1.0]",
            path.name, peak,
        )
    elif peak >= CLIP_WARN_THRESHOLD:
        logger.debug(
            "%s approaches full scale (peak=%.5f)", path.name, peak
        )

    return np.clip(audio, -1.0, 1.0)


# ── Step 6: post-load validation ──────────────────────────────────────────────

def _validate(audio: np.ndarray, path: Path) -> None:
    """
    Assert the full output contract before returning to the caller.

    Checks (in order, failing fast):
        1. shape is (2, N) — exactly two channels, at least one sample
        2. dtype is float32
        3. all values are finite (no NaN or ±inf)
        4. duration ≥ MIN_DURATION_S

    A shape or dtype failure here is a bug in the ingest stage itself.
    A NaN/inf failure or duration failure is a property of the input file.
    The error messages distinguish these two cases.
    """
    # 1. Shape
    if audio.ndim != 2 or audio.shape[0] != 2:
        raise IngestError(
            f"post-normalisation shape {audio.shape} is not (2, N) — "
            "this is an ingest stage bug, not an input file error"
        )

    # 2. dtype
    if audio.dtype != np.float32:
        raise IngestError(
            f"post-normalisation dtype is {audio.dtype}, expected float32 — "
            "this is an ingest stage bug, not an input file error"
        )

    # 3. Finite values
    if not np.all(np.isfinite(audio)):
        n_bad = int(np.sum(~np.isfinite(audio)))
        raise IngestError(
            f"{path.name} contains {n_bad} non-finite sample(s) "
            "(NaN or ±inf) — the source file may be corrupt or truncated"
        )

    # 4. Minimum duration
    n_samples = audio.shape[1]
    duration_s = n_samples / TARGET_SR
    if duration_s < MIN_DURATION_S:
        raise IngestError(
            f"{path.name} is too short "
            f"({duration_s:.3f}s < {MIN_DURATION_S}s minimum) — "
            "provide at least one second of audio"
        )
