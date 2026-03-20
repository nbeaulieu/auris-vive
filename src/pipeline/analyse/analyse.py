"""
Analyse stage — per-stem visualisation curve extraction.

Accepts the separated stems dict and returns a StemCurves object per stem.
Uses librosa, numpy, and scipy only — no ML dependencies.

Contract
--------
    input  : stems: dict[str, np.ndarray]  shape=(2, N)  dtype=float32  sr=44100
    output : dict[str, StemCurves]  same keys as input
"""

from __future__ import annotations

import logging

import time

import librosa
import numpy as np
from scipy.signal import butter, sosfiltfilt

from src.pipeline.analyse.curves import AnalyseError, StemCurves

logger = logging.getLogger(__name__)

TARGET_SR: int = 44_100
DEFAULT_FPS: int = 100
_WARMTH_CUTOFF: float = 300.0  # Hz — boundary for low-frequency energy
_PITCH_FMIN: float = librosa.note_to_hz("C2")   # ~65 Hz
_PITCH_FMAX: float = librosa.note_to_hz("C7")   # ~2093 Hz
_DRUMS_STEMS: frozenset[str] = frozenset({"drums"})


# ── Public interface ──────────────────────────────────────────────────────────

def analyse(
    stems: dict[str, np.ndarray],
    sr: int = TARGET_SR,
    fps: int = DEFAULT_FPS,
) -> dict[str, StemCurves]:
    """
    Extract six normalised visualisation curves from each stem.

    Parameters
    ----------
    stems : dict[str, np.ndarray]
        Output of the separate stage.  Each value is shape=(2, N), float32.
    sr : int
        Sample rate of the stems.
    fps : int
        Target frames per second for the output curves.

    Returns
    -------
    dict[str, StemCurves]
        One StemCurves per stem, keyed identically to the input.

    Raises
    ------
    AnalyseError
        Any failure during feature extraction.
    """
    if not isinstance(stems, dict):
        raise AnalyseError(
            f"expected dict[str, np.ndarray], got {type(stems).__name__}"
        )

    hop_length = sr // fps
    result: dict[str, StemCurves] = {}

    for stem_name, stem in stems.items():
        if not isinstance(stem, np.ndarray):
            raise AnalyseError(
                f"stem '{stem_name}' is {type(stem).__name__}, expected np.ndarray"
            )
        try:
            result[stem_name] = _extract_curves(
                stem, sr, hop_length, fps, stem_name,
            )
        except AnalyseError:
            raise
        except Exception as exc:
            raise AnalyseError(
                f"curve extraction failed for '{stem_name}': {exc}"
            ) from exc

    logger.info("analyse complete  stems=%s  fps=%d", list(result.keys()), fps)
    return result


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_curves(
    stem: np.ndarray,
    sr: int,
    hop_length: int,
    fps: int,
    stem_name: str = "",
) -> StemCurves:
    """Extract all seven curves from a single stem waveform."""
    # Mix to mono for spectral features
    mono = stem.mean(axis=0) if stem.ndim == 2 else stem

    # RMS energy
    rms = librosa.feature.rms(y=mono, hop_length=hop_length)[0]
    energy = _normalise(_apply_envelope(rms))

    # Spectral centroid → brightness
    centroid = librosa.feature.spectral_centroid(
        y=mono, sr=sr, hop_length=hop_length,
    )[0]
    brightness = _normalise(_apply_envelope(centroid))

    # Onset strength
    onset_env = librosa.onset.onset_strength(
        y=mono, sr=sr, hop_length=hop_length,
    )
    onset = _normalise(_apply_envelope(onset_env))

    # Warmth — ratio of energy below _WARMTH_CUTOFF to total energy
    warmth_raw = _low_energy_ratio(mono, sr, hop_length)
    warmth = _normalise(_apply_envelope(warmth_raw))

    # Spectral flatness → texture (0 = tonal, 1 = noisy)
    flatness = librosa.feature.spectral_flatness(
        y=mono, hop_length=hop_length,
    )[0]
    texture = _normalise(_apply_envelope(flatness))

    # Spectral flux
    S = np.abs(librosa.stft(mono, hop_length=hop_length))
    flux_raw = np.sqrt(np.sum(np.diff(S, axis=1) ** 2, axis=0))
    # Pad to match other features (diff removes one frame)
    flux_raw = np.concatenate([[0.0], flux_raw])
    flux = _normalise(_apply_envelope(flux_raw))

    # Pitch — pyin on pitched stems, zeros for drums
    pitch_curve = _extract_pitch(mono, sr, hop_length, stem_name)

    # Align all curves to the shortest length (off-by-one from different features)
    min_len = min(len(energy), len(brightness), len(onset),
                  len(warmth), len(texture), len(flux), len(pitch_curve))
    return StemCurves(
        energy=energy[:min_len],
        brightness=brightness[:min_len],
        onset=onset[:min_len],
        warmth=warmth[:min_len],
        texture=texture[:min_len],
        flux=flux[:min_len],
        pitch_curve=pitch_curve[:min_len],
        fps=fps,
        sr=sr,
    )


# ── Pitch extraction ──────────────────────────────────────────────────────────

def _extract_pitch(
    mono: np.ndarray,
    sr: int,
    hop_length: int,
    stem_name: str,
) -> np.ndarray:
    """
    Extract normalised fundamental frequency curve via librosa.pyin.

    Returns zeros for drum stems (unpitched — pyin output is meaningless).
    Unvoiced frames are set to 0.0; voiced frames are normalised by fmax.
    """
    n_frames = 1 + len(mono) // hop_length

    if stem_name in _DRUMS_STEMS:
        return np.zeros(n_frames, dtype=np.float32)

    t0 = time.monotonic()
    f0, _voiced_flag, _voiced_probs = librosa.pyin(
        mono,
        fmin=_PITCH_FMIN,
        fmax=_PITCH_FMAX,
        sr=sr,
        hop_length=hop_length,
        fill_na=np.nan,
    )
    elapsed = time.monotonic() - t0
    logger.info("pitch extraction: %s  (%.1fs)", stem_name, elapsed)

    # NaN → 0.0 (unvoiced), then normalise voiced frames to [0, 1]
    f0 = np.where(np.isnan(f0), 0.0, f0)
    f0 = np.clip(f0 / _PITCH_FMAX, 0.0, 1.0)

    return _apply_envelope(f0).astype(np.float32)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_envelope(
    frames: np.ndarray,
    attack: float = 0.3,
    release: float = 0.1,
) -> np.ndarray:
    """
    Exponential envelope follower.

    Each frame depends on the previous frame, so this is the one unavoidable
    loop.  At 100 fps x 30s = 3000 frames it runs in < 1ms.
    """
    if len(frames) == 0:
        return frames.astype(np.float32)
    out = np.empty(len(frames), dtype=np.float64)
    out[0] = float(frames[0])
    for i in range(1, len(frames)):
        coeff = attack if frames[i] > out[i - 1] else release
        out[i] = coeff * frames[i] + (1.0 - coeff) * out[i - 1]
    return out.astype(np.float32)


def _normalise(x: np.ndarray) -> np.ndarray:
    """Scale array to [0.0, 1.0] float32.  Constant signals map to zeros."""
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-10:
        return np.zeros(len(x), dtype=np.float32)
    return ((x - lo) / (hi - lo)).astype(np.float32)


def _low_energy_ratio(
    mono: np.ndarray,
    sr: int,
    hop_length: int,
) -> np.ndarray:
    """
    Per-frame ratio of energy below _WARMTH_CUTOFF Hz to total energy.

    Uses a Butterworth lowpass to isolate the low band, then computes
    windowed RMS of both the filtered and original signals.
    """
    # Butterworth lowpass at _WARMTH_CUTOFF
    nyquist = sr / 2.0
    if _WARMTH_CUTOFF >= nyquist:
        # Everything is below cutoff — warmth is 1.0 everywhere
        n_frames = 1 + len(mono) // hop_length
        return np.ones(n_frames, dtype=np.float32)

    sos = butter(4, _WARMTH_CUTOFF / nyquist, btype="low", output="sos")
    low = sosfiltfilt(sos, mono).astype(np.float32)

    rms_total = librosa.feature.rms(y=mono, hop_length=hop_length)[0]
    rms_low = librosa.feature.rms(y=low, hop_length=hop_length)[0]

    # Avoid division by zero — silent frames get warmth 0
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(rms_total > 1e-10, rms_low / rms_total, 0.0)

    return ratio.astype(np.float32)
