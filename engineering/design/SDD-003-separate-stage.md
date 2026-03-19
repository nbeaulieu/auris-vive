# SDD-003 — Separate stage design

| Field      | Value                                                        |
|------------|--------------------------------------------------------------|
| Status     | Draft                                                        |
| Date       | 2026-03-19                                                   |
| Relates to | ADR-001 (stack), ADR-002 (inference backend), ADR-003 (drums) |
| Covers     | Pipeline stage 2: source separation via Demucs               |

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Context: where separate sits in the pipeline](#2-context-where-separate-sits-in-the-pipeline)
3. [Model strategy](#3-model-strategy)
4. [Device selection](#4-device-selection)
5. [Singleton model loading](#5-singleton-model-loading)
6. [Parallel inference and progressive delivery](#6-parallel-inference-and-progressive-delivery)
7. [Output contract](#7-output-contract)
8. [Error handling](#8-error-handling)
9. [Full implementation](#9-full-implementation)
10. [Testing requirements](#10-testing-requirements)
11. [Open questions](#11-open-questions)

---

## 1. Purpose and scope

The separate stage accepts the normalised stereo array from ingest and returns
per-stem waveforms using Demucs neural source separation. It is responsible for:

- Loading and managing two Demucs models as process-level singletons
- Running both models in parallel on the available compute device
- Returning a complete set of six stems: `drums`, `bass`, `vocals`, `other`,
  `piano`, `guitar`
- Signalling which stems are available progressively so the API layer can
  push partial results to clients via WebSocket

**What this stage is not responsible for:**

- Device provisioning — the device is determined by the selection layer and
  passed in explicitly
- Job queuing or scheduling — that is the job queue's concern (SDD-006)
- Any form of audio enhancement before or after separation
- Transcription — that is the next stage (SDD-004)

---

## 2. Context: where separate sits in the pipeline

```
Ingest stage
  │  np.ndarray  shape=(2, N)  dtype=float32  sr=44100
  ▼
┌──────────────────────────────────────────────────────────────────┐
│  SEPARATE STAGE                                                  │
│                                                                  │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐  │
│  │ htdemucs_ft             │  │ htdemucs_6s                  │  │
│  │ → drums                 │  │ → piano  ◄── keep            │  │
│  │ → bass                  │  │ → guitar ◄── keep            │  │
│  │ → vocals                │  │ → drums  ┐                   │  │
│  │ → other                 │  │ → bass   │ discard —         │  │
│  └──────────┬──────────────┘  │ → vocals │ htdemucs_ft       │  │
│             │ fast path       │ → other  ┘ is authoritative  │  │
│             │ (~25-40s)       └──────────┬───────────────────┘  │
│             │                            │ slow path (~25-40s)  │
│             ▼                            ▼                      │
│       emit: drums/bass/vocals/other    emit: piano/guitar       │
└──────────────────────────────────────────────────────────────────┘
  │  dict[str, np.ndarray]  (6 stems total)
  ▼
Transcribe stage (SDD-004)
```

Both models run in parallel. `htdemucs_ft` is authoritative for the core 4
stems. Only `piano` and `guitar` are taken from `htdemucs_6s` — its versions
of the shared stems are discarded.

---

## 3. Model strategy

### Why two models

`htdemucs` (the base 4-stem model) and `htdemucs_6s` (the 6-stem model that
adds piano and guitar) represent a quality tradeoff:

- `htdemucs_ft` is a fine-tuned ensemble of 4 `htdemucs` variants. It
  produces demonstrably higher quality on the core stems (drums, bass,
  vocals, other) than either the base model or the 6-stem model.
- `htdemucs_6s` adds piano and guitar as explicit stems but slightly degrades
  quality on the core stems compared to `htdemucs_ft`, because the model
  must partition the audio into 6 parts instead of 4.

The solution: use each model for what it does best. `htdemucs_ft` owns the
4 core stems. `htdemucs_6s` contributes only piano and guitar. The overlapping
stem outputs from `htdemucs_6s` are discarded.

### Model specifications

| Model | Stems | Weights size | Notes |
|-------|-------|-------------|-------|
| `htdemucs_ft` | drums, bass, vocals, other | ~320MB (4-model ensemble) | Fine-tuned, highest quality on core stems |
| `htdemucs_6s` | drums, bass, vocals, other, piano, guitar | ~80MB | Only piano + guitar used |

Both sets of weights are cached on the Modal Volume at first load. Subsequent
cold starts load from the volume (~3–5s) rather than downloading (~30s+).

### GPU memory budget (T4, 16GB)

| Item | Memory |
|------|--------|
| `htdemucs_ft` (4 models) | ~1.2GB |
| `htdemucs_6s` | ~300MB |
| Audio buffers (4-min track) | ~200MB |
| OS + CUDA overhead | ~1GB |
| **Total** | **~2.7GB** |

Well within T4's 16GB. Both models can be resident simultaneously.

---

## 4. Device selection

Device is selected via the `AURIS_DEVICE` environment variable:

| Value | Behaviour |
|-------|-----------|
| `cpu` | Force CPU. Used in dev and CI. |
| `cuda` | Force CUDA GPU. Raises at startup if unavailable. |
| `mps` | Force Apple Silicon GPU. Raises at startup if unavailable. |
| `auto` | Detect at runtime: CUDA → MPS → CPU. Default in production. |

```python
import os
import torch

def select_device() -> torch.device:
    setting = os.environ.get("AURIS_DEVICE", "auto").lower()

    if setting == "cpu":
        return torch.device("cpu")
    if setting == "cuda":
        if not torch.cuda.is_available():
            raise SeparateError("AURIS_DEVICE=cuda but CUDA is not available")
        return torch.device("cuda")
    if setting == "mps":
        if not torch.backends.mps.is_available():
            raise SeparateError("AURIS_DEVICE=mps but MPS is not available")
        return torch.device("mps")
    if setting == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        logger.warning(
            "no GPU detected (AURIS_DEVICE=auto) — falling back to CPU. "
            "Expect ~10 min inference for a 4-minute track."
        )
        return torch.device("cpu")

    raise SeparateError(f"unknown AURIS_DEVICE value: '{setting}' — "
                        "expected cpu | cuda | mps | auto")
```

The device is selected once at module import and passed explicitly into the
separation functions. Tests set `AURIS_DEVICE=cpu` via `pytest` fixtures or
`conftest.py` — no GPU required to run the test suite.

---

## 5. Singleton model loading

Both models are loaded as module-level singletons via lazy init functions.
This ensures:

- In Modal containers that stay warm, models remain resident in GPU memory
  between jobs — subsequent jobs pay only inference time, not load time
- In cold-start containers, models load from the cached Volume once and are
  then resident for the lifetime of the process
- In local dev, models load on first job and stay loaded for the session

```python
import threading
from demucs.pretrained import get_model

_ft_model = None
_6s_model = None
_lock = threading.Lock()

def _get_ft_model(device: torch.device):
    global _ft_model
    if _ft_model is None:
        with _lock:
            if _ft_model is None:
                logger.info("loading htdemucs_ft — first call, may take a moment")
                _ft_model = get_model("htdemucs_ft")
                _ft_model.to(device)
                _ft_model.eval()
    return _ft_model

def _get_6s_model(device: torch.device):
    global _6s_model
    if _6s_model is None:
        with _lock:
            if _6s_model is None:
                logger.info("loading htdemucs_6s — first call, may take a moment")
                _6s_model = get_model("htdemucs_6s")
                _6s_model.to(device)
                _6s_model.eval()
    return _6s_model
```

The double-checked lock pattern prevents race conditions when multiple threads
call `_get_ft_model()` simultaneously on the first invocation.

---

## 6. Parallel inference and progressive delivery

Both models run concurrently using `concurrent.futures.ThreadPoolExecutor`.
PyTorch releases the GIL during inference, so threading (not multiprocessing)
is sufficient for genuine parallelism on GPU.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def separate(
    audio: np.ndarray,
    device: torch.device,
    on_stems_ready: Callable[[dict[str, np.ndarray]], None] | None = None,
) -> dict[str, np.ndarray]:
    ...
```

The optional `on_stems_ready` callback is how the separation stage signals
progressive availability to the caller (the job runner, which forwards to
the WebSocket layer). It is called twice:

1. When `htdemucs_ft` completes → `{"drums": ..., "bass": ..., "vocals": ..., "other": ...}`
2. When `htdemucs_6s` completes → `{"piano": ..., "guitar": ...}`

The WebSocket protocol (SDD-006) emits a `stems_ready` event on each callback:

```json
{ "event": "stems_ready", "stems": ["drums", "bass", "vocals", "other"] }
{ "event": "stems_ready", "stems": ["piano", "guitar"] }
{ "event": "job_complete" }
```

This enables the visual layer to begin rendering the core stems immediately
while piano and guitar are still being separated — the user sees the
visualisation start ~25–40s into processing rather than waiting for the full
~50–60s.

If `on_stems_ready` is `None` (e.g. in batch processing or tests), the
callback is simply skipped and the function returns when both models complete.

---

## 7. Output contract

```
input  : audio: np.ndarray  shape=(2, N)  dtype=float32  sr=44100
         device: torch.device
         on_stems_ready: Callable | None

output : dict[str, np.ndarray]
           keys   : "drums" | "bass" | "vocals" | "other" | "piano" | "guitar"
           values : np.ndarray  shape=(2, N')  dtype=float32  sr=44100
```

**N vs N':** Demucs applies internal padding during inference. The output
sample count N' may differ from the input N by a small amount (typically
≤ 512 samples at 44100 Hz — less than 12ms). Downstream stages must tolerate
this. The pipeline runner trims all stems to the shortest length after
separation to ensure consistent N across all stems.

**Stem provenance:**

| Stem | Source model |
|------|-------------|
| drums | htdemucs_ft |
| bass | htdemucs_ft |
| vocals | htdemucs_ft |
| other | htdemucs_ft |
| piano | htdemucs_6s |
| guitar | htdemucs_6s |

---

## 8. Error handling

All failures raise `SeparateError` with a descriptive message. No internal
exception escapes the module boundary.

| Condition | `SeparateError` message |
|-----------|------------------------|
| Invalid device setting | `"unknown AURIS_DEVICE value: '{val}'"` |
| CUDA requested but unavailable | `"AURIS_DEVICE=cuda but CUDA is not available"` |
| Model download/load failure | `"failed to load {model_name}: {detail}"` |
| Inference failure | `"inference failed for {model_name}: {detail}"` |
| Input shape violation | `"expected (2, N) float32 array, got shape {shape}"` |
| OOM on GPU | `"out of memory during {model_name} inference — try a shorter clip or CPU"` |

OOM deserves special handling — torch raises `torch.cuda.OutOfMemoryError`
which should be caught explicitly and converted to a descriptive `SeparateError`
that names the remedy.

---

## 9. Full implementation

```python
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

STEMS_FT = ("drums", "bass", "vocals", "other")
STEMS_6S = ("piano", "guitar")
ALL_STEMS = STEMS_FT + STEMS_6S


class SeparateError(Exception):
    """Domain exception for the separate stage."""


# ── Device selection ──────────────────────────────────────────────────────────

def select_device() -> torch.device:
    """
    Select compute device from AURIS_DEVICE environment variable.

    AURIS_DEVICE=cpu    Force CPU (default in dev/CI via conftest.py)
    AURIS_DEVICE=cuda   Force CUDA GPU
    AURIS_DEVICE=mps    Force Apple Silicon GPU
    AURIS_DEVICE=auto   Detect: CUDA → MPS → CPU (default in production)
    """
    setting = os.environ.get("AURIS_DEVICE", "auto").lower()

    if setting == "cpu":
        return torch.device("cpu")

    if setting == "cuda":
        if not torch.cuda.is_available():
            raise SeparateError("AURIS_DEVICE=cuda but CUDA is not available")
        return torch.device("cuda")

    if setting == "mps":
        if not torch.backends.mps.is_available():
            raise SeparateError("AURIS_DEVICE=mps but MPS is not available")
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
            "Set AURIS_DEVICE=cuda for production or AURIS_DEVICE=mps on Apple Silicon."
        )
        return torch.device("cpu")

    raise SeparateError(
        f"unknown AURIS_DEVICE value: '{setting}' — expected cpu | cuda | mps | auto"
    )


# ── Singleton model registry ──────────────────────────────────────────────────

_models: dict[str, object] = {}
_lock = threading.Lock()


def _get_model(name: str, device: torch.device):
    """
    Load and cache a Demucs model as a process-level singleton.

    Thread-safe via double-checked locking. In Modal warm containers,
    the model remains resident in GPU memory between jobs.
    """
    if name not in _models:
        with _lock:
            if name not in _models:
                logger.info("loading %s — first call, loading weights", name)
                try:
                    from demucs.pretrained import get_model
                    model = get_model(name)
                    model.to(device)
                    model.eval()
                    _models[name] = model
                    logger.info("loaded %s", name)
                except Exception as exc:
                    raise SeparateError(f"failed to load {name}: {exc}") from exc
    return _models[name]


# ── Core separation ───────────────────────────────────────────────────────────

def _run_model(
    model_name: str,
    audio: np.ndarray,
    device: torch.device,
    stem_names: tuple[str, ...],
) -> dict[str, np.ndarray]:
    """
    Run a single Demucs model and return requested stems.

    Parameters
    ----------
    model_name : Demucs model identifier (e.g. "htdemucs_ft")
    audio      : shape=(2, N)  float32  sr=44100
    device     : torch.device
    stem_names : which stems to return from this model's output

    Returns
    -------
    dict[str, np.ndarray]  — only the requested stems
    """
    from demucs.apply import apply_model
    from demucs.audio import convert_audio

    model = _get_model(model_name, device)

    # Convert numpy array to torch tensor with batch dimension: (1, 2, N)
    wav = torch.from_numpy(audio).unsqueeze(0).to(device)

    # Resample to model's native sample rate if it differs (htdemucs uses 44100)
    wav = convert_audio(wav, 44100, model.samplerate, model.audio_channels)

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

    # sources shape: (1, n_stems, 2, N) — remove batch dimension
    sources = sources.squeeze(0)

    # Map model stem index to name
    stem_index = {name: i for i, name in enumerate(model.sources)}

    result = {}
    for name in stem_names:
        if name not in stem_index:
            raise SeparateError(
                f"stem '{name}' not in {model_name} output "
                f"(available: {list(model.sources)})"
            )
        stem_audio = sources[stem_index[name]].cpu().numpy()  # (2, N')
        result[name] = stem_audio.astype(np.float32)

    return result


def _trim_to_shortest(stems: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Trim all stems to the shortest sample count.

    Demucs applies internal padding; output N' may vary slightly between
    models and runs. This ensures a consistent N across all stems.
    """
    min_len = min(v.shape[1] for v in stems.values())
    return {k: v[:, :min_len] for k, v in stems.items()}


# ── Public interface ──────────────────────────────────────────────────────────

def separate(
    audio: np.ndarray,
    device: torch.device | None = None,
    on_stems_ready: Callable[[dict[str, np.ndarray]], None] | None = None,
) -> dict[str, np.ndarray]:
    """
    Run source separation on a normalised stereo audio array.

    Runs htdemucs_ft and htdemucs_6s in parallel. htdemucs_ft is authoritative
    for drums/bass/vocals/other. Only piano and guitar are taken from htdemucs_6s.

    Parameters
    ----------
    audio : np.ndarray
        Normalised stereo array from ingest.
        shape=(2, N), dtype=float32, sr=44100.
    device : torch.device | None
        Compute device. If None, select_device() is called automatically.
    on_stems_ready : Callable | None
        Optional callback invoked as each model completes.
        Called twice: first with the 4 core stems, then with piano + guitar.
        Used by the job runner to push progressive WebSocket events to clients.

    Returns
    -------
    dict[str, np.ndarray]
        Six stems: drums, bass, vocals, other, piano, guitar.
        Each shape=(2, N'), dtype=float32.

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
        device, audio.shape[1] / 44100,
    )

    all_stems: dict[str, np.ndarray] = {}

    def run_ft():
        stems = _run_model("htdemucs_ft", audio, device, STEMS_FT)
        if on_stems_ready:
            on_stems_ready(stems)
        return stems

    def run_6s():
        stems = _run_model("htdemucs_6s", audio, device, STEMS_6S)
        if on_stems_ready:
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
        "separate complete  stems=%s  shape=%s",
        list(all_stems.keys()), next(iter(all_stems.values())).shape,
    )

    return all_stems
```

---

## 10. Testing requirements

| TC | Input | Expected output |
|----|-------|----------------|
| TC-SEP-001 | Valid (2, N) float32 array, AURIS_DEVICE=cpu, models mocked | Returns dict with all 6 stem keys |
| TC-SEP-002 | Valid input, models mocked | All stem arrays are float32 |
| TC-SEP-003 | Valid input, models mocked | All stem arrays have shape (2, N') |
| TC-SEP-004 | Valid input, models mocked | on_stems_ready called exactly twice |
| TC-SEP-005 | Valid input, models mocked | First callback contains drums/bass/vocals/other |
| TC-SEP-006 | Valid input, models mocked | Second callback contains piano/guitar |
| TC-SEP-007 | Valid input, ft model longer than 6s model | Output trimmed to shortest — all stems same N |
| TC-SEP-008 | Wrong input shape (1, N) | SeparateError raised |
| TC-SEP-009 | AURIS_DEVICE=cuda, no CUDA available | SeparateError with descriptive message |
| TC-SEP-010 | AURIS_DEVICE=invalid | SeparateError naming the bad value |
| TC-SEP-011 | Model load raises exception | SeparateError wraps it, original in __cause__ |
| TC-SEP-012 | Inference raises OOM | SeparateError mentions remedy (shorter clip / CPU) |
| TC-SEP-013 | select_device() with AURIS_DEVICE=auto, no GPU | Returns cpu device, logs warning |
| TC-SEP-014 | select_device() with AURIS_DEVICE=cpu | Returns cpu device, no warning |

All tests mock `demucs.pretrained.get_model` and `demucs.apply.apply_model`
so the test suite runs without GPU, without model weights, and without the
`[ml]` dependency group installed (mocks are registered at import time via
`unittest.mock.patch`).

---

## 11. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-SEP-2 | Thread safety of Demucs models under concurrent inference — is `apply_model` safe to call from multiple threads with separate model instances? | ML | Pre-implementation |
| Q-SEP-3 | On MPS (Apple Silicon), does `apply_model` work correctly or does it require `mps` → `cpu` fallback for unsupported ops? | ML | Dev testing |
| Q-SEP-4 | What is the keep-alive TTL for Modal containers to balance cold-start cost vs idle GPU cost? | Infrastructure | ADR-002 Q-MODAL-1 |
| Q-SEP-5 | Should `_trim_to_shortest` log a warning when the length difference exceeds a threshold (e.g. > 100 samples)? | Engineering | Implementation |

---

*Document owner: Architecture team — update when implementation deviates from this spec.*
