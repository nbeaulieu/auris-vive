# SDD-002 — Ingest stage design

| Field      | Value                                      |
|------------|--------------------------------------------|
| Status     | Draft                                      |
| Date       | 2026-03-19                                 |
| Relates to | ADR-001 (technology stack selection)       |
| Covers     | Pipeline stage 1: audio ingest and normalisation |

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Context: where ingest sits in the pipeline](#2-context-where-ingest-sits-in-the-pipeline)
3. [Supported input formats](#3-supported-input-formats)
4. [Stage 1 — Decode](#4-stage-1--decode)
5. [Stage 2 — Resample](#5-stage-2--resample)
6. [Stage 3 — Convert to float32](#6-stage-3--convert-to-float32)
7. [Stage 4 — Ensure stereo](#7-stage-4--ensure-stereo)
8. [Error handling and validation](#8-error-handling-and-validation)
9. [Full implementation](#9-full-implementation)
10. [Testing requirements](#10-testing-requirements)
11. [Open questions](#11-open-questions)

---

## 1. Purpose and scope

The ingest stage is the first stage of the music analysis pipeline. Its sole responsibility is to accept an audio file path from an input adapter and return a normalised NumPy array that every downstream stage can consume without further transformation.

Ingest does not perform any analysis, separation, or transcription. It is deliberately dumb — a pure normalisation function with no side effects beyond reading a file. Its output is a contract: a `float32` stereo array at 44,100 Hz, shaped `(2, N)`, where values are clipped to `[-1.0, 1.0]`.

Every downstream stage (Demucs source separation, Basic Pitch transcription) is written against this contract. If the contract is met, no downstream stage needs to know or care about the original file format, sample rate, bit depth, or channel configuration.

**What ingest is not responsible for:**

- Fetching audio from URLs, streams, or devices — that is the input adapter's job (see SDD-001)
- Quality assessment of the audio content
- Any form of audio enhancement, noise reduction, or pre-processing
- Persisting the normalised audio to disk

---

## 2. Context: where ingest sits in the pipeline

```
Input adapter
  │  path: str  (absolute path to a local audio file)
  ▼
┌─────────────────────────────────────────────────┐
│  INGEST STAGE                                   │
│  1. Decode       (codec → PCM samples)          │
│  2. Resample     (any rate → 44,100 Hz)         │
│  3. Convert      (int* → float32 [-1, 1])       │
│  4. Ensure stereo (mono → duplicate channel)    │
└─────────────────────────────────────────────────┘
  │  np.ndarray, dtype=float32, shape=(2, N)
  ▼
Separate stage (Demucs)
```

The input adapter is responsible for everything before this — downloading a file from a URL, extracting audio from a video container, reading from a device buffer. By the time control reaches ingest, a path to a readable local file is guaranteed. Ingest does not perform network I/O.

---

## 3. Supported input formats

`librosa.load()` delegates to `soundfile` for most formats and falls back to `audioread` for formats soundfile cannot handle. The combined coverage is:

| Format | Extension | Codec | Notes |
|--------|-----------|-------|-------|
| MP3 | `.mp3` | MPEG Layer III | Lossy. Most common consumer format. Decoded via `audioread` (wraps FFmpeg or GStreamer). |
| WAV | `.wav` | PCM (various bit depths) | Lossless PCM. Handled natively by `soundfile`. Multiple bit depths: 8, 16, 24, 32-bit int and 32-bit float. |
| FLAC | `.flac` | Free Lossless Audio Codec | Lossless compressed. Handled natively by `soundfile`. Preferred format for pipeline outputs. |
| AAC | `.aac`, `.m4a` | Advanced Audio Coding | Lossy. Requires `audioread` with FFmpeg backend. Common in Apple ecosystem. |
| OGG Vorbis | `.ogg` | Vorbis | Lossy open format. Handled by `soundfile`. |
| MP4 audio | `.mp4`, `.m4a` | AAC or ALAC | Requires FFmpeg. Only the audio track is extracted; video is discarded. |
| AIFF | `.aiff`, `.aif` | PCM | Lossless. Apple's equivalent of WAV. Handled by `soundfile`. |

**Operational dependency:** MP3 and MP4 decoding requires FFmpeg to be present in the system PATH. The deployment environment must ensure FFmpeg is installed. Absence of FFmpeg causes `audioread` to raise a `NoBackendError` at runtime, which ingest must catch and convert to a descriptive `IngestError`.

**Formats explicitly not supported:**

- MIDI (`.mid`) — not audio; no waveform to decode
- Video-only formats with no audio track
- DRM-protected files — codec will fail with a permissions error

---

## 4. Stage 1 — Decode

### What decoding does

An audio file on disk is not audio — it is a compressed, encoded representation of audio. The file container (e.g. MP4) wraps one or more codec streams (e.g. AAC). The codec applies a compression algorithm that exploits psychoacoustic properties of human hearing to discard information that is imperceptible.

Decoding reverses this process and produces **PCM (Pulse-Code Modulation)** — a sequence of integer or floating-point samples representing air pressure at uniform time intervals. This is the universal internal representation for digital audio and the format all subsequent stages operate on.

### How librosa handles it

`librosa.load()` inspects the file extension and delegates:

- **`soundfile`** handles WAV, FLAC, OGG, AIFF natively in Python with no external binary dependencies.
- **`audioread`** handles MP3, AAC, MP4 by wrapping whichever backend is available in the environment: FFmpeg (preferred), GStreamer, or Core Audio (macOS only).

The caller does not need to know which backend was used. The result is always a NumPy array of PCM samples.

### What comes out

After decoding, the data is a NumPy array of shape `(N,)` for mono or `(2, N)` for stereo (librosa uses channel-first ordering internally but may return channel-last depending on version — see the implementation section for the explicit transpose guard).

The dtype at this point may be `int16`, `int32`, or `float32` depending on the source file. Bit depth normalisation happens in stage 3.

### Key parameters

```python
librosa.load(
    path,
    sr=44100,      # target sample rate — triggers resampling if file differs
    mono=False,    # preserve stereo; do not mix down channels
    dtype=np.float32  # request float32 output directly where possible
)
```

Setting `sr=44100` tells librosa to resample during load if the file's native rate differs. This is convenient but means decoding and resampling happen in a single call. If you need the original sample rate for diagnostic logging, call with `sr=None` first, log `sr`, then resample explicitly.

---

## 5. Stage 2 — Resample

### Why resampling is necessary

Audio files arrive at many different sample rates:

| Source | Typical sample rate |
|--------|-------------------|
| CD audio, most music files | 44,100 Hz |
| Video production, broadcast | 48,000 Hz |
| Telephone / voice codec | 8,000 – 16,000 Hz |
| High-resolution audio | 88,200 Hz, 96,000 Hz |
| Old web audio / podcasts | 22,050 Hz |

Demucs (`htdemucs`) was trained exclusively on 44,100 Hz audio. Its internal convolutional layers have learned filter responses calibrated to that rate. Feeding 48,000 Hz audio without resampling shifts every frequency relationship by a factor of 48000/44100 ≈ 1.088 — bass sounds higher, harmonics misalign, and source separation quality degrades materially.

### How resampling works

Resampling is not simply "dropping samples" (downsampling) or "repeating samples" (naive upsampling). Both produce aliasing artefacts. The correct algorithm is:

1. **Anti-aliasing filter** — apply a low-pass filter to remove frequencies above the target Nyquist frequency (`target_sr / 2`). For downsampling from 48 kHz to 44.1 kHz, this removes everything above 22,050 Hz, which is inaudible to humans.
2. **Polyphase interpolation** — reconstruct the signal at the new sample positions using sinc interpolation. librosa uses `resampy` for high-quality resampling by default, which implements the Kaiser-windowed sinc filter.

The result is mathematically equivalent to what you would have recorded if the original signal had been captured at the target rate. No perceptible information is lost for music audio.

### The Nyquist theorem

The sample rate sets a hard ceiling on representable frequency: `f_max = sample_rate / 2`. This is the Nyquist theorem. At 44,100 Hz, the maximum representable frequency is 22,050 Hz — safely above the 20,000 Hz upper limit of human hearing. This is why 44,100 Hz became the standard for audio that "sounds complete" to humans.

### Resampling in practice

When `sr=44100` is passed to `librosa.load()`, resampling is performed during load if the file's native rate differs. The quality of resampling can be tuned:

```python
# High quality (default) — uses resampy with Kaiser-best window
audio, sr = librosa.load(path, sr=44100, mono=False, res_type='kaiser_best')

# Faster, slightly lower quality — use for development / testing
audio, sr = librosa.load(path, sr=44100, mono=False, res_type='kaiser_fast')
```

For production, `kaiser_best` is required. `kaiser_fast` is acceptable in CI test pipelines where speed matters more than fidelity.

---

## 6. Stage 3 — Convert to float32

### Why float32 in `[-1.0, 1.0]`?

Audio files use integer sample formats with varying bit depths. The bit depth determines dynamic range — how many distinct amplitude levels can be represented:

| Bit depth | Integer range | Dynamic range |
|-----------|--------------|---------------|
| 8-bit | -128 to 127 | ~48 dB |
| 16-bit (CD quality) | -32,768 to 32,767 | ~96 dB |
| 24-bit (studio) | -8,388,608 to 8,388,607 | ~144 dB |
| 32-bit float | continuous in [-1.0, 1.0] | ~1528 dB (theoretical) |

PyTorch and NumPy arithmetic both operate in floating-point. If you feed integer samples directly into a neural network, the magnitudes are meaningless to the model — a value of 20,000 means "near maximum" in 16-bit audio but "nearly silent" in 24-bit audio.

Normalising to `float32` in `[-1.0, 1.0]` makes amplitude physically meaningful: `0.0` is silence, `1.0` is the maximum undistorted signal level, `-1.0` is maximum negative excursion. Every model in the pipeline — Demucs and Basic Pitch — expects this representation.

### librosa does most of this automatically

When `dtype=np.float32` is specified (or when `sr` triggers resampling, which forces float internally), librosa divides integer samples by their maximum representable value:

```
float_sample = int_sample / max_int_value
# e.g. 16-bit: float_sample = int_sample / 32768.0
```

### The clipping guard

Floating-point arithmetic during resampling can push samples marginally outside `[-1.0, 1.0]` — for example, a sample at exactly `32767` in 16-bit may become `1.0000001` after interpolation. This is not distortion in any audible sense, but it can cause NaN propagation or unexpected behaviour in downstream models that assume normalised input. An explicit clip is cheap and defensive:

```python
audio = np.clip(audio, -1.0, 1.0)
```

Additionally, if a file was recorded with clipping (a hard, flat-topped waveform), the samples will legitimately sit at exactly `±1.0` for long stretches. Ingest cannot repair this — it should detect it and log a warning so engineers can diagnose downstream quality issues:

```python
clipping_ratio = np.mean(np.abs(audio) >= 0.999)
if clipping_ratio > 0.01:  # more than 1% of samples clipped
    logger.warning(f"Input audio appears clipped ({clipping_ratio:.1%} of samples at ±1.0)")
```

---

## 7. Stage 4 — Ensure stereo

### Why Demucs requires stereo

Demucs's `htdemucs` model was trained on stereo recordings. Its architecture includes convolutional layers that jointly process left and right channels, and the learned weights encode stereo relationships — for example, that a centred bass guitar produces nearly identical signals in both channels, while a panned guitar may appear strongly in one channel. If only one channel is provided, the tensor shape does not match the model's expected input and the forward pass raises a runtime error.

### The upmix strategy

For mono inputs, the correct approach is to duplicate the single channel into both the left and right positions:

```python
if audio.ndim == 1:
    audio = np.stack([audio, audio])  # shape: (N,) → (2, N)
```

This is called a mono-to-stereo upmix. The resulting stereo signal has a correlation of exactly 1.0 between channels — it encodes no spatial information, but it satisfies the model's input contract. Source separation quality on mono-sourced material will be somewhat lower than on genuine stereo recordings because the model cannot use inter-channel differences as separation cues. This should be documented to users.

### Channel ordering

librosa uses **channel-first** ordering: the array shape is `(channels, samples)` — i.e. `(2, N)`. This matches PyTorch's expected tensor layout when the batch dimension is added (`(1, 2, N)`). The ordering must be verified explicitly because some audio libraries return `(samples, channels)` (channel-last), which would silently produce the wrong result when passed to Demucs.

```python
# Guard against channel-last layout from unexpected sources
if audio.ndim == 2 and audio.shape[0] > audio.shape[1]:
    # More likely (samples, channels) than (channels, samples)
    audio = audio.T
```

### Multi-channel inputs (>2 channels)

Some files arrive with more than two channels (5.1 surround, ambisonics, multi-mic recordings). The current pipeline does not support multi-channel source separation. For inputs with more than two channels, the ingest stage should mix down to stereo by taking only the first two channels:

```python
if audio.shape[0] > 2:
    logger.warning(f"Input has {audio.shape[0]} channels; using first two only")
    audio = audio[:2, :]
```

A future iteration could perform a proper downmix (e.g. ITU-R BS.775 standard for 5.1 → stereo), but the current approach is sufficient for music files, which are overwhelmingly stereo.

---

## 8. Error handling and validation

### Error taxonomy

All exceptions raised by the ingest stage should be caught and re-raised as a single domain exception `IngestError` with a human-readable message. The pipeline runner wraps this in a job failure response that the API surfaces to the client.

| Condition | Root exception | `IngestError` message |
|-----------|---------------|----------------------|
| File not found | `FileNotFoundError` | `"Audio file not found: {path}"` |
| Unreadable / corrupt file | `librosa.exceptions.LibrosaError`, `soundfile.SoundFileError` | `"Could not decode audio file: {path}. File may be corrupt or in an unsupported format."` |
| No audio backend for format | `audioread.exceptions.NoBackendError` | `"No decoder available for {ext} files. Ensure FFmpeg is installed."` |
| Unexpected shape after load | `AssertionError` | `"Unexpected audio shape {shape} after normalisation."` |
| File too short | Custom check | `"Audio too short ({duration:.2f}s). Minimum is {MIN_DURATION}s."` |

### Post-load validation

After normalisation, validate the output before returning:

```python
MIN_DURATION_SECONDS = 1.0

def _validate(audio: np.ndarray, sr: int = 44100) -> None:
    assert audio.ndim == 2,           f"Expected 2D array, got {audio.ndim}D"
    assert audio.shape[0] == 2,       f"Expected stereo (2, N), got shape {audio.shape}"
    assert audio.dtype == np.float32, f"Expected float32, got {audio.dtype}"
    assert np.all(np.isfinite(audio)), "Audio contains NaN or Inf values"

    duration = audio.shape[1] / sr
    assert duration >= MIN_DURATION_SECONDS, (
        f"Audio too short ({duration:.2f}s); minimum is {MIN_DURATION_SECONDS}s"
    )
```

---

## 9. Full implementation

```python
import logging
import numpy as np
import librosa

logger = logging.getLogger(__name__)

MIN_DURATION_SECONDS = 1.0
TARGET_SAMPLE_RATE   = 44_100


class IngestError(Exception):
    """Raised when the ingest stage cannot produce a valid audio array."""


def ingest(path: str) -> np.ndarray:
    """
    Load and normalise an audio file for downstream pipeline stages.

    Accepts any format supported by librosa (MP3, WAV, FLAC, AAC, OGG, AIFF, MP4).
    Returns a float32 stereo array of shape (2, N) at 44,100 Hz with values in [-1.0, 1.0].

    Args:
        path: Absolute path to a local audio file. The caller (input adapter)
              is responsible for ensuring the file exists and is readable.

    Returns:
        np.ndarray of shape (2, N), dtype=float32.

    Raises:
        IngestError: For any failure during loading, decoding, or normalisation.
    """
    logger.info(f"Ingesting: {path}")

    # --- Decode and resample ---
    try:
        audio, sr = librosa.load(
            path,
            sr=TARGET_SAMPLE_RATE,
            mono=False,
            dtype=np.float32,
            res_type='kaiser_best',
        )
    except FileNotFoundError:
        raise IngestError(f"Audio file not found: {path}")
    except Exception as exc:
        # librosa surfaces codec failures as various exception types
        # depending on the backend. Catch broadly and re-raise.
        raise IngestError(
            f"Could not decode audio file: {path}. "
            f"File may be corrupt, DRM-protected, or in an unsupported format. "
            f"Detail: {exc}"
        ) from exc

    # --- Channel normalisation ---
    if audio.ndim == 1:
        # Mono input: duplicate channel to satisfy stereo contract
        logger.debug("Mono input detected — upmixing to stereo")
        audio = np.stack([audio, audio])

    elif audio.ndim == 2 and audio.shape[0] > audio.shape[1]:
        # Likely channel-last layout (samples, channels) — transpose
        logger.debug("Channel-last layout detected — transposing")
        audio = audio.T

    if audio.shape[0] > 2:
        # Multi-channel: take first two channels only
        logger.warning(
            f"Input has {audio.shape[0]} channels; using first two. "
            "Spatial information beyond stereo will be discarded."
        )
        audio = audio[:2, :]

    # --- Float32 clip ---
    audio = np.clip(audio, -1.0, 1.0)

    # --- Clipping diagnostic ---
    clipping_ratio = float(np.mean(np.abs(audio) >= 0.999))
    if clipping_ratio > 0.01:
        logger.warning(
            f"Input audio appears clipped "
            f"({clipping_ratio:.1%} of samples at ±1.0). "
            "Source separation and transcription quality may be reduced."
        )

    # --- Post-load validation ---
    try:
        _validate(audio)
    except AssertionError as exc:
        raise IngestError(f"Audio failed post-load validation: {exc}") from exc

    duration = audio.shape[1] / TARGET_SAMPLE_RATE
    logger.info(
        f"Ingest complete: {duration:.2f}s, "
        f"shape={audio.shape}, dtype={audio.dtype}"
    )

    return audio


def _validate(audio: np.ndarray) -> None:
    assert audio.ndim == 2, \
        f"Expected 2D array (channels, samples), got {audio.ndim}D"
    assert audio.shape[0] == 2, \
        f"Expected stereo shape (2, N), got {audio.shape}"
    assert audio.dtype == np.float32, \
        f"Expected float32, got {audio.dtype}"
    assert np.all(np.isfinite(audio)), \
        "Audio contains NaN or Inf values — possible corrupt input"
    duration = audio.shape[1] / TARGET_SAMPLE_RATE
    assert duration >= MIN_DURATION_SECONDS, (
        f"Audio duration {duration:.2f}s is below minimum {MIN_DURATION_SECONDS}s"
    )
```

---

## 10. Testing requirements

Each normalisation step should have an isolated unit test. The following table describes the minimum test cases:

| Test | Input | Expected output |
|------|-------|-----------------|
| Stereo WAV, 44,100 Hz | Standard stereo WAV | Shape `(2, N)`, dtype `float32`, values in `[-1, 1]` |
| Stereo MP3, 44,100 Hz | Standard stereo MP3 | Same contract as above |
| Mono WAV | Single-channel WAV | Shape `(2, N)` — channels are identical |
| 48,000 Hz file | WAV at 48 kHz | Shape `(2, N)` at 44,100 Hz — `N = duration × 44100` |
| 96,000 Hz file | WAV at 96 kHz | Correct downsampled length |
| Pre-clipped file | WAV with samples at ±32767 | Clipping warning logged; values still in `[-1, 1]` |
| File not found | Non-existent path | `IngestError` raised with descriptive message |
| Corrupt file | Truncated MP3 | `IngestError` raised |
| Too short | 0.5s file | `IngestError` raised |
| Multi-channel | 6-channel WAV | Warning logged; output shape `(2, N)` |
| No FFmpeg | MP3 with no backend | `IngestError` with FFmpeg install instruction |

Test fixtures should be generated programmatically using `soundfile` or `scipy.io.wavfile` rather than checked in as binary files, to keep the repository small.

---

## 11. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q1 | Should ingest also extract and return file-level metadata (BPM, key, duration, loudness) for storage alongside job results? | Product | Sprint 2 |
| Q2 | What is the correct stereo downmix algorithm for 5.1 and 7.1 surround inputs? ITU-R BS.775 or simpler L+R extraction? | ML | ADR-005 |
| Q3 | Is `kaiser_best` resampling quality acceptable, or do we need `soxr_vhq` (SoX very high quality) for studio-grade inputs? | ML | Evaluation sprint |
| Q4 | Should the clipping threshold (currently 1%) and minimum duration (currently 1s) be configurable per deployment or fixed? | Infrastructure | Sprint 2 |
| Q5 | How should ingest handle files where one channel is silent (e.g. a broken stereo recording)? Treat as mono or pass through? | Product | Sprint 2 |

---

*Document owner: Architecture team — update when implementation deviates from this spec.*
