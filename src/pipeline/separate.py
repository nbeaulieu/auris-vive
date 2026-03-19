"""
Separate stage — SDD-003

Accepts the normalised stereo array from ingest and returns per-stem waveforms
via two Demucs models running in parallel.

Contract
--------
    input  : audio: np.ndarray  shape=(2, N)  dtype=float32  sr=44100
             device: torch.device  (from select_device())
    output : dict[str, np.ndarray]
               keys   : "drums" | "bass" | "vocals" | "other" | "piano" | "guitar"
               values : shape=(2, N')  dtype=float32  sr=44100

Model strategy
--------------
    htdemucs_ft  → drums, bass, vocals, other  (authoritative for core stems)
    htdemucs_6s  → piano, guitar only          (core stem output discarded)

Both models run in parallel via ThreadPoolExecutor. PyTorch releases the GIL
during inference so threading provides genuine parallelism on GPU.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import torch

logger = logging.getLogger(__name__)

STEMS_FT: tuple[str, ...] = ("drums", "bass", "vocals", "other")
STEMS_6S: tuple[str, ...] = ("piano", "guitar")
ALL_STEMS: tuple[str, ...] = STEMS_FT + STEMS_6S

_DEMUCS_SR = 44_100


class SeparateError(Exception):
    """Domain exception for the separate stage."""


# ── Device selection ──────────────────────────────────────────────────────────

def select_device() -> torch.device:
    """
    Select compute device from AURIS_DEVICE environment variable.

        AURIS_DEVICE=cpu    Force CPU — default in dev / CI
        AURIS_DEVICE=cuda   Force CUDA GPU
        AURIS_DEVICE=mps    Force Apple Silicon GPU
        AURIS_DEVICE=auto   Detect: CUDA -> MPS -> CPU (production default)
    """
    setting = os.environ.get("AURIS_DEVICE", "auto").lower()

    if setting == "cpu":
        logger.debug("device: CPU (forced via AURIS_DEVICE=cpu)")
        return torch.device("cpu")

    if setting == "cuda":
        if not torch.cuda.is_available():
            raise SeparateError("AURIS_DEVICE=cuda but CUDA is not available")
        logger.info("device: CUDA (%s)", torch.cuda.get_device_name(0))
        return torch.device("cuda")

    if setting == "mps":
        if not torch.backends.mps.is_available():
            raise SeparateError("AURIS_DEVICE=mps but MPS is not available")
        logger.info("device: Apple MPS")
        return torch.device("mps")

    if setting == "auto":
        if torch.cuda.is_available():
            logger.info("device: CUDA (%s)", torch.cuda.get_device_name(0))
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            logger.info("device: Apple MPS")
            return torch.device("mps")
        logger.warning(
            "no GPU detected (AURIS_DEVICE=auto) — falling back to CPU. "
            "Expect ~10 min inference for a 4-minute track. "
            "Set AURIS_DEVICE=cuda for production or AURIS_DEVICE=mps "
            "on Apple Silicon."
        )
        return torch.device("cpu")

    raise SeparateError(
        f"unknown AURIS_DEVICE value: '{setting}' — "
        "expected cpu | cuda | mps | auto"
    )


# ── Singleton model registry ──────────────────────────────────────────────────

_models: dict[str, object] = {}
_lock = threading.Lock()


def _get_model(name: str, device: torch.device) -> object:
    """
    Load and cache a Demucs model as a process-level singleton.
    Thread-safe via double-checked locking.
    """
    if name not in _models:
        with _lock:
            if name not in _models:
                logger.info("loading %s — first call, may take a moment", name)
                try:
                    from demucs.pretrained import get_model  # type: ignore[import]
                    model = get_model(name)
                    model.to(device)
                    model.eval()
                    _models[name] = model
                    logger.info("loaded %s", name)
                except Exception as exc:
                    raise SeparateError(f"failed to load {name}: {exc}") from exc
    return _models[name]


def _clear_model_cache() -> None:
    """Evict all cached models. For use in tests only."""
    global _models
    with _lock:
        _models = {}


# ── Core inference ────────────────────────────────────────────────────────────

def _run_model(
    model_name: str,
    audio: np.ndarray,
    device: torch.device,
    stem_names: tuple[str, ...],
) -> dict[str, np.ndarray]:
    """Run a single Demucs model and return only the requested stems."""
    model = _get_model(model_name, device)

    try:
        from demucs.apply import apply_model    # type: ignore[import]
        from demucs.audio import convert_audio  # type: ignore[import]
    except ImportError as exc:
        raise SeparateError(
            f"demucs is not installed — add it via pip install -e '.[ml]': {exc}"
        ) from exc

    wav = torch.from_numpy(audio).unsqueeze(0).to(device)
    wav = convert_audio(wav, _DEMUCS_SR, model.samplerate, model.audio_channels)

    try:
        with torch.no_grad():
            sources = apply_model(model, wav, device=device)
    except torch.cuda.OutOfMemoryError as exc:
        raise SeparateError(
            f"out of memory during {model_name} inference — "
            "try a shorter clip or use AURIS_DEVICE=cpu"
        ) from exc
    except Exception as exc:
        raise SeparateError(f"inference failed for {model_name}: {exc}") from exc

    sources = sources.squeeze(0)  # (n_stems, 2, N')

    stem_index: dict[str, int] = {
        name: i for i, name in enumerate(model.sources)
    }

    result: dict[str, np.ndarray] = {}
    for name in stem_names:
        if name not in stem_index:
            raise SeparateError(
                f"stem '{name}' not available in {model_name} "
                f"(available: {list(model.sources)})"
            )
        result[name] = sources[stem_index[name]].cpu().numpy().astype(np.float32)

    return result


def _trim_to_shortest(stems: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Trim all stems to the shortest sample count to normalise Demucs padding."""
    min_len = min(v.shape[1] for v in stems.values())
    lengths = {k: v.shape[1] for k, v in stems.items()}
    if len(set(lengths.values())) > 1:
        logger.debug("trimming stems to %d samples (was: %s)", min_len, lengths)
    return {k: v[:, :min_len] for k, v in stems.items()}


# ── Public interface ──────────────────────────────────────────────────────────

def separate(
    audio: np.ndarray,
    device: torch.device | None = None,
    on_stems_ready: Callable[[dict[str, np.ndarray]], None] | None = None,
) -> dict[str, np.ndarray]:
    """
    Run source separation on a normalised stereo audio array.

    Parameters
    ----------
    audio           : shape=(2, N)  dtype=float32  sr=44100
    device          : compute device; auto-selected if None
    on_stems_ready  : optional callback invoked as each model completes;
                      called twice (core stems, then piano/guitar) to support
                      progressive WebSocket delivery

    Returns
    -------
    dict[str, np.ndarray]
        Six stems: drums, bass, vocals, other, piano, guitar.
        Each array: shape=(2, N'), dtype=float32.

    Raises
    ------
    SeparateError
        Any failure from device selection through inference.
    """
    if audio.ndim != 2 or audio.shape[0] != 2:
        raise SeparateError(
            f"expected (2, N) float32 array, got shape {audio.shape}"
        )

    if device is None:
        device = select_device()

    logger.info(
        "separate start  device=%s  duration=%.2fs",
        device, audio.shape[1] / _DEMUCS_SR,
    )

    all_stems: dict[str, np.ndarray] = {}

    def run_ft() -> dict[str, np.ndarray]:
        stems = _run_model("htdemucs_ft", audio, device, STEMS_FT)
        if on_stems_ready is not None:
            on_stems_ready(stems)
        return stems

    def run_6s() -> dict[str, np.ndarray]:
        stems = _run_model("htdemucs_6s", audio, device, STEMS_6S)
        if on_stems_ready is not None:
            on_stems_ready(stems)
        return stems

    with ThreadPoolExecutor(max_workers=2) as executor:
        ft_future = executor.submit(run_ft)
        s6_future = executor.submit(run_6s)

        for future in as_completed([ft_future, s6_future]):
            try:
                all_stems.update(future.result())
            except SeparateError:
                raise
            except Exception as exc:
                raise SeparateError(f"separation thread failed: {exc}") from exc

    all_stems = _trim_to_shortest(all_stems)

    logger.info(
        "separate complete  stems=%s  samples=%d",
        list(all_stems.keys()),
        next(iter(all_stems.values())).shape[1],
    )

    return all_stems
