# Engineering

This directory contains all technical documentation for the Auris Vive pipeline — architecture decisions, stage designs, and the API spec.

If you are a designer or artist looking for the brand kit, you want [`../brand/`](../brand/).

---

## Document map

### Decisions (ADRs)

Architecture Decision Records capture *why* we chose what we chose. Read these before touching the pipeline.

| Document | Decision | Status |
|----------|----------|--------|
| [ADR-001](./decisions/ADR-001-stack.md) | Technology stack — Python, Demucs, Basic Pitch, music21 | ✅ Written |
| [ADR-002](./decisions/ADR-002-inference-backend.md) | Inference backend — Modal, JobQueue abstraction, singleton model loading | ✅ Written |
| [ADR-003](./decisions/ADR-003-drum-transcription.md) | Drum stem transcription — onset-only v1, DrumTranscriber ABC, ADTLib v2 | ✅ Written |
| ADR-004 | Score quantisation — strict vs expressive | 🔲 Pending |
| ADR-005 | Multi-channel downmix algorithm | 🔲 Pending |
| [ADR-006](./decisions/ADR-006-client-integration.md) | Client integration strategy — API-first, thin clients, on-device rationale | ✅ Written |

### Stage design documents (SDDs)

One document per pipeline stage. Each SDD covers: what the stage does, why it's designed that way, the full implementation, edge cases, error handling, and test requirements.

| Document | Stage | Status |
|----------|-------|--------|
| [SDD-001](./design/SDD-001-pipeline-overview.html) | Full pipeline overview — open in browser | 🔄 In progress |
| [SDD-002](./design/SDD-002-ingest-stage.md) | Ingest — decode, resample, normalise | ✅ Written |
| SDD-003 | Separate — Demucs source separation | 🔲 Pending |
| SDD-004 | Transcribe — Basic Pitch MIDI extraction | 🔲 Pending |
| SDD-005 | Score — music21 → MusicXML → PDF | 🔲 Pending |
| SDD-006 | API and job queue | 🔲 Pending |
| SDD-007 | Input adapters (file, URL, stream, device) | 🔲 Pending |

---

## Architecture in brief

```
Input adapter       →  file / URL / stream / device
  ↓ path: str
Ingest              →  librosa decode + normalise
  ↓ np.ndarray (2, N) float32 @ 44,100 Hz
Separate            →  Demucs htdemucs
  ↓ dict[str, np.ndarray]  (drums / bass / vocals / other)
Transcribe          →  Basic Pitch per stem
  ↓ dict[str, PrettyMIDI]
Outputs             →  FLAC stems / .mid files / MusicXML+PDF
  ↓ JobResult { stems, midi, score }
API                 →  REST + WebSocket
  ↓
Clients             →  Web embed / Mobile SDK
```

Each handoff is a typed contract. No stage reaches past its immediate neighbour. See [SDD-001](./design/SDD-001-pipeline-overview.html) for the full picture.

---

## Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Language | Python | ML research ecosystem — Demucs and Basic Pitch have no equivalent elsewhere |
| Audio I/O | librosa | Decodes any format; returns NumPy — universal internal representation |
| Source separation | Demucs `htdemucs` | Best quality on MUSDB18; hybrid waveform+spectrogram architecture |
| Transcription | Basic Pitch (Spotify) | Handles polyphony; classical methods don't |
| MIDI representation | pretty_midi | Clean object model; native Basic Pitch output |
| Score generation | music21 | Understands music theory; MusicXML output |

Full rationale in [ADR-001](./decisions/ADR-001-stack.md).

---

## Open questions

18 unresolved decisions are tracked in [SDD-001](./design/SDD-001-pipeline-overview.html#open-questions). The most blocking ones:

| ID | Question | Blocks |
|----|----------|--------|
| Q-STREAM-1 | Batch vs rolling-window streaming architecture | Stream adapter, pipeline design |
| Q-TRX-2 | Drum transcription — ADTLib vs onset-only vs skip | SDD-004, ADR-003 |
| Q-SEP-1 | Model loading — singleton vs per-job | SDD-003, ADR-002 |
| Q-API-1 | Authentication model | SDD-006 |

---

## Development setup

*(Stub — to be filled when implementation begins)*

```bash
# Python 3.11+
pip install librosa demucs basic-pitch pretty_midi music21

# FFmpeg required for MP3/MP4 decoding
brew install ffmpeg        # macOS
apt install ffmpeg         # Ubuntu/Debian
```

---

## Contributing

See [`../.github/CONTRIBUTING.md`](../.github/CONTRIBUTING.md) for how to add ADRs and SDDs.

**Engineering questions** → open an issue tagged `engineering`
**Pipeline design questions** → open an issue tagged `pipeline`
