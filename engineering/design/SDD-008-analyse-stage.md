# SDD-008 — Analyse stage design

| Field      | Value                                                        |
|------------|--------------------------------------------------------------|
| Status     | Draft                                                        |
| Date       | 2026-03-19                                                   |
| Relates to | ADR-001 (stack), SDD-003 (separate), ADR-003 (drums)        |
| Covers     | Pipeline stage 3.5: per-stem curve extraction for visualisation |

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [Context: where analyse sits in the pipeline](#2-context)
3. [Output contract: StemCurves](#3-output-contract-stemcurves)
4. [Curve definitions](#4-curve-definitions)
5. [Envelope shaping: attack, release, smoothing](#5-envelope-shaping)
6. [Frame rate strategy](#6-frame-rate-strategy)
7. [CurvesSource adapter](#7-curvessource-adapter)
8. [Full implementation](#8-full-implementation)
9. [Testing requirements](#9-testing-requirements)
10. [Open questions](#10-open-questions)

---

## 1. Purpose and scope

The analyse stage sits between source separation and visualisation. It
converts raw per-stem waveforms into time-series curves that the visual
layer can drive animations from directly — no signal processing required
in the renderer.

Each stem produces a `StemCurves` object containing six normalised curves,
all sharing the same time axis. The curves are:

- **amplitude** — loudness envelope
- **centroid** — spectral centre of mass (low = bass-heavy, high = bright)
- **flatness** — tonal vs noise-like character
- **bass** — energy in the low frequency band (20–250 Hz)
- **mid** — energy in the mid frequency band (250–4000 Hz)
- **high** — energy in the high frequency band (4000–20000 Hz)

All curves are normalised to `[0.0, 1.0]` and shaped `(T,)` where T is
determined by the frame rate.

**What this stage is not responsible for:**
- Deciding which curves drive which visual elements — that is the visual
  layer's concern
- Rendering or animation
- Real-time streaming (v1 is batch; streaming analysis is post-v1)

---

## 2. Context

```
Separate stage
  │  dict[str, np.ndarray]  (6 stems, shape=(2,N), float32, sr=44100)
  ▼
┌─────────────────────────────────────────────────────────────┐
│  ANALYSE STAGE                                              │
│  Per stem:                                                  │
│    1. Frame the waveform at high resolution (100fps equiv.) │
│    2. Extract 6 curves per frame                            │
│    3. Apply attack/release envelope shaping                 │
│    4. Apply smoothing                                       │
│    5. Normalise to [0, 1]                                   │
└─────────────────────────────────────────────────────────────┘
  │  dict[str, StemCurves]
  ▼
CurvesSource (adapter)
  ├── DiskCurvesSource   → reads/writes .npy files in stems/
  └── MemoryCurvesSource → holds arrays in-process
  │
  ▼
Visual layer
```

---

## 3. Output contract: StemCurves

```python
@dataclasses.dataclass(frozen=True)
class StemCurves:
    # Six normalised time-series curves, all shape (T,), dtype float32
    amplitude:  np.ndarray   # loudness envelope          ∈ [0, 1]
    centroid:   np.ndarray   # spectral centroid          ∈ [0, 1]
    flatness:   np.ndarray   # spectral flatness          ∈ [0, 1]
    bass:       np.ndarray   # low band energy            ∈ [0, 1]
    mid:        np.ndarray   # mid band energy            ∈ [0, 1]
    high:       np.ndarray   # high band energy           ∈ [0, 1]

    # Metadata
    frame_rate:  float       # frames per second (e.g. 100.0)
    n_frames:    int         # T — number of frames
    duration_s:  float       # audio duration in seconds
    attack_ms:   float       # attack time used
    release_ms:  float       # release time used
    smooth_ms:   float       # smoothing window used
    stem_name:   str         # which stem this came from
```

All six arrays are guaranteed to have the same shape `(T,)`, be `float32`,
and have values in `[0.0, 1.0]`. Downstream consumers must not re-normalise.

---

## 4. Curve definitions

### 4.1 Amplitude envelope

RMS energy computed per frame, then shaped by the attack/release envelope
(see §5), then normalised.

```python
hop_length = sr // frame_rate          # samples per frame
rms = librosa.feature.rms(
    y=mono_stem,
    frame_length=hop_length * 2,
    hop_length=hop_length,
)[0]                                   # shape (T,)
```

Uses the mono mix of the stem (left + right averaged). Stereo RMS would
be more accurate but unnecessary for visualisation.

### 4.2 Spectral centroid

The frequency-weighted mean of the spectrum per frame. Low values indicate
bass-heavy content (drums, bass guitar); high values indicate bright content
(hi-hats, vocals, guitar harmonics).

```python
centroid = librosa.feature.spectral_centroid(
    y=mono_stem, sr=sr, hop_length=hop_length
)[0]                                   # shape (T,), units: Hz
```

Normalise by dividing by Nyquist (sr/2) before returning.

### 4.3 Spectral flatness

Ratio of geometric mean to arithmetic mean of the spectrum. Values near 0
indicate tonal content (a clear pitch); values near 1 indicate noise-like
content (white noise, snare, cymbals). Useful for distinguishing drum hits
from sustained tones.

```python
flatness = librosa.feature.spectral_flatness(
    y=mono_stem, hop_length=hop_length
)[0]                                   # shape (T,), already ∈ [0, 1]
```

### 4.4 Band energies (bass, mid, high)

RMS energy within three frequency bands, computed via STFT:

| Band | Range     | Visual use |
|------|-----------|------------|
| bass | 20–250 Hz | Kick, bass guitar, low synths |
| mid  | 250–4000 Hz | Vocals, guitar body, snare |
| high | 4000–20000 Hz | Hi-hats, cymbals, vocal air, string harmonics |

```python
stft = np.abs(librosa.stft(mono_stem, hop_length=hop_length))
freqs = librosa.fft_frequencies(sr=sr)

def band_rms(low_hz, high_hz):
    mask = (freqs >= low_hz) & (freqs < high_hz)
    return np.sqrt(np.mean(stft[mask] ** 2, axis=0))  # shape (T,)

bass = band_rms(20, 250)
mid  = band_rms(250, 4000)
high = band_rms(4000, 20000)
```

Each band is normalised independently (divide by its own max across the
full clip) so relative levels within a band are preserved.

---

## 5. Envelope shaping: attack, release, smoothing

Raw RMS and band energy curves are noisy — single transients cause spikes
that look jittery in animation. Envelope shaping converts these into smooth,
reactive curves that feel musical.

### Attack and release

Implemented as a per-sample first-order filter that rises fast (attack) and
falls slow (release):

```python
def apply_envelope(curve: np.ndarray, attack_coef: float, release_coef: float) -> np.ndarray:
    out = np.zeros_like(curve)
    for i in range(len(curve)):
        if curve[i] > out[i - 1]:
            out[i] = attack_coef  * curve[i] + (1 - attack_coef)  * out[i - 1]
        else:
            out[i] = release_coef * curve[i] + (1 - release_coef) * out[i - 1]
    return out
```

Coefficients are derived from time constants:

```python
def time_to_coef(ms: float, frame_rate: float) -> float:
    frames = ms / 1000 * frame_rate
    return 1.0 - np.exp(-1.0 / frames) if frames > 0 else 1.0
```

Typical defaults:
- `attack_ms = 10`   — fast rise, feels responsive
- `release_ms = 150` — slow fall, feels musical rather than choppy

### Smoothing

Additional Gaussian smoothing applied after envelope shaping. Controlled
by `smooth_ms` — the window width in milliseconds. Implemented via
`scipy.ndimage.gaussian_filter1d`.

```python
from scipy.ndimage import gaussian_filter1d
sigma = smooth_ms / 1000 * frame_rate / 3  # convert ms to frame sigma
smoothed = gaussian_filter1d(curve, sigma=sigma)
```

Setting `smooth_ms=0` disables smoothing entirely. Default: `smooth_ms=20`.

### Designer experimentation

All three parameters (`attack_ms`, `release_ms`, `smooth_ms`) are exposed
as arguments to `analyse()` and stored in `StemCurves.metadata`. The visual
layer can load the same `.npy` data and re-apply different envelope parameters
in memory without re-running analysis.

---

## 6. Frame rate strategy

Analysis is captured at a high base rate (`default: 100fps`) regardless of
the target render rate. This means:

- A 30fps renderer uses every 3rd frame
- A 60fps renderer uses every ~2nd frame
- A 120fps renderer uses every frame (slight interpolation needed)

The consumer decimates to its target rate — the data is captured once at
high resolution and never needs to be recomputed for a different frame rate.

`hop_length = sr // frame_rate_capture` gives the samples-per-frame.
At `frame_rate=100` and `sr=44100`: `hop_length = 441`.

---

## 7. CurvesSource adapter

Same pattern as `InputAdapter`. Buffers the visual layer from the storage
decision.

```
src/pipeline/analyse/
    __init__.py
    curves.py        — StemCurves dataclass, AnalyseError
    analyse.py       — analyse() function
    source.py        — CurvesSource ABC
    disk.py          — DiskCurvesSource (reads/writes .npy)
    memory.py        — MemoryCurvesSource (in-process)
```

### CurvesSource ABC

```python
class CurvesSource(abc.ABC):
    @abc.abstractmethod
    def load(self, stem_name: str) -> StemCurves: ...

    @abc.abstractmethod
    def save(self, stem_name: str, curves: StemCurves) -> None: ...

    @abc.abstractmethod
    def exists(self, stem_name: str) -> bool: ...

    @abc.abstractmethod
    def available_stems(self) -> list[str]: ...
```

### DiskCurvesSource

Reads and writes a directory of `.npy` files. Each stem produces one file
per curve plus a metadata JSON:

```
test_audio/<slug>/curves/
    drums_amplitude.npy
    drums_centroid.npy
    drums_flatness.npy
    drums_bass.npy
    drums_mid.npy
    drums_high.npy
    drums_meta.json      ← frame_rate, attack_ms, release_ms, smooth_ms, etc.
    bass_amplitude.npy
    ...
```

### MemoryCurvesSource

Holds a `dict[str, StemCurves]` in memory. Used when running the full
pipeline end-to-end without touching disk (e.g. streaming mode, tests).

---

## 8. Full implementation

### `src/pipeline/analyse/curves.py`

```python
import dataclasses
import numpy as np

@dataclasses.dataclass(frozen=True)
class StemCurves:
    amplitude:  np.ndarray
    centroid:   np.ndarray
    flatness:   np.ndarray
    bass:       np.ndarray
    mid:        np.ndarray
    high:       np.ndarray
    frame_rate:  float
    n_frames:    int
    duration_s:  float
    attack_ms:   float
    release_ms:  float
    smooth_ms:   float
    stem_name:   str

    def at_fps(self, fps: float) -> "StemCurves":
        """Return a decimated copy at a lower frame rate for a specific renderer."""
        step = max(1, round(self.frame_rate / fps))
        return dataclasses.replace(
            self,
            amplitude = self.amplitude[::step],
            centroid  = self.centroid[::step],
            flatness  = self.flatness[::step],
            bass      = self.bass[::step],
            mid       = self.mid[::step],
            high      = self.high[::step],
            frame_rate = self.frame_rate / step,
            n_frames   = len(self.amplitude[::step]),
        )


class AnalyseError(Exception):
    """Domain exception for the analyse stage."""
```

### `src/pipeline/analyse/analyse.py`

```python
import logging
import numpy as np
import librosa
from scipy.ndimage import gaussian_filter1d
from src.pipeline.analyse.curves import AnalyseError, StemCurves

logger = logging.getLogger(__name__)

SR           = 44_100
FRAME_RATE   = 100.0    # capture rate — consumers decimate to their target fps
ATTACK_MS    = 10.0
RELEASE_MS   = 150.0
SMOOTH_MS    = 20.0

BASS_HZ  = (20,   250)
MID_HZ   = (250,  4000)
HIGH_HZ  = (4000, 20000)


def analyse(
    stems: dict[str, np.ndarray],
    sr: int = SR,
    frame_rate: float = FRAME_RATE,
    attack_ms: float = ATTACK_MS,
    release_ms: float = RELEASE_MS,
    smooth_ms: float = SMOOTH_MS,
) -> dict[str, StemCurves]:
    """
    Extract per-stem visualisation curves from separated waveforms.

    Parameters
    ----------
    stems      : output of the separate stage
    sr         : sample rate (must be 44100)
    frame_rate : capture rate in fps (default 100 — decimate in renderer)
    attack_ms  : envelope attack time in milliseconds
    release_ms : envelope release time in milliseconds
    smooth_ms  : gaussian smoothing window in milliseconds (0 = off)

    Returns
    -------
    dict[str, StemCurves]  — one StemCurves per stem
    """
    result = {}
    for stem_name, stem in stems.items():
        logger.debug("analysing stem: %s", stem_name)
        try:
            result[stem_name] = _analyse_stem(
                stem, stem_name, sr, frame_rate,
                attack_ms, release_ms, smooth_ms,
            )
        except Exception as exc:
            raise AnalyseError(
                f"analysis failed for stem '{stem_name}': {exc}"
            ) from exc
    return result


def _analyse_stem(
    stem: np.ndarray,
    stem_name: str,
    sr: int,
    frame_rate: float,
    attack_ms: float,
    release_ms: float,
    smooth_ms: float,
) -> StemCurves:
    hop = int(sr / frame_rate)
    mono = stem.mean(axis=0)                          # (N,) — mono mix
    duration_s = len(mono) / sr

    # Raw feature extraction
    amplitude = _rms(mono, hop)
    centroid  = _centroid(mono, sr, hop)
    flatness  = _flatness(mono, hop)
    bass, mid, high = _bands(mono, sr, hop)

    # Envelope shaping
    atk = _time_to_coef(attack_ms, frame_rate)
    rel = _time_to_coef(release_ms, frame_rate)
    sig = smooth_ms / 1000 * frame_rate / 3          # gaussian sigma in frames

    def shape(curve):
        c = _apply_envelope(curve, atk, rel)
        if sig > 0:
            c = gaussian_filter1d(c, sigma=sig)
        return _normalise(c).astype(np.float32)

    return StemCurves(
        amplitude  = shape(amplitude),
        centroid   = shape(centroid),
        flatness   = shape(flatness),
        bass       = shape(bass),
        mid        = shape(mid),
        high       = shape(high),
        frame_rate  = frame_rate,
        n_frames    = len(shape(amplitude)),
        duration_s  = duration_s,
        attack_ms   = attack_ms,
        release_ms  = release_ms,
        smooth_ms   = smooth_ms,
        stem_name   = stem_name,
    )


# ── Signal processing helpers ─────────────────────────────────────────────────

def _rms(mono, hop):
    return librosa.feature.rms(
        y=mono, frame_length=hop * 2, hop_length=hop
    )[0]


def _centroid(mono, sr, hop):
    return librosa.feature.spectral_centroid(
        y=mono, sr=sr, hop_length=hop
    )[0] / (sr / 2)                                  # normalise by Nyquist


def _flatness(mono, hop):
    return librosa.feature.spectral_flatness(
        y=mono, hop_length=hop
    )[0]


def _bands(mono, sr, hop):
    stft  = np.abs(librosa.stft(mono, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr)

    def band(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return np.sqrt(np.mean(stft[mask] ** 2, axis=0) + 1e-8)

    return band(*BASS_HZ), band(*MID_HZ), band(*HIGH_HZ)


def _time_to_coef(ms, frame_rate):
    frames = ms / 1000 * frame_rate
    return float(1.0 - np.exp(-1.0 / frames)) if frames > 0 else 1.0


def _apply_envelope(curve, atk, rel):
    out = np.zeros_like(curve)
    for i in range(1, len(curve)):
        coef = atk if curve[i] > out[i - 1] else rel
        out[i] = coef * curve[i] + (1 - coef) * out[i - 1]
    return out


def _normalise(curve):
    lo, hi = curve.min(), curve.max()
    return (curve - lo) / (hi - lo + 1e-8)
```

---

## 9. Testing requirements

| TC | Input | Expected |
|----|-------|----------|
| TC-ANA-001 | 6-stem dict, default params | Returns dict with all 6 keys |
| TC-ANA-002 | Any stem | All 6 curves same shape (T,) |
| TC-ANA-003 | Any stem | All values in [0.0, 1.0] |
| TC-ANA-004 | Any stem | dtype float32 |
| TC-ANA-005 | Silent stem (zeros) | No crash, curves are all zeros or near-zero |
| TC-ANA-006 | attack_ms=0 | No crash, envelope still applied |
| TC-ANA-007 | smooth_ms=0 | Smoothing skipped, curves still valid |
| TC-ANA-008 | StemCurves.at_fps(30) | Returns curves at ~30fps |
| TC-ANA-009 | DiskCurvesSource save/load | Round-trip preserves values within float32 precision |
| TC-ANA-010 | MemoryCurvesSource | save/load/exists work correctly |
| TC-ANA-011 | DiskCurvesSource.available_stems() | Returns only stems that have been saved |
| TC-ANA-012 | Bad stem shape | AnalyseError raised |

---

## 10. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q-ANA-1 | Are 100fps capture and the three default band boundaries right for the designer's needs? Adjust after visual prototype. | Design | Post-prototype |
| Q-ANA-2 | Should `at_fps()` interpolate rather than decimate for upsampling? | Engineering | When needed |
| Q-ANA-3 | Should the analyse stage run per-stem in parallel (ThreadPoolExecutor)? 6 stems × 30s ≈ fast enough serial, but worth profiling. | Engineering | Optimisation sprint |
| Q-ANA-4 | Streaming analysis — rolling window approach for real-time feeds. Blocked on Q-STREAM-1. | Engineering | Post-v1 |

---

*Document owner: Architecture team — update when implementation deviates from this spec.*
