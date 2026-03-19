# ADR-001 — Technology stack for the music analysis pipeline

| Field       | Value                        |
|-------------|------------------------------|
| Status      | Accepted                     |
| Date        | 2026-03-19                   |
| Deciders    | Architecture team            |
| Category    | Technology selection         |

---

## 1. Context and problem statement

We are building a pipeline that accepts audio input from multiple sources (files, URLs, live streams, devices), separates it into per-instrument stems, transcribes those stems into MIDI note data, and renders human-readable scores. The system must be embeddable in web and mobile clients via an API-first interface.

The core challenge is that music analysis sits at the intersection of signal processing, machine learning, and music theory — three domains with distinct tooling ecosystems. We need a stack that handles all three without requiring us to build foundational capabilities ourselves.

---

## 2. Decision drivers

- **Model availability** — state-of-the-art source separation and transcription models are published as Python packages; we need to be where the research is.
- **Separation of concerns** — each pipeline stage (ingest, separate, transcribe, render) must be independently replaceable as better models emerge.
- **Polyphony support** — the transcription layer must handle multiple simultaneous notes per stem, ruling out classical monophonic pitch detectors.
- **Operational simplicity** — models should be callable from application code without custom training or infrastructure.
- **Output fidelity** — the stack must produce standard interchange formats (FLAC, MIDI, MusicXML) that downstream tools and clients can consume without custom parsers.

---

## 3. Considered options

### 3.1 Implementation language

| Option | Rationale for rejection |
|--------|------------------------|
| **Python** ✓ | Selected — see decision below |
| Node.js | No mature equivalents to Demucs or Basic Pitch; audio ML research does not target this runtime |
| Rust | Excellent performance, but no production-grade neural source separation or transcription libraries exist |
| C++ | Maximum performance ceiling, but development velocity is prohibitive for a pipeline with multiple ML model integrations |

### 3.2 Source separation model

| Option | Rationale for rejection |
|--------|------------------------|
| **Demucs (`htdemucs`)** ✓ | Selected — see decision below |
| Spleeter (Deezer) | Older architecture; lower quality on complex mixes; development has slowed |
| NMF (non-negative matrix factorisation) | Classical approach; no learned priors; poor performance on polyphonic material |
| Open-Unmix | Solid baseline but outperformed by `htdemucs` on standard benchmarks (MUSDB18) |

### 3.3 Transcription model

| Option | Rationale for rejection |
|--------|------------------------|
| **Basic Pitch (Spotify)** ✓ | Selected — see decision below |
| pYIN | Monophonic only; fails on chords and simultaneous notes |
| CREPE | High accuracy for monophonic pitch tracking; does not handle polyphony |
| MT3 (Google Magenta) | Strong multi-instrument transcription from raw mix; complex inference setup; overkill for per-stem transcription |

### 3.4 MIDI representation

| Option | Rationale for rejection |
|--------|------------------------|
| **pretty_midi** ✓ | Selected — see decision below |
| mido | Lower-level; requires manual parsing of MIDI messages; more boilerplate for note-level access |
| music21 (for MIDI too) | Capable but heavy; appropriate only at the score layer |

### 3.5 Score generation

| Option | Rationale for rejection |
|--------|------------------------|
| **music21** ✓ | Selected — see decision below |
| Direct MusicXML generation | Requires hand-authoring a complex XML schema; error-prone |
| LilyPond (direct) | Powerful engraving engine but requires learning a dedicated notation language; no Python-native API |
| MuseScore CLI | Excellent renderer but acts as a consumer of MusicXML, not a generator; used downstream of music21 |

---

## 4. Decision

### 4.1 Python as implementation language

Python is selected as the pipeline implementation language. The ML research community publishes source separation and transcription models as Python packages; there is no equivalent ecosystem in any other language for this problem domain. Python's role in the pipeline is orchestration, not computation — all numerically intensive work executes inside compiled extensions (PyTorch kernels, librosa's C extensions). The performance cost of Python's interpreter is therefore negligible.

### 4.2 librosa for ingest and normalisation

librosa is selected for audio I/O. It decodes any common codec (MP3, FLAC, WAV, AAC), resamples to a target rate, and returns a NumPy array — the universal representation shared by all downstream stages. Its `load()` function acts as the ingest contract: whatever the input adapter hands us, librosa converts it to a `float32` array at 44,100 Hz. This decouples the adapter layer entirely from the processing pipeline.

### 4.3 Demucs (`htdemucs`) for source separation

Demucs is selected as the source separation model. The `htdemucs` variant uses a hybrid architecture operating simultaneously in the waveform and spectrogram domains, which produces demonstrably cleaner stem separation than earlier waveform-only or spectrogram-only approaches. It is distributed as a Python package with pre-trained weights, requiring no custom training. It produces four stems (drums, bass, vocals, other) as stereo NumPy arrays, which map cleanly to the pipeline's output contract.

The primary operational concern is inference time on CPU — a four-minute track requires approximately 10 minutes on a modern CPU. GPU acceleration reduces this to under 30 seconds. The pipeline runner must therefore be designed to accept a device parameter and the deployment environment must provision GPU instances for production workloads.

### 4.4 Basic Pitch for polyphonic transcription

Basic Pitch is selected for per-stem note transcription. It accepts an audio array and returns a `pretty_midi` object containing detected notes with onset times, offsets, pitches, and velocities. Its key differentiator over classical methods is polyphony handling — it can detect simultaneous notes within a stem, which is essential for piano, guitar, and other chordal instruments.

Basic Pitch is run per-stem rather than on the full mix. This is a deliberate architectural choice: source separation first, then transcription on each isolated stem. This produces higher transcription accuracy than transcribing the full mix, because each stem contains a narrower range of timbres for the model to disambiguate.

Note: Basic Pitch performs poorly on drums, which have no stable pitch. Drum stems should be routed to a rhythm/onset detection path rather than through Basic Pitch. This is flagged as a follow-up decision (ADR-002).

### 4.5 pretty_midi as the MIDI representation layer

pretty_midi is selected as the in-memory MIDI representation. It provides a clean object model — a `PrettyMIDI` instance contains a list of `Instrument` objects, each holding a list of `Note` objects with pitch, start, end, and velocity attributes. It reads and writes standard `.mid` files. It is the native output format of Basic Pitch and the natural input format for music21.

### 4.6 music21 for score generation

music21 is selected for MusicXML score generation. Unlike the rest of the stack, music21 understands music theory: it can infer key signatures, quantise notes to a rhythmic grid, organise note events into measures, and apply beaming. These operations are necessary to convert a flat list of MIDI note events into notation that is readable by a musician. music21 outputs MusicXML, which is the standard interchange format for notation software. LilyPond or MuseScore CLI can be used downstream to render MusicXML to PDF.

---

## 5. Data flow

```
Input adapter (file / URL / stream / device)
  └─► librosa.load()          → float32 stereo array @ 44,100 Hz
        └─► Demucs htdemucs   → {drums, bass, vocals, other} arrays
              └─► Basic Pitch → pretty_midi objects per stem
                    └─► music21 → MusicXML
                          └─► LilyPond / MuseScore → PDF score
```

Each stage produces a standard representation. No stage is aware of its neighbours' implementation details.

---

## 6. Consequences

### Positive

- The pipeline is entirely composed of pre-trained models. No labelled training data, training infrastructure, or ML expertise is required to operate it.
- Each stage is independently replaceable. If a better source separation model is published, only the separation stage changes; the ingest and transcription stages are unaffected.
- All output formats (FLAC, MIDI, MusicXML) are open standards with broad third-party tool support.
- The NumPy array as the internal audio representation is a zero-cost interface — no serialisation or copying required between stages running in the same process.

### Negative / risks

- **GPU dependency in production** — Demucs inference on CPU is too slow for synchronous API responses. Production deployments require GPU instances, which increases infrastructure cost and operational complexity.
- **Drum transcription gap** — Basic Pitch is not appropriate for unpitched percussion. A separate onset detection and drum pattern classification path is needed and is not covered by this decision.
- **Score quality is bounded by MIDI quality** — music21 can only render what Basic Pitch detects. Transcription errors (missed notes, incorrect pitches, quantisation artefacts) propagate to the score. Managing user expectations around score fidelity is a product concern.
- **Python packaging complexity** — Demucs and Basic Pitch have deep PyTorch dependency trees. Reproducible environment management (pinned lockfiles, container images) is required from the start.

---

## 7. Open questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| Q1 | What is the GPU provisioning strategy for production? On-demand vs reserved vs spot? | Infrastructure | ADR-002 |
| Q2 | How do we handle drum stems — onset detection only, or a separate drum transcription model? | ML | ADR-003 |
| Q3 | What is the acceptable latency SLA for the `/jobs` API endpoint? This determines whether GPU is required at all tiers. | Product | Sprint planning |
| Q4 | Should music21 score output be quantised to a fixed grid or attempt to preserve expressive timing? | Product | ADR-004 |

---

## 8. References

- [Demucs — Music Source Separation](https://github.com/facebookresearch/demucs) — Meta Research
- [Basic Pitch](https://github.com/spotify/basic-pitch) — Spotify Research
- [librosa documentation](https://librosa.org/doc/latest/)
- [pretty_midi documentation](https://craffel.github.io/pretty-midi/)
- [music21 documentation](https://web.mit.edu/music21/)
- [MUSDB18 benchmark](https://sigsep.github.io/datasets/musdb.html) — standard evaluation dataset for source separation
- [arc42 architecture documentation template](https://arc42.org)
